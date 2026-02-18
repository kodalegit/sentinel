"""Add users table and update cases for auth

Revision ID: a1b2c3d4e5f6
Revises: 7af45e7fc361
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7af45e7fc361'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='auditor'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
        sa.CheckConstraint("role IN ('auditor', 'supervisor', 'admin', 'system')", name='ck_user_role'),
    )
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Create system user for historical case attribution
    # Using a fixed UUID so it's consistent across environments
    system_user_id = 'a0000000-0000-0000-0000-000000000001'
    op.execute(f"""
        INSERT INTO users (id, username, email, hashed_password, full_name, role, is_active)
        VALUES (
            '{system_user_id}',
            'system',
            'system@sentinel.local',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G5Q5Q5Q5Q5Q5Q5',
            'System User',
            'system',
            true
        )
    """)

    # Add new FK columns to cases table (nullable initially)
    op.add_column('cases', sa.Column('assigned_to_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('cases', sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Migrate existing cases to use system user
    op.execute(f"""
        UPDATE cases SET created_by_id = '{system_user_id}'
    """)

    # Make created_by_id NOT NULL after migration
    op.alter_column('cases', 'created_by_id', nullable=False)

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_cases_assigned_to', 'cases', 'users',
        ['assigned_to_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_cases_created_by', 'cases', 'users',
        ['created_by_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_cases_assigned', 'cases', ['assigned_to_id'])

    # Drop old string columns from cases
    op.drop_column('cases', 'assigned_to')
    op.drop_column('cases', 'created_by')

    # Update case_notes table
    op.add_column('case_notes', sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Migrate existing notes to use system user
    op.execute(f"""
        UPDATE case_notes SET author_id = '{system_user_id}'
    """)

    # Make author_id NOT NULL after migration
    op.alter_column('case_notes', 'author_id', nullable=False)

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_case_notes_author', 'case_notes', 'users',
        ['author_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_notes_author', 'case_notes', ['author_id'])

    # Drop old string column from case_notes
    op.drop_column('case_notes', 'author')


def downgrade() -> None:
    # Re-add old string columns
    op.add_column('case_notes', sa.Column('author', sa.String(255), nullable=True, server_default='auditor'))
    op.add_column('cases', sa.Column('created_by', sa.String(255), nullable=True, server_default='system'))
    op.add_column('cases', sa.Column('assigned_to', sa.String(255), nullable=True))

    # Migrate data back (using full_name from users)
    op.execute("""
        UPDATE case_notes cn
        SET author = u.full_name
        FROM users u
        WHERE cn.author_id = u.id
    """)
    op.execute("""
        UPDATE cases c
        SET created_by = u.full_name, assigned_to = (
            SELECT u2.full_name FROM users u2 WHERE u2.id = c.assigned_to_id
        )
        FROM users u
        WHERE c.created_by_id = u.id
    """)

    # Make string columns NOT NULL
    op.alter_column('case_notes', 'author', nullable=False)
    op.alter_column('cases', 'created_by', nullable=False)

    # Drop FK constraints and new columns
    op.drop_constraint('fk_case_notes_author', 'case_notes', type_='foreignkey')
    op.drop_index('ix_notes_author', 'case_notes')
    op.drop_column('case_notes', 'author_id')

    op.drop_constraint('fk_cases_assigned_to', 'cases', type_='foreignkey')
    op.drop_constraint('fk_cases_created_by', 'cases', type_='foreignkey')
    op.drop_index('ix_cases_assigned', 'cases')
    op.drop_column('cases', 'assigned_to_id')
    op.drop_column('cases', 'created_by_id')

    # Drop users table
    op.drop_index('ix_users_email', 'users')
    op.drop_index('ix_users_username', 'users')
    op.drop_table('users')
