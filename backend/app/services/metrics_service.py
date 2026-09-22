import docker
from app.core.docker_client import client
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def _format_bytes(bytes_value: int) -> str:
    """Formate les bytes en unité lisible (KB, MB, GB)"""
    if bytes_value == 0:
        return "0B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    value = float(bytes_value)
    
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(value)}{units[unit_index]}"
    return f"{value:.0f}{units[unit_index]}"


def get_container_stats(container_id: str) -> Optional[dict]:
    """
    Récupère les stats en temps réel d'un conteneur Docker.
    Retourne None si le conteneur n'existe pas ou n'est pas running.
    """
    try:
        container = client.containers.get(container_id)
        
        if container.status != 'running':
            return None
        
        # Récupération des stats (stream=False pour avoir un snapshot)
        stats = container.stats(stream=False)
        
        # Calcul CPU
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * stats['cpu_stats']['online_cpus'] * 100
        else:
            cpu_percent = 0.0
        
        # Mémoire
        memory_usage = stats['memory_stats'].get('usage', 0) or 0
        memory_limit = stats['memory_stats'].get('limit', 0) or 0
        
        if memory_limit > 0:
            memory_percent = (memory_usage / memory_limit) * 100
        else:
            memory_percent = 0.0
        
        # Réseau
        network_rx = 0
        network_tx = 0
        if 'networks' in stats:
            for iface_stats in stats['networks'].values():
                network_rx += iface_stats.get('rx_bytes', 0)
                network_tx += iface_stats.get('tx_bytes', 0)
        
        return {
            'container_id': container_id,
            'container_name': container.name,
            'cpu_percent': round(cpu_percent, 2),
            'memory_usage': memory_usage,
            'memory_limit': memory_limit,
            'memory_percent': round(memory_percent, 2),
            'network_rx': network_rx,
            'network_tx': network_tx
        }
        
    except docker.errors.NotFound:
        logger.warning(f"Conteneur {container_id} introuvable")
        return None
    except Exception as e:
        logger.error(f"Erreur récupération stats pour {container_id}: {e}")
        return None


def get_project_metrics(project_slug: str, container_ids: list[str]) -> dict:
    """
    Agrège les métriques de tous les conteneurs d'un projet.
    """
    if not container_ids:
        return {
            'project_slug': project_slug,
            'total_cpu_percent': 0.0,
            'total_memory_usage': 0,
            'total_memory_limit': 0,
            'memory_usage_formatted': '0B / 0B',
            'container_count': 0,
            'containers': [],
        }
    
    containers_stats = []
    total_cpu = 0.0
    total_memory_usage = 0
    total_memory_limit = 0
    
    for container_id in container_ids:
        stats = get_container_stats(container_id)
        if stats:
            containers_stats.append(stats)
            total_cpu += stats['cpu_percent']
            total_memory_usage += stats['memory_usage']
            total_memory_limit += stats['memory_limit']
    
    # Formatage lisible de la mémoire
    memory_formatted = f"{_format_bytes(total_memory_usage)} / {_format_bytes(total_memory_limit)}"
    
    return {
        'project_slug': project_slug,
        'total_cpu_percent': round(total_cpu, 2),
        'total_memory_usage': total_memory_usage,
        'total_memory_limit': total_memory_limit,
        'memory_usage_formatted': memory_formatted,
        'container_count': len(containers_stats),
        'containers': containers_stats,
    }