"""add admin and banned

Revision ID: 6e003647d5f7
Revises: c2aca77d5c96
Create Date: 2021-02-24 22:08:30.689623

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e003647d5f7'
down_revision = 'c2aca77d5c96'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('admin', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('banned', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'banned')
    op.drop_column('user', 'admin')
    # ### end Alembic commands ###