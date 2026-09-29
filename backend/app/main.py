from contextlib import asynccontextmanager

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

from app.core.boostrap import bootstrap_initial_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Exécuté au démarrage du serveur
    bootstrap_initial_admin()
    yield
    # Exécuté à l'arrêt du serveur (nettoyage si besoin)
    
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