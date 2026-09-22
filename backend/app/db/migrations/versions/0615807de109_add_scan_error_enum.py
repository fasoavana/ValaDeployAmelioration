"""add SCAN_ERROR value to failreason enum

Revision ID: 0615807de109
Revises: 25d2a58dc9ba
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0615807de109'
down_revision: Union[str, Sequence[str], None] = '25d2a58dc9ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE ne peut pas tourner à l'intérieur de la transaction
    # implicite d'Alembic sur PostgreSQL < 12 (et pose problème si utilisé dans la
    # même transaction juste avant d'insérer une ligne avec cette valeur, même en
    # PG >= 12). autocommit_block() force cette instruction à s'exécuter hors
    # transaction, en toute sécurité.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE failreason ADD VALUE IF NOT EXISTS 'SCAN_ERROR'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL ne permet pas de retirer une valeur d'un enum sans recréer le
    # type entièrement (et migrer toutes les colonnes qui l'utilisent). On laisse
    # volontairement cette migration non réversible plutôt que de risquer de
    # casser des données existantes qui utiliseraient déjà 'SCAN_ERROR'.
    pass