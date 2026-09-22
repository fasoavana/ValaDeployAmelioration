#app/api/routes_logs.py

import asyncio
import logging
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.db.database import Session_local
from app.core.security import decode_token
from app.core.exceptions import ContainerNotFoundError
from app.services.logs_service import stream_container_logs
from app.services.project_service import ProjectService
from app.models.project import ProjectComponent, ProjectStatus

logger = logging.getLogger(__name__)
router = APIRouter()

async def stream_file_logs_tail(file_path: str):
    """Lit un fichier de log en temps réel (équivalent à tail -f)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.5)
                continue
            yield line

@router.websocket("/logs/{slug}")
async def websocket_logs(websocket: WebSocket,
                          slug: str,
                          token: str = Query(None),
                          component_id: str = Query(None)):
    if not token:
        token = websocket.cookies.get("access_token")
    if not token:
        logger.warning("WS logs %s: token manquant", slug)
        await websocket.close(code=4401)
        return
    
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception as e:
        logger.warning("WS logs %s: échec decode_token (%s)", slug, e)
        await websocket.close(code=4401)
        return

    db = Session_local()
    try:
        project = ProjectService.get_project_by_slug(db, slug)
        if project is None or project.user_id != user_id:
            logger.warning("WS logs %s: projet introuvable ou non autorisé", slug)
            await websocket.close(code=4404)
            return
        
        container_ref = None
        if component_id:
            component = db.query(ProjectComponent).filter(
                ProjectComponent.id == int(component_id),
                ProjectComponent.project_id == project.id
            ).first()
            if component and component.container_ids:
                container_ref = component.container_ids[0]
        else:
            if project.container_ids:
                container_ref = project.container_ids[0]

        build_log_path = f"app/logs/build_{project.id}.log"
        await websocket.accept()

        # 1. Envoyer l'historique du build s'il existe (même si le build est fini)
        if os.path.exists(build_log_path):
            await websocket.send_text("---  Historique du pipeline de build ---\n")
            try:
                with open(build_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        await websocket.send_text(line)
            except Exception as e:
                logger.error(f"Erreur lecture historique log: {e}")
            await websocket.send_text("\n---  Fin de l'historique ---\n")

        # 2. Stream en temps réel selon l'état du projet
        if project.status == ProjectStatus.BUILDING and os.path.exists(build_log_path):
            await websocket.send_text("---  Stream du build en temps réel ---\n")
            try:
                async for line in stream_file_logs_tail(build_log_path):
                    await websocket.send_text(line)
            except Exception as e:
                logger.error(f"Erreur stream fichier log: {e}")
                
        elif container_ref and project.status in [ProjectStatus.RUNNING, ProjectStatus.BUILDING]:
            await websocket.send_text("---  Stream des logs du conteneur en direct ---\n")
            try:
                async for line in stream_container_logs(container_ref):
                    await websocket.send_text(line)
            except ContainerNotFoundError:
                await websocket.send_text("--- Conteneur introuvable ou arrêté ---")
        else:
            await websocket.send_text("--- Le déploiement est terminé. Aucun stream actif. ---")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Erreur WebSocket logs pour %s", slug)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        finally:
            db.close()