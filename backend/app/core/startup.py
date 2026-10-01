"""Ordre de démarrage : PostgreSQL disponible, migrations, puis bootstrap."""
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.database import engine
from app.core.boostrap import bootstrap_initial_admin


def initialize_database():
    # Aussi valable hors Compose ; une migration en erreur n'est jamais rejouée
    # dans cette boucle. Seule la disponibilité de PostgreSQL est attendue.
    for attempt in range(30):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            break
        except OperationalError:
            if attempt == 29:
                raise
            time.sleep(1)

    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "app/db/migrations"))
    command.upgrade(config, "head")
    bootstrap_initial_admin()
