"""Require an explicit profile setup; retain existing chosen usernames."""

import sqlalchemy as sa
from alembic import op

revision = "0003_profile_setup"
down_revision = "0002_public_usernames"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("profile_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE users SET profile_completed = true"
        " WHERE username !~ '^ath_[0-9a-f]{20}$' AND length(trim(display_name)) > 0"
    )


def downgrade() -> None:
    op.drop_column("users", "profile_completed")
