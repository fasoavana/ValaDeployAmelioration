#app/services/stack_deployment/context.py
class StackDeploymentContext:
    """
    Tout l'état partagé entre les composants d'une même stack, passé à chaque
    ComponentDeployer. Un seul objet créé par pipeline (run_stack_deployment_pipeline) :

    - certains champs sont fixes pour toute la durée du pipeline (db, slug,
      project_network, components, log, history_run_id, is_cancelled) ;
    - d'autres sont réassignés par l'orchestrateur à chaque itération de la
      boucle (comp_payload, component, container_name, ...) ;
    - db_component est accumulé au fil du traitement : posé par
      DatabaseComponentDeployer une fois la DB démarrée, relu ensuite par
      BackComponentDeployer pour construire DB_URL.
    """

    def __init__(self, db, slug, project_network, components, log, history_run_id, is_cancelled):
        # --- Fixe pour tout le pipeline ---
        self.db = db
        self.slug = slug
        self.project_network = project_network
        self.components = components  # payload complet de la stack (tous les composants)
        self.log = log
        self.history_run_id = history_run_id
        self.is_cancelled = is_cancelled

        # --- Accumulé au fil des composants ---
        self.db_component = None  # ProjectComponent DATABASE, une fois traité

        # --- Réassigné à chaque itération par l'orchestrateur ---
        self.comp_payload = None
        self.component = None
        self.container_name = None
        self.destination_path = None
        self.clone_result = None
        self.build_result = None

        # Signal levé par un ComponentDeployer quand un checkpoint d'annulation
        # est déclenché : l'orchestrateur doit alors `break` la boucle des
        # composants (au lieu d'un simple `continue` sur échec ordinaire).
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True
