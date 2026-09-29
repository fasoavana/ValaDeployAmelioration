#app.services.build.builder
"""
Module de build d'images Docker.
Gère la compilation des images à partir des Dockerfiles.
"""
import logging
import os
import json
import docker
from app.core.docker_client import client
from typing import Optional, Dict

logger = logging.getLogger(__name__)

def build_docker_image(project_path: str,
                       slug: str, 
                       commit_hash: str,
                       build_args: Optional[Dict[str, str]] = None) -> str:
    """
    Build une image Docker pour le projet.
    
    Args:
        project_path: Chemin vers le répertoire du projet
        slug: Slug du projet
        commit_hash: Hash du commit
        build_args: Arguments de build optionnels (dictionnaire)
        
    Returns:
        str: Tag de l'image Docker construite
        
    Raises:
        ValueError: Si le build échoue
        FileNotFoundError: Si le chemin du projet n'existe pas
    """
    short_commit_hash = commit_hash[:7]
    image_tag = f"{slug}:{short_commit_hash}"

    try:
        logger.info(f"Démarrage du build Docker pour {image_tag}...")
        if build_args:
            logger.info(f"Arguments de build injectés : {build_args}")
        
        # Préparation des arguments pour le client Docker
        build_kwargs = {
            'path': project_path,
            'tag': image_tag,
            'rm': True,  # Nettoie les conteneurs intermédiaires
            # 'decode': True a été supprimé car il cause un bug de stream 
            # avec certaines versions du SDK Docker Python
        }
        
        # Si on a des build_args, on les ajoute au dictionnaire
        if build_args:
            build_kwargs['buildargs'] = build_args
        
        logger.info(f"Tentative de build avec les kwargs suivants : {build_kwargs}")

        # Vérification de sécurité avant l'appel
        if not os.path.isdir(project_path):
            logger.error(f"Le chemin de contexte de build n'existe pas ou n'est pas un dossier : {project_path}")
            raise FileNotFoundError(f"Le dossier de build est introuvable : {project_path}")

        # Build avec streaming des logs
        build_result = client.images.build(**build_kwargs)  
        
        # Le SDK retourne un tuple : (Image object, logs_generator)
        image, logs_generator = build_result
        
        # Traitement robuste des logs en temps réel
        for chunk in logs_generator:
            # Le SDK peut renvoyer des dictionnaires OU des bytes selon la version/config
            if isinstance(chunk, dict):
                if 'stream' in chunk:
                    logger.debug(chunk['stream'].strip())
                elif 'error' in chunk:
                    logger.error(chunk['error'])
                    raise ValueError(f"Erreur pendant le build: {chunk['error']}")
                    
            elif isinstance(chunk, bytes):
                try:
                    chunk_str = chunk.decode('utf-8')
                    # Parfois c'est du JSON, parfois du texte brut
                    chunk_data = json.loads(chunk_str)
                    if 'stream' in chunk_data:
                        logger.debug(chunk_data['stream'].strip())
                    elif 'error' in chunk_data:
                        logger.error(chunk_data['error'])
                        raise ValueError(f"Erreur pendant le build: {chunk_data['error']}")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Si ce n'est pas du JSON valide, on log le texte brut
                    logger.debug(chunk_str.strip())
            else:
                # Fallback pour tout autre type inattendu
                logger.debug(str(chunk).strip())
                
    except docker.errors.BuildError as e:
        # IMPORTANT : client.images.build() (API haut niveau) itère en interne
        # sur le stream brut AVANT de retourner quoi que ce soit. Dès qu'il
        # rencontre un chunk contenant 'error', il lève BuildError directement
        # à l'intérieur de l'appel ci-dessus : le for chunk in logs_generator
        # n'est donc JAMAIS exécuté dans ce cas, et son parsing détaillé ne
        # sert à rien pour diagnostiquer un échec.
        #
        # Heureusement, le SDK conserve tout l'historique des chunks émis
        # avant l'échec (via itertools.tee) et l'attache à l'exception dans
        # l'attribut e.build_log. On l'exploite ici pour remonter les vraies
        # lignes d'erreur (ex: la sortie complète de "npm ERR! ...") au lieu
        # du message générique "returned a non-zero code: 1".
        detailed_lines = []
        try:
            for chunk in e.build_log:
                if isinstance(chunk, dict) and 'stream' in chunk:
                    line = chunk['stream'].strip()
                    if line:
                        detailed_lines.append(line)
        except Exception:
            pass  # e.build_log peut être partiellement consommé selon le contexte

        full_log = "\n".join(detailed_lines[-50:])  # les 50 dernières lignes suffisent en général
        logger.error(f"Échec du build Docker pour {image_tag}")
        logger.error(f"Détail complet du build avant échec :\n{full_log}")
        logger.error(f"Message d'erreur final : {e}")

        raise ValueError(f"Failed to build Docker image: {e}\n\nLogs détaillés :\n{full_log}")
    except FileNotFoundError:
        # On remonte l'erreur telle quelle, elle est déjà loggée
        raise
    except Exception as e:
        logger.exception(f"Erreur inattendue lors du build Docker")
        raise ValueError(f"Erreur inattendue lors du build: {e}")

    logger.info(f"Build réussi : {image_tag}")
    return image_tag