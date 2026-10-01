"""Régressions de stabilisation. Docker simulé ; SQLite ne valide pas PostgreSQL.

Exécuter : python -m unittest discover -s tests -p 'test_stabilization.py' -v
"""
import importlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet

BACKEND = Path(__file__).resolve().parents[1]
# Toutes les valeurs Settings sont remplacées : aucun secret réel utilisé.
for line in (BACKEND / '.env.example').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        os.environ[key] = value
os.environ['ENCRYPTION_KEY'] = Fernet.generate_key().decode()

with patch('docker.from_env', return_value=MagicMock()):
    import app.main
    from app.services import container_service as cs
    from app.services import deploy_service as ds
    from app.services.build import builder
    from app.services.stack_deployment.app_component_deployer import AppComponentDeployer
    from app.services.stack_deployment.database_deployer import DatabaseComponentDeployer
from app.core.image_reference import validate_image_reference
from app.core import startup
from app.core.config import Settings
from app.models.project import Project, ProjectComponent, ProjectStatus, ComponentKind, FailReason
from app.models.deployment import DeploymentRun, PipelineStatus
from app.schemas.stack_deploy import StackComponentSchema
from app.schemas.deploy import CloneSchema
from app.services.project_service import ProjectService
from app.services.security_profile import get_runtime_port, get_security_profile, STANDARD_PROFILE
from app.services.build.detector import ProjectType, detect_project_type
from app.services.build.generator import generate_dockerfile
from app.services.stack_deployment.context import StackDeploymentContext
from app.api import routes_projects, routes_stack
from app.db.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pydantic import ValidationError
import docker


class References(unittest.TestCase):
    def test_valid_references(self):
        for value in ['postgres:15-alpine', 'nginx', 'team/app:Release_1',
                      'localhost:5000/team/app:v1', 'registry.example.com/a/b',
                      '[::1]:5000/team/app:latest', 'nginx@sha256:' + 'a'*64,
                      'nginx:alpine@sha256:' + 'b'*64, 'sha256:' + 'c'*64]:
            with self.subTest(value=value):
                self.assertEqual(validate_image_reference(value), value)

    def test_invalid_references(self):
        for value in [None, '', 'PostgreSQL 15', 'PostgreSQL:15', 'postgres ',
                      'https://docker.io/postgres', 'app:', 'team//app',
                      'app@sha256:abc', 'app@sha256:' + 'g'*64, 'repo/app:bad tag',
                      'registry:bad/app', '-app', 'app:' + 'a'*129]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'postgres:15-alpine'):
                validate_image_reference(value)

    def test_invalid_database_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            StackComponentSchema(name='db', kind='database', db_image='PostgreSQL 15')

    def test_zero_replicas_rejected(self):
        with self.assertRaises(ValidationError):
            CloneSchema(slug='app', repo_url='example', port=80, replica=0)

    def test_bad_reference_has_no_docker_side_effect(self):
        with patch.object(cs, 'client') as client:
            with self.assertRaises(ValueError):
                cs.run_container('PostgreSQL 15', 'db', 'net', expose_traefik=False)
            self.assertEqual(client.mock_calls, [])


