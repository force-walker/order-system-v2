"""Add independent authentication users and revocable sessions; no customer changes."""
from alembic import op
import sqlalchemy as sa

revision = "2026091701"
down_revision = "2026062202"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_users",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("auth_users.user_id"), nullable=False),
        sa.Column("access_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("refresh_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("access_expires_at", sa.DateTime(), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])


def downgrade():
    op.drop_table("auth_sessions")
    op.drop_table("auth_users")
