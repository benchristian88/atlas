"""Exercise the actual old fields on an explicitly empty disposable database."""
import importlib.util
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.skipif(not os.getenv('ATLAS_TEST_POSITIONS_MIGRATION_URL'), reason='requires empty disposable migration database')


def test_fresh_populated_upgrade_downgrade_reupgrade(monkeypatch):
    url = os.environ['ATLAS_TEST_POSITIONS_MIGRATION_URL']
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), 'Refusing to modify nonempty database'
    monkeypatch.setenv('DATABASE_URL', url)
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    assert ScriptDirectory.from_config(config).get_heads() == ['20261004_0024']
    command.upgrade(config, 'head')  # Entire fresh chain first.
    command.downgrade(config, '20260921_0022')
    path = Path(__file__).parents[1] / 'migrations/versions/20260921_0023_managed_topology_positions.py'
    spec = importlib.util.spec_from_file_location('positions_migration', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    roles = [key for key, _ in migration.SEEDS] + ['automatic']
    with engine.begin() as db:
        for role in roles:
            db.execute(text('INSERT INTO asset_types (key,name,topology_role) VALUES (:role,:role,:role)'), dict(role=role))
        # Simulate a customized old database without losing that administrator intent.
        checks = inspect(db).get_check_constraints('asset_types')
        constraint = next(c['name'] for c in checks if 'topology_role' in c['sqltext'])
        db.execute(text(f'ALTER TABLE asset_types DROP CONSTRAINT "{constraint}"'))
        db.execute(text("INSERT INTO asset_types (key,name,topology_role) VALUES ('legacy','Legacy','custom_legacy')"))
        db.execute(text("UPDATE relationship_types SET topology_layer='data_resilience' WHERE key='connects_to'"))
        w = db.scalar(text("INSERT INTO workspaces (name,slug) VALUES ('Positions','positions') RETURNING id"))
        c = db.scalar(text("INSERT INTO customers (name,workspace_id) VALUES ('Positions',:w) RETURNING id"), dict(w=w))
        s = db.scalar(text("INSERT INTO sites (name,customer_id) VALUES ('Positions',:c) RETURNING id"), dict(c=c))
        db.execute(text("INSERT INTO assets (workspace_id,customer_id,site_id,name,asset_type) VALUES (:w,:c,:s,'Untouched','server')"), dict(w=w,c=c,s=s))
        snapshot = db.execute(text('SELECT * FROM asset_types ORDER BY id')).mappings().all()
        assets = db.execute(text('SELECT * FROM assets ORDER BY id')).all()
        classes = dict(db.execute(text('SELECT id,topology_layer FROM relationship_types')).all())
    command.upgrade(config, 'head')
    with engine.connect() as db:
        positions = db.execute(text('SELECT key,name,sort_order FROM topology_positions ORDER BY sort_order')).all()
        assert [(p.key,p.name) for p in positions[:9]] == migration.SEEDS
        assert len({p.sort_order for p in positions}) == len(positions)
        assert 'automatic' not in {p.key for p in positions}
        for before in snapshot:
            after = db.execute(text('SELECT a.*,p.key AS position_key FROM asset_types a LEFT JOIN topology_positions p ON p.id=a.topology_position_id WHERE a.id=:id'), dict(id=before['id'])).mappings().one()
            assert after['position_key'] == (None if before['topology_role'] == 'automatic' else before['topology_role'])
            assert all(after[key] == value for key,value in before.items() if key != 'topology_role')
        assert db.execute(text('SELECT * FROM assets ORDER BY id')).all() == assets
        assert dict(db.execute(text('SELECT id,topology_class FROM relationship_types')).all()) == classes
        assert 'topology_role' not in {c['name'] for c in inspect(db).get_columns('asset_types')}
    command.downgrade(config, '20260921_0022')
    with engine.connect() as db:
        assert db.execute(text('SELECT * FROM asset_types ORDER BY id')).mappings().all() == snapshot
        assert dict(db.execute(text('SELECT id,topology_layer FROM relationship_types')).all()) == classes
        assert db.execute(text('SELECT * FROM assets ORDER BY id')).all() == assets
    command.upgrade(config, 'head')
    with engine.begin() as db:
        assert db.execute(text('SELECT key,name,sort_order FROM topology_positions ORDER BY sort_order')).all() == positions
        db.execute(text("INSERT INTO topology_positions (key,name,sort_order) VALUES (:key,'Long custom',100)"), {'key': 'a' * 40})
        db.execute(text("UPDATE asset_types SET topology_position_id=(SELECT id FROM topology_positions WHERE name='Long custom') WHERE key='legacy'"))
    with pytest.raises(RuntimeError, match='32-character'):
        command.downgrade(config, '20260921_0022')
    with engine.connect() as db:
        assert db.scalar(text('SELECT version_num FROM alembic_version')) == '20261004_0024'
        assert db.scalar(text("SELECT p.key FROM asset_types a JOIN topology_positions p ON p.id=a.topology_position_id WHERE a.key='legacy'")) == 'a' * 40
    engine.dispose()
