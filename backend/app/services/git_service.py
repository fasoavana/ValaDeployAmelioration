import os
from git import Repo
from git.exc import GitCommandError
import shutil

def clone_repository(repo_url, clone_path, branch='main'):
    """
    Clone a Git repository to the specified path.

    Args:
        repo_url (str): The URL of the Git repository.
        branch (str): The branch to clone. Defaults to 'main'.
        clone_path (str): The local path where the repository should be cloned.

    Returns:
        dict: A dictionary containing the clone path and commit hash.
    """
    try:
        # supprimer le dossier avant de cloner
        if os.path.exists(clone_path):
            shutil.rmtree(clone_path)

        # Ensure the parent directory exists
        parent_directory = os.path.dirname(clone_path)
        if parent_directory:
            ensure_directory_exists(parent_directory)

        # Clone the repository
        repository = Repo.clone_from(url=repo_url, to_path=clone_path, branch=branch)
        commit_hash = get_commit_hash(repository)
        return {"clone_path": clone_path, "commit_hash": commit_hash}
    except ValueError:
        raise # pour ne pas masquer les erreurs de validation
    except GitCommandError as e:
         raise ValueError(f"Impossible de cloner le dépôt : {e}")
    except Exception as e:
        raise ValueError(f"An error occurred while cloning the repository: {str(e)}")
    
def get_commit_hash(repository):
    """
    Get the latest commit hash of a Git repository.

    Args:
        repository (Repo): The Git repository object.

    Returns:
        str: The latest commit hash or an error message.
    """
    try:
        # Open the repository
        # Get the latest commit hash
        commit_hash = repository.head.commit.hexsha
        return commit_hash
    except Exception as e:
        raise ValueError(f"An error occurred while retrieving the commit hash: {str(e)}")
    
    
def ensure_directory_exists(path):
    """
    Ensure that the specified directory exists. If it doesn't, create it.

    Args:
        path (str): The path of the directory to check/create.
    """
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        raise ValueError(f"An error occurred while ensuring the directory exists: {str(e)}")