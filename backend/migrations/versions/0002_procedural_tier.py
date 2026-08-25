"""known_environments.generation -> tier (float); clean slate for generated data

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "known_environments",
        "generation",
        type_=sa.Float(),
        postgresql_using="generation::double precision",
    )
    op.alter_column(
        "known_environments",
        "generation",
        new_column_name="tier",
        existing_type=sa.Float(),
    )

    # The naming/tier algorithm changed completely (see
    # docs/design/procedural-environment-generation.md), so no
    # previously-generated (non-base) environment can be trusted. Discard
    # every generated environment and any in-progress state that references
    # one, so each slot's environment progress restarts from just the 4
    # hardcoded base environments. `used` is left alone - this only clears
    # environment progress, not whether the slot has been played.
    op.execute("DELETE FROM known_environments")
    op.execute(
        """
        UPDATE save_slots SET
            current_tab = 'stats',
            time_alive_seconds = 0.0,
            evolution_stage = 'dormant',
            evolution_click_progress = 0,
            selected_environment = NULL,
            hidden_revealed = FALSE,
            hidden_environment_name = NULL,
            hidden_cycle_index = 1,
            hidden_slot_index = 3,
            environment_slot_keys = '["water", "earth", "air", "fire"]'::jsonb,
            awaiting_hidden_relock_choice = FALSE
        """
    )
    op.execute("DELETE FROM environment_time_seconds")
    op.execute(
        """
        INSERT INTO environment_time_seconds (slot_id, environment_key, seconds)
        SELECT id, key, 0.0
        FROM save_slots, unnest(ARRAY['water', 'earth', 'air', 'fire']) AS key
        """
    )


def downgrade() -> None:
    op.alter_column(
        "known_environments",
        "tier",
        new_column_name="generation",
        existing_type=sa.Float(),
    )
    op.alter_column(
        "known_environments",
        "generation",
        type_=sa.Integer(),
        postgresql_using="generation::integer",
    )
