# app/services/log_service.py
import asyncio
import logging
from typing import AsyncIterator

import docker

from app.core.docker_client import client

logger = logging.getLogger(__name__)


from app.core.exceptions import ContainerNotFoundError

async def stream_container_logs(container_ref: str, tail: int = 200) -> AsyncIterator[str]:
    """
    Stream les logs d'un conteneur ligne par ligne, de façon non-bloquante
    pour la boucle asyncio.

    docker-py est synchrone : la lecture du flux (`container.logs(stream=True,
    follow=True)`) se fait donc dans un thread à part (run_in_executor), et
    chaque ligne est poussée dans une asyncio.Queue que la coroutine
    consomme avec `await`.
    """
    try:
        container = client.containers.get(container_ref)
    except docker.errors.NotFound:
        raise ContainerNotFoundError(container_ref)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _read_logs():
        try:
            for log_line in container.logs(follow=True, stream=True, tail=tail):
                if stop_event.is_set():
                    break
                loop.call_soon_threadsafe(
                    queue.put_nowait, log_line.decode(errors="replace")
                )
        except Exception as e:  # noqa: BLE001 - on veut remonter n'importe quelle erreur au client
            loop.call_soon_threadsafe(queue.put_nowait, e)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # signal de fin

    loop.run_in_executor(None, _read_logs)

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        # Signale au thread de s'arrêter. Limite connue : comme la lecture
        # est bloquée sur le socket Docker en attendant la prochaine ligne,
        # le thread ne se termine réellement qu'à la prochaine ligne de log
        # (ou à l'arrêt du conteneur). Sans impact sur la boucle asyncio,
        # mais à garder en tête si beaucoup de connexions restent ouvertes
        # longtemps sur des conteneurs peu bavards.
        stop_event.set()