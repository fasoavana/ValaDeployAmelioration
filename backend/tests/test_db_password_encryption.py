import os
from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet


BACKEND = Path(__file__).resolve().parents[1]

# Permet d'exécuter ce fichier seul, sans dépendre de l'ordre
# d'import des autres tests.
for line in (BACKEND / ".env.example").read_text().splitlines():
    if (
        line
        and not line.startswith("#")
        and "=" in line
    ):
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)

os.environ["ENCRYPTION_KEY"] = (
    Fernet.generate_key().decode()
)


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base

# Charger tous les modèles participant au registre ORM.
from app.models.user import User
from app.models.project import (
    Project,
    ProjectComponent,
    ProjectStatus,
    ComponentKind,
)
from app.models.deployment import DeploymentRun
from app.models.security_audit import SecurityAuditLog
from app.models.security_confirmation import SecurityConfirmation

from app.core.security import decrypt_data
from app.services.project_service import ProjectService


class DbPasswordEncryptionTests(unittest.TestCase):

    def setUp(self):

        self.engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
        )

        Base.metadata.create_all(self.engine)

        Session = sessionmaker(
            bind=self.engine
        )

        self.db = Session()

        project = Project(
            user_id=1,
            slug="db-password-test",
            repo_url="example",
            branch="main",
            replica=1,
            env_vars={},
            port=80,
            status=ProjectStatus.FAILED,
        )

        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        component = ProjectComponent(
            project_id=project.id,
            kind=ComponentKind.DATABASE,
            name="database",
            status=ProjectStatus.FAILED,
        )

        self.db.add(component)
        self.db.commit()
        self.db.refresh(component)

        self.component = component

    def tearDown(self):

        self.db.close()
        self.engine.dispose()

    def test_generated_password_is_encrypted_before_persistence(
        self,
    ):

        fake_password = (
            "FAKE_DB_PASSWORD_AFTER_TEST_ONLY"
        )

        with patch(
            "app.services.project_service."
            "secrets.token_urlsafe",
            return_value=fake_password,
        ):
            ProjectService.generate_db_credentials(
                self.db,
                self.component.id,
                "demo",
            )

        self.db.refresh(self.component)

        stored = self.component.db_password

        self.assertIsNotNone(stored)

        # La base ne doit jamais contenir le secret brut.
        self.assertNotEqual(
            stored,
            fake_password,
        )

        # Mais l'application doit pouvoir récupérer le secret
        # uniquement lorsqu'il est réellement nécessaire.
        self.assertEqual(
            decrypt_data(stored),
            fake_password,
        )

    def test_retry_does_not_reencrypt_existing_password(
        self,
    ):

        fake_password = (
            "FAKE_DB_PASSWORD_RETRY_TEST_ONLY"
        )

        with patch(
            "app.services.project_service."
            "secrets.token_urlsafe",
            return_value=fake_password,
        ):
            ProjectService.generate_db_credentials(
                self.db,
                self.component.id,
                "demo",
            )

        self.db.refresh(self.component)

        first_ciphertext = (
            self.component.db_password
        )

        ProjectService.generate_db_credentials(
            self.db,
            self.component.id,
            "demo",
        )

        self.db.refresh(self.component)

        self.assertEqual(
            self.component.db_password,
            first_ciphertext,
        )

        self.assertEqual(
            decrypt_data(
                self.component.db_password
            ),
            fake_password,
        )


if __name__ == "__main__":
    unittest.main()
