"""新增业务表：配置项、密钥轮换策略与密钥版本。

Revision ID: 0002_business_tables
Revises: 0001_initial
Create Date: 2026-09-23
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# 本迁移的版本号，下游 0003 及以后迁移以此为 down_revision
revision: str = '0002_business_tables'
# 上一版本，承接 0001_initial
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Alembic 自动生成开始，按模型元数据建立业务表 ###
    # 配置项表：按环境存储配置键值，同一键在不同环境唯一
    op.create_table('config_items',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('config_key', sa.String(length=256), nullable=False),
    sa.Column('env', sa.String(length=32), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('config_key', 'env', name='uq_config_key_env')
    )
    op.create_index(op.f('ix_config_items_config_key'), 'config_items', ['config_key'], unique=False)
    op.create_index(op.f('ix_config_items_env'), 'config_items', ['env'], unique=False)
    op.create_index(op.f('ix_config_items_status'), 'config_items', ['status'], unique=False)
    # 密钥轮换策略表：定义密钥的轮换周期与时间点
    op.create_table('rotation_policies',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('policy_name', sa.String(length=128), nullable=False),
    sa.Column('secret_name', sa.String(length=256), nullable=False),
    sa.Column('interval_days', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('last_rotated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_rotation_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rotation_policies_policy_name'), 'rotation_policies', ['policy_name'], unique=True)
    op.create_index(op.f('ix_rotation_policies_secret_name'), 'rotation_policies', ['secret_name'], unique=False)
    op.create_index(op.f('ix_rotation_policies_status'), 'rotation_policies', ['status'], unique=False)
    # 密钥版本表：保存各密钥每次轮换后的密文版本，(密钥名, 版本号) 唯一
    op.create_table('secret_versions',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('secret_name', sa.String(length=256), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('ciphertext', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('secret_name', 'version', name='uq_secret_name_version')
    )
    op.create_index(op.f('ix_secret_versions_secret_name'), 'secret_versions', ['secret_name'], unique=False)
    op.create_index(op.f('ix_secret_versions_status'), 'secret_versions', ['status'], unique=False)
    # ### Alembic 自动生成结束 ###


def downgrade() -> None:
    # ### Alembic 自动生成开始，按逆序删除业务表与索引 ###
    op.drop_index(op.f('ix_secret_versions_status'), table_name='secret_versions')
    op.drop_index(op.f('ix_secret_versions_secret_name'), table_name='secret_versions')
    op.drop_table('secret_versions')
    op.drop_index(op.f('ix_rotation_policies_status'), table_name='rotation_policies')
    op.drop_index(op.f('ix_rotation_policies_secret_name'), table_name='rotation_policies')
    op.drop_index(op.f('ix_rotation_policies_policy_name'), table_name='rotation_policies')
    op.drop_table('rotation_policies')
    op.drop_index(op.f('ix_config_items_status'), table_name='config_items')
    op.drop_index(op.f('ix_config_items_env'), table_name='config_items')
    op.drop_index(op.f('ix_config_items_config_key'), table_name='config_items')
    op.drop_table('config_items')
    # ### Alembic 自动生成结束 ###
