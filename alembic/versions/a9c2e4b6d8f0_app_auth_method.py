"""app auth method

How each app signs its own users in, which its scans do not record: they
record auth methods only for the services an app calls. Creating an app
requires it from now on.

Every app in production when this revision was written signed its users in
through the org's identity provider (OAuth), so existing apps are backfilled
with 'oauth'. The column keeps no default afterwards: a new app must declare
its own, rather than read as one that clears without anyone saying so.

Revision ID: a9c2e4b6d8f0
Revises: f1c3e5a7b9d2
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9c2e4b6d8f0'
down_revision: Union[str, Sequence[str], None] = 'f1c3e5a7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# core.enums.AuthMethod as it stands at this revision, like the other
# auth_method columns' CHECKs. The API narrows what an app may declare.
_AUTH_METHODS = (
    "('ntlm', 'kerberos', 'negotiate', 'oauth', 'login_redirect', 'basic', 'bearer', "
    "'api_key', 'other', 'unauthenticated', 'no_response', 'dns_failed', 'unknown')"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('apps', sa.Column('auth_method', sa.String(), nullable=True))
    op.execute("UPDATE apps SET auth_method = 'oauth'")
    op.alter_column('apps', 'auth_method', existing_type=sa.String(), nullable=False)
    op.create_check_constraint('ck_apps_auth_method', 'apps', f"auth_method IN {_AUTH_METHODS}")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_apps_auth_method', 'apps', type_='check')
    op.drop_column('apps', 'auth_method')
