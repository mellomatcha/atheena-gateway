"""Separate public handles from private profile names."""

import sqlalchemy as sa
from alembic import op

revision = "0002_public_usernames"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.Text(), nullable=True))
    op.execute("UPDATE users SET username = 'ath_' || substr(md5(id::text), 1, 20)")
    op.alter_column(
        "users",
        "username",
        nullable=False,
        server_default=sa.text("'ath_' || substr(md5(random()::text), 1, 20)"),
    )
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_check_constraint("username_format", "users", "username ~ '^[a-z][a-z0-9_]{2,23}$'")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_username_format"), "users", type_="check")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "username")
