"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "save_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("current_tab", sa.String(length=16), nullable=False),
        sa.Column("time_alive_seconds", sa.Float(), nullable=False),
        sa.Column("evolution_stage", sa.String(length=16), nullable=False),
        sa.Column("evolution_click_progress", sa.Integer(), nullable=False),
        sa.Column("selected_environment", sa.String(length=64), nullable=True),
        sa.Column("hidden_revealed", sa.Boolean(), nullable=False),
        sa.Column("hidden_environment_name", sa.String(length=64), nullable=True),
        sa.Column("hidden_cycle_index", sa.Integer(), nullable=False),
        sa.Column("hidden_slot_index", sa.Integer(), nullable=False),
        sa.Column("environment_slot_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("awaiting_hidden_relock_choice", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "current_tab IN ('stats', 'environment')", name="ck_save_slots_current_tab"
        ),
        sa.CheckConstraint(
            "evolution_stage IN ('dormant', 'cracked', 'hatching', 'petawaru')",
            name="ck_save_slots_evolution_stage",
        ),
        sa.CheckConstraint(
            "evolution_click_progress >= 0 AND evolution_click_progress <= 2",
            name="ck_save_slots_evolution_click_progress",
        ),
        sa.CheckConstraint("hidden_cycle_index >= 1", name="ck_save_slots_hidden_cycle_index"),
        sa.CheckConstraint(
            "hidden_slot_index >= 0 AND hidden_slot_index <= 3",
            name="ck_save_slots_hidden_slot_index",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "environment_time_seconds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("environment_key", sa.String(length=64), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["slot_id"], ["save_slots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "environment_key", name="uq_env_time_slot_key"),
    )

    op.create_table(
        "known_environments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("traits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("parents", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["slot_id"], ["save_slots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "name", name="uq_known_env_slot_name"),
    )


def downgrade() -> None:
    op.drop_table("known_environments")
    op.drop_table("environment_time_seconds")
    op.drop_table("save_slots")
