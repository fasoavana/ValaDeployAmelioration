"""Un seul pipeline peut modifier les ressources d'un projet à la fois."""
from contextlib import contextmanager
from sqlalchemy import text
from app.db.database import engine


@contextmanager
def project_deployment_lock(project_id):
    # Verrou de session, indépendant des commits du suivi de pipeline.
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(824602, :id)"), {"id": project_id})
        connection.commit()
        try:
            yield
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(824602, :id)"), {"id": project_id})
            connection.commit()