class Runtime(unittest.TestCase):
    def test_ports_and_profiles(self):
        for value in [ProjectType.REACT_VITE, 'react_vite']:
            self.assertEqual(get_runtime_port(value, 80), 8080)
            self.assertTrue(get_security_profile(value).read_only)
        self.assertEqual(get_runtime_port('laravel_monolith', 80), 8000)
        self.assertEqual(get_runtime_port('dockerfile', 9000), 9000)
        self.assertEqual(get_security_profile('python'), STANDARD_PROFILE)

    def test_application_creation_has_profile_and_correct_labels(self):
        with patch.object(cs, 'client') as client, patch.object(cs, 'verify_containers_running') as verify:
            client.containers.get.side_effect = docker.errors.NotFound('missing')
            client.containers.create.return_value.id = 'new-id'
            result = cs.run_container('demo:v1', 'demo-1', 'net', port=8080,
                security_profile=get_security_profile('react_vite'))
            kwargs = client.containers.create.call_args.kwargs
            from docker.models.containers import _create_container_args
            # Exerce réellement la conversion des kwargs par le SDK installé.
            _create_container_args(dict(kwargs, version='1.44'))
            self.assertEqual(result, 'new-id')
            self.assertEqual(kwargs['cap_drop'], ['ALL'])
            self.assertTrue(kwargs['read_only'])
            self.assertEqual(kwargs['labels']['traefik.http.services.demo-1.loadbalancer.server.port'], '8080')
            verify.assert_called_once_with(['new-id'])

    def test_database_explicitly_exempt(self):
        with patch.object(cs, 'client') as client, patch.object(cs, 'verify_containers_running'):
            client.containers.get.side_effect = docker.errors.NotFound('missing')
            cs.run_container('postgres:15-alpine', 'db', 'net', expose_traefik=False, security_profile=None)
            kwargs = client.containers.create.call_args.kwargs
            self.assertNotIn('cap_drop', kwargs)
            self.assertNotIn('read_only', kwargs)
            self.assertEqual(kwargs['labels'], {})

    def test_database_retry_reuses_anonymous_volume(self):
        with patch.object(cs, 'client') as client, patch.object(cs, 'verify_containers_running'), patch.object(cs, 'archive_container_evidence'):
            client.containers.get.return_value.attrs = {'Mounts': [
                {'Type': 'volume', 'Name': 'anonymous-volume-id', 'Destination': '/var/lib/postgresql/data', 'RW': True}
            ]}
            cs.run_container('postgres:15-alpine', 'db', 'net', expose_traefik=False,
                             security_profile=None, preserve_volumes=True)
            self.assertEqual(client.containers.create.call_args.kwargs['volumes'], {
                'anonymous-volume-id': {'bind': '/var/lib/postgresql/data', 'mode': 'rw'}
            })

    def test_external_image_is_pulled_when_absent(self):
        with patch.object(cs, 'client') as client, patch.object(cs, 'verify_containers_running'):
            client.containers.get.side_effect = docker.errors.NotFound('missing')
            client.containers.create.side_effect = [docker.errors.ImageNotFound('missing image'), SimpleNamespace(id='new', start=lambda: None)]
            self.assertEqual(cs.run_container('postgres:15-alpine', 'db', 'net', expose_traefik=False, security_profile=None), 'new')
            client.images.pull.assert_called_once_with('postgres:15-alpine')

    def test_start_failure_keeps_created_id(self):
        with patch.object(cs, 'client') as client:
            client.containers.get.side_effect = docker.errors.NotFound('missing')
            container = client.containers.create.return_value
            container.id = 'partial-id'
            container.start.side_effect = docker.errors.APIError('cannot start')
            with self.assertRaises(cs.ContainerDeploymentError) as caught:
                cs.run_container('demo:v1', 'demo-1', 'net', port=8000)
            self.assertEqual(caught.exception.container_ids, ['partial-id'])
            container.remove.assert_not_called()

    def test_exit_detected_after_initial_running(self):
        running = SimpleNamespace(status='running', name='app', attrs={'State': {'ExitCode': 0}})
        exited = SimpleNamespace(status='exited', name='app', attrs={'State': {'ExitCode': 1}})
        with patch.object(cs, 'client') as client, patch.object(cs.time, 'sleep'), patch.object(cs.time, 'monotonic', side_effect=[0, 0, 1]):
            client.containers.get.side_effect = [running, exited]
            with self.assertRaisesRegex(cs.ContainerDeploymentError, 'ExitCode=1'):
                cs.verify_containers_running(['id'], delay=3)

    def test_exit_zero_is_not_deployment_success(self):
        with patch.object(cs, 'client') as client:
            client.containers.get.return_value = SimpleNamespace(status='exited', name='app', attrs={'State': {'ExitCode': 0}})
            with self.assertRaisesRegex(cs.ContainerDeploymentError, 'ExitCode=0'):
                cs.verify_containers_running(['id'], delay=0)

    def test_missing_container_is_failure(self):
        with patch.object(cs, 'client') as client:
            client.containers.get.side_effect = docker.errors.NotFound('missing')
            with self.assertRaises(cs.ContainerDeploymentError):
                cs.verify_containers_running(['id'], delay=0)

    def test_all_replicas_required(self):
        with patch.object(cs, 'client') as client:
            client.containers.get.side_effect = [
                SimpleNamespace(status='running', attrs={'State': {}}),
                SimpleNamespace(status='exited', attrs={'State': {'ExitCode': 1}}),
            ]
            self.assertEqual(cs.get_real_containers_status(['a', 'b']), ProjectStatus.FAILED)

    def test_scale_preserves_all_partial_ids_and_scopes_names(self):
        other = MagicMock(name='other')
        other.name = 'my-app-back-1'
        with patch.object(cs, 'client') as client, patch.object(cs, 'run_container', side_effect=['first', cs.ContainerDeploymentError('failed', ['second'])]):
            client.containers.list.return_value = [other]
            with self.assertRaises(cs.ContainerDeploymentError) as caught:
                cs.scale_project('my-app:v1', 'my-app', 'net', 2, port=8000)
            self.assertEqual(caught.exception.container_ids, ['first', 'second'])
            other.remove.assert_not_called()

    def test_recreation_preserves_runtime_environment_volumes_and_names(self):
        old = MagicMock()
        old.name = 'demo-front-1'
        old.image.id = 'sha256:' + 'a'*64
        old.image.attrs = {'Config': {'Labels': {'io.valadeploy.runtime-type': 'react_vite'}}}
        old.attrs = {
            'Config': {'Env': ['GENERATED=value'], 'User': 'nginx', 'Cmd': ['nginx'],
                       'Labels': {'traefik.enable': 'true', 'custom.label': 'preserved'}},
            'NetworkSettings': {'Networks': {'net-demo': {}, cs.settings.APP_NETWORK: {}}},
            'Mounts': [{'Type': 'volume', 'Name': 'my-data', 'Destination': '/data', 'RW': True}],
        }
        with patch.object(cs, 'client') as client, patch.object(cs, 'run_container', return_value='new') as run:
            client.containers.get.return_value = old
            self.assertEqual(cs.recreate_container('old', 'demo', 80), 'new')
            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs['port'], 8080)
            self.assertTrue(kwargs['security_profile'].read_only)
            self.assertEqual(kwargs['plain_envs_var'], {'GENERATED': 'value'})
            self.assertEqual(kwargs['volumes']['my-data']['bind'], '/data')
            self.assertEqual(kwargs['slug'], old.name)
            self.assertEqual(kwargs['labels']['custom.label'], 'preserved')
            self.assertEqual(kwargs['extra_networks'], [cs.settings.APP_NETWORK])

    def test_legacy_recreation_fails_before_removal(self):
        old = MagicMock()
        old.attrs = {'Config': {}}
        old.image.attrs = {'Config': {}}
        with patch.object(cs, 'client') as client:
            client.containers.get.return_value = old
            with self.assertRaisesRegex(ValueError, 'Retry'):
                cs.recreate_container('old', 'demo', 80)
            old.remove.assert_not_called()

    def test_rebuild_has_unique_tag_and_runtime_metadata(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(builder, 'client') as client:
            client.images.build.side_effect = [(MagicMock(), []), (MagicMock(), [])]
            first = builder.build_docker_image(directory, 'demo', 'abcdef0123', project_type=ProjectType.REACT_VITE)
            second = builder.build_docker_image(directory, 'demo', 'abcdef0123', project_type=ProjectType.REACT_VITE)
            self.assertNotEqual(first, second)
            self.assertEqual(client.images.build.call_count, 2)
            self.assertEqual(client.images.build.call_args.kwargs['labels']['io.valadeploy.runtime-type'], 'react_vite')
            client.images.prune.assert_not_called()

    def test_fresh_clone_context_gets_current_template(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'package.json').write_text('{"dependencies":{"react":"*","vite":"*"}}')
            kind = detect_project_type(directory)
            generate_dockerfile(kind, directory)
            self.assertIn('USER nginx', (p/'Dockerfile').read_text())
            self.assertIn('listen 8080', (p/'nginx.conf.template').read_text())


class DatabaseAndPipelines(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = os.getcwd()
        self.log_directory = tempfile.TemporaryDirectory()
        os.chdir(self.log_directory.name)
        self.engine = create_engine('sqlite://', poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.db = self.sessions()
        self.project = Project(user_id=1, slug='demo', repo_url='example', branch='main',
            replica=1, env_vars={}, port=80, status=ProjectStatus.FAILED, pipeline_run_id='run')
        self.db.add(self.project)
        self.db.commit()
        self.pid = self.project.id

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        os.chdir(self.previous_cwd)
        self.log_directory.cleanup()

    def add_component(self, kind, name, **kw):
        comp = ProjectComponent(project_id=self.pid, kind=kind, name=name,
            status=ProjectStatus.FAILED, **kw)
        self.db.add(comp)
        self.db.commit()
        return comp

    def test_create_stack_persists_exposure_and_initial_token(self):
        project = ProjectService.create_pending_stack(self.db, SimpleNamespace(id=1), 'new-stack', [
            {'name': 'front', 'kind': ComponentKind.FRONT, 'repo_url': 'example', 'port': 80, 'expose_publicly': False},
            {'name': 'db', 'kind': ComponentKind.DATABASE, 'db_image': 'postgres:15-alpine'},
        ])
        self.assertTrue(project.pipeline_run_id)
        self.assertEqual(len(project.services), 2)
        self.assertFalse(project.services[0].expose_publicly)

    def test_create_mono_has_initial_token(self):
        project = ProjectService.create_pending_project(self.db, SimpleNamespace(id=1), 'new-mono',
            'example', 'main', 1, {}, 80)
        self.assertTrue(project.pipeline_run_id)
        self.assertEqual(project.status, ProjectStatus.BUILDING)

    def test_credentials_not_regenerated(self):
        comp = self.add_component(ComponentKind.DATABASE, 'db')
        ProjectService.generate_db_credentials(self.db, comp.id, 'demo')
        initial = comp.db_password
        ProjectService.generate_db_credentials(self.db, comp.id, 'demo')
        self.assertEqual(comp.db_password, initial)

    def test_retry_preserves_resources_and_private_exposure(self):
        comp = self.add_component(ComponentKind.FRONT, 'front', port=80, expose_publicly=False, container_ids=['old'])
        with patch.object(ds, 'client') as client:
            project, stack, components, token = ds.DeployService.retry_deployment(self.db, self.pid, 1)
            self.assertTrue(stack)
            self.assertEqual(comp.container_ids, ['old'])
            self.assertFalse(comp.expose_publicly)
            self.assertNotEqual(token, 'run')
            client.volumes.list.assert_not_called()
            client.images.list.assert_not_called()

    def test_double_retry_rejected(self):
        ds.DeployService.retry_deployment(self.db, self.pid, 1)
        with self.assertRaisesRegex(ValueError, 'déjà en cours'):
            ds.DeployService.retry_deployment(self.db, self.pid, 1)

    def test_legacy_exposure_no_guess(self):
        self.add_component(ComponentKind.FRONT, 'front', port=80, expose_publicly=None)
        with self.assertRaisesRegex(ValueError, 'Exposition inconnue'):
            ds.DeployService.retry_deployment(self.db, self.pid, 1)
        self.assertEqual(self.project.status, ProjectStatus.FAILED)

    def test_failed_real_status_is_not_erased(self):
        result = routes_projects.get_real_container_status('demo', None, self.db, SimpleNamespace(id=1))
        self.assertEqual(result['status'], 'failed')

    def test_stopping_failed_mono_keeps_failure(self):
        self.project.container_ids = ['partial']
        self.project.error_message = 'deployment failed'
        self.db.commit()
        with patch.object(routes_projects, 'manage_container_state'):
            result = routes_projects.project_action('demo', 'stop', None, self.db, SimpleNamespace(id=1))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.project.error_message, 'deployment failed')

    def test_stack_aggregation_rejects_partial_running(self):
        components = [SimpleNamespace(status=status) for status in [ProjectStatus.RUNNING, ProjectStatus.STOPPED]]
        self.assertEqual(ProjectService.aggregate_component_status(components), ProjectStatus.FAILED)

    def test_mono_pipeline_partial_failure_keeps_ids(self):
        self.project.status = ProjectStatus.BUILDING
        self.db.commit()
        scan = {'blocking': False, 'severity_count': {}, 'critical_vulnerabilities': []}
        with nullcontext():
            with patch.object(ds, 'Session_local', self.sessions), patch.object(ds, 'project_deployment_lock', return_value=nullcontext()), \
                 patch.object(ds, 'clone_repository', return_value={'commit_hash': 'abc1234'}), \
                 patch.object(ds, 'detect_secret', return_value={'blocking': False}), \
                 patch.object(ds, 'detect_project_type', return_value=ProjectType.REACT_VITE), \
                 patch.object(ds, 'prepare_build_environment'), patch.object(ds, 'generate_dockerfile'), \
                 patch.object(ds, 'build_docker_image', return_value='demo:new'), patch.object(ds, 'scan_image', return_value=scan), \
                 patch.object(ds, 'scale_project', side_effect=cs.ContainerDeploymentError('ExitCode=1', ['partial'])):
                ds.DeployService.run_deployment_pipeline(self.pid, CloneSchema(slug='demo', repo_url='example', port=80), 1, 'run')
        self.db.expire_all()
        p = self.db.get(Project, self.pid)
        self.assertEqual(p.status, ProjectStatus.FAILED)
        self.assertEqual(p.container_ids, ['partial'])
        self.assertEqual(p.fail_reason, FailReason.DEPLOY_ERROR)
        self.assertEqual(self.db.query(DeploymentRun).one().status, PipelineStatus.FAILED)

    def test_stack_failed_database_does_not_start_backend(self):
        db_comp = self.add_component(ComponentKind.DATABASE, 'db', db_image='postgres:15-alpine', expose_publicly=False)
        back = self.add_component(ComponentKind.BACK, 'back', port=8000, expose_publicly=False)
        self.project.status = ProjectStatus.BUILDING
        self.db.commit()
        def fail_db(ctx):
            ProjectService.mark_component_failed(ctx.db, ctx.component.id, 'DB failed', FailReason.DEPLOY_ERROR)
        fake_db = SimpleNamespace(deploy=fail_db)
        fake_back = MagicMock()
        payloads = [{'component_id': c.id, 'kind': c.kind, 'name': c.name} for c in [db_comp, back]]
        with patch.object(ds, 'Session_local', self.sessions), patch.object(ds, 'project_deployment_lock', return_value=nullcontext()), \
             patch.object(ds, 'ensure_project_network', return_value='net-demo'), \
             patch.object(ds, 'get_component_deployer', side_effect=[fake_db, fake_back]):
            ds.DeployService.run_stack_deployment_pipeline(self.pid, 'demo', payloads, 1, 'run')
        fake_back.deploy.assert_not_called()
        self.db.expire_all()
        self.assertEqual(self.db.get(Project, self.pid).status, ProjectStatus.FAILED)
        self.assertEqual(self.db.get(ProjectComponent, back.id).status, ProjectStatus.FAILED)
        self.assertEqual(self.db.query(DeploymentRun).one().status, PipelineStatus.FAILED)

    def test_app_component_uses_profile_and_runtime_port(self):
        comp = self.add_component(ComponentKind.FRONT, 'front', port=80, expose_publicly=True)
        ctx = StackDeploymentContext(self.db, 'demo', 'net-demo', [], lambda x: None, None, lambda: False)
        ctx.component = comp
        ctx.comp_payload = {'port': 80, 'expose_publicly': True, 'replica': 1}
        ctx.container_name = 'demo-front'
        ctx.detect_result = ProjectType.REACT_VITE
        ctx.build_result = 'demo:new'
        ctx.clone_result = {'commit_hash': 'abcdef'}
        module = importlib.import_module(AppComponentDeployer.__module__)
        with patch.object(module, 'scale_project', return_value=['id']) as scale:
            AppComponentDeployer()._deploy_container(ctx)
            self.assertEqual(scale.call_args.kwargs['port'], 8080)
            self.assertTrue(scale.call_args.kwargs['security_profile'].read_only)


class StartupAndMigrations(unittest.TestCase):
    def test_startup_order(self):
        events = []
        with patch.object(startup, 'engine'), patch.object(startup.command, 'upgrade', side_effect=lambda *args: events.append('migration')), \
             patch.object(startup, 'bootstrap_initial_admin', side_effect=lambda: events.append('admin')):
            startup.initialize_database()
        self.assertEqual(events, ['migration', 'admin'])

    def test_migration_error_blocks_admin(self):
        with patch.object(startup, 'engine'), patch.object(startup.command, 'upgrade', side_effect=RuntimeError('migration failed')), \
             patch.object(startup, 'bootstrap_initial_admin') as admin:
            with self.assertRaises(RuntimeError):
                startup.initialize_database()
            admin.assert_not_called()

    def test_example_contains_all_settings(self):
        keys = {line.split('=', 1)[0] for line in (BACKEND/'.env.example').read_text().splitlines() if line and not line.startswith('#') and '=' in line}
        self.assertEqual(keys, set(Settings.model_fields))

    def test_migration_graph_and_offline_sql(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic import command
        output = io.StringIO()
        config = Config(str(BACKEND/'alembic.ini'), output_buffer=output)
        config.set_main_option('script_location', str(BACKEND/'app/db/migrations'))
        self.assertEqual(ScriptDirectory.from_config(config).get_heads(), ['d83a72b91e60'])
        command.upgrade(config, 'head', sql=True)
        sql = output.getvalue()
        self.assertIn('CREATE TABLE users', sql)
        self.assertIn('ADD COLUMN expose_publicly BOOLEAN', sql)

    def test_import_all_application_modules(self):
        for path in (BACKEND/'app').rglob('*.py'):
            if 'migrations' in path.parts:
                continue
            name = '.'.join(path.relative_to(BACKEND).with_suffix('').parts)
            importlib.import_module(name)


if __name__ == '__main__':
    unittest.main()
