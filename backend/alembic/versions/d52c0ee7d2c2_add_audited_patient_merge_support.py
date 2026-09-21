"""add audited patient merge support

Revision ID: d52c0ee7d2c2
Revises: 7e533bbb8af8
Create Date: 2026-08-21 14:50:47.664387
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd52c0ee7d2c2'
down_revision: Union[str, Sequence[str], None] = '7e533bbb8af8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('patients') as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column('merged_into_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_patients_is_active', ['is_active'], unique=False)
        batch_op.create_index('ix_patients_merged_into_id', ['merged_into_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_patients_merged_into_id_patients',
            'patients',
            ['merged_into_id'],
            ['id'],
            ondelete='RESTRICT',
        )


def downgrade() -> None:
    with op.batch_alter_table('patients') as batch_op:
        batch_op.drop_constraint('fk_patients_merged_into_id_patients', type_='foreignkey')
        batch_op.drop_index('ix_patients_merged_into_id')
        batch_op.drop_index('ix_patients_is_active')
        batch_op.drop_column('merged_into_id')
        batch_op.drop_column('is_active')
