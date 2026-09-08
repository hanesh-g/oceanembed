"""add_ocean_tables

Revision ID: 0001
Revises: 
Create Date: 2026-09-07 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Manually patch migration: add PostGIS extension + spatial index
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis;')

    op.create_table('model_runs',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('week_label', sa.String(length=20), nullable=False),
    sa.Column('run_date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('model_version', sa.String(length=64), nullable=False),
    sa.Column('gate_status', sa.String(length=8), nullable=False),
    sa.Column('gate_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_runs_week_label'), 'model_runs', ['week_label'], unique=False)

    op.create_table('argo_profiles',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('platform_id', sa.String(length=32), nullable=False),
    sa.Column('profile_date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('lat', sa.Float(), nullable=False),
    sa.Column('lon', sa.Float(), nullable=False),
    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=False),
    sa.Column('depth_levels', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('temp_values', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('sal_values', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_argo_profiles_platform_id'), 'argo_profiles', ['platform_id'], unique=False)
    # create_index using gist is created via op.create_index
    op.create_index('argo_geom_gist_idx', 'argo_profiles', ['geom'], unique=False, postgresql_using='gist')


def downgrade():
    op.drop_index('argo_geom_gist_idx', table_name='argo_profiles', postgresql_using='gist')
    op.drop_index(op.f('ix_argo_profiles_platform_id'), table_name='argo_profiles')
    op.drop_table('argo_profiles')
    op.drop_index(op.f('ix_model_runs_week_label'), table_name='model_runs')
    op.drop_table('model_runs')
    op.execute('DROP EXTENSION IF EXISTS postgis;')
