import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.core.config import settings

from app.api.routes_deploy import router as deploy_router
from app.api.routes_logs import router as logs_router
from app.api.routes_auth import router as auth_router
from app.api.routes_projects import router as project_router
from app.api.routes_security import router as security_router
from app.api.routes_stack import router as stack_router
from app.api.routes_deployment import router as deployment_router
from app.api.routes_metrics import router as metrics_router
from fastapi.middleware.cors import CORSMiddleware

from app.core.startup import initialize_database
from app.services.network_service import reconcile_traefik_ingress_networks
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

NETWORK_RECONCILE_INTERVAL_SECONDS = 5


async def _network_reconciliation_loop():
    """
    Vérifie périodiquement que Traefik reste connecté aux réseaux
    ingress gérés par ValaDeploy.
    """
    while True:
        try:
            connected = await run_in_threadpool(
                reconcile_traefik_ingress_networks
            )

            if connected:
                logger.info(
                    "Traefik reconnecté aux réseaux ingress : %s",
                    ", ".join(connected),
                )

        except Exception as exc:
            # Une indisponibilité temporaire de Docker ou de Traefik
            # ne doit pas empêcher le backend ValaDeploy de fonctionner.
            logger.warning(
                "Réconciliation des réseaux ingress impossible : %s",
                exc,
            )

        await asyncio.sleep(NETWORK_RECONCILE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialisation de la base de données.
    await run_in_threadpool(initialize_database)

    # 2. Réconciliation continue des réseaux ingress.
    network_task = asyncio.create_task(
        _network_reconciliation_loop()
    )

    try:
        yield
    finally:
        network_task.cancel()

        with suppress(asyncio.CancelledError):
            await network_task
    
app = FastAPI(
    title=settings.APP_NAME,
    description="Projet de memoire",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://app.localhost:8080", "http://localhost:8080"],  # Tes domaines
    allow_credentials=True,  # OBLIGATOIRE pour les cookies httpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(deploy_router, prefix="/api")
app.include_router(stack_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(project_router, prefix="/api")
app.include_router(security_router, prefix="/api")
app.include_router(deployment_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")

@app.get("/")
def show_message():
    return {"message": "it's work"}