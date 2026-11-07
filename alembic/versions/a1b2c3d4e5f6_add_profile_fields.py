"""add profile fields (username, bio, image_file)

Revision ID: a1b2c3d4e5f6
Revises: 64561b300e8c
Create Date: 2026-11-06 12:00:00

Existing users have no username, so this migration is done in three steps:
add the column as nullable -> fill it for existing rows -> make it NOT NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '64561b300e8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(length=300), nullable=True))
    op.add_column('users', sa.Column('image_file', sa.String(), nullable=True))

    # Emails are now stored lowercase.
    op.execute("UPDATE users SET email = lower(email)")
    # Username for existing rows: the part of the email before "@" (letters/digits/_ only,
    # max 20 chars) plus "_<id>". The id suffix guarantees every value is unique.
    op.execute(
        "UPDATE users SET username = "
        "COALESCE(NULLIF(left(regexp_replace(split_part(email, '@', 1), '[^A-Za-z0-9_]', '', 'g'), 20), ''), 'user')"
        " || '_' || id"
    )
    op.alter_column('users', 'username', nullable=False)
    op.create_index('uq_users_username_lower', 'users', [sa.text('lower(username)')], unique=True)


def downgrade() -> None:
    op.drop_index('uq_users_username_lower', table_name='users')
    op.drop_column('users', 'image_file')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'username')
