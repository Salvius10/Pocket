"""Initial schema: every table in ARCHITECTURE.md §5.

The first revision creates the schema from the model metadata as it stood at this commit, so
the models and the database cannot drift before there is anything to migrate. Later revisions
must use explicit op.* calls.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-20
"""

from alembic import op
from core_api import models

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    models.Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    models.Base.metadata.drop_all(bind=op.get_bind())
