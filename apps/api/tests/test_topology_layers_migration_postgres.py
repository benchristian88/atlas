"""Use only an explicitly supplied empty disposable migration database."""
import importlib.util
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(not os.getenv('ATLAS_TEST_LAYERS_MIGRATION_URL'), reason='requires empty disposable migration database')


def test_empty_chain_upgrade_backfill_preservation_and_downgrade(monkeypatch):
    url = os.environ['ATLAS_TEST_LAYERS_MIGRATION_URL']
    engine = create_engine(url)
    assert not inspect(engine).get_table_names(), 'Refusing to modify nonempty database'
    monkeypatch.setenv('DATABASE_URL', url)
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    assert ScriptDirectory.from_config(config).get_heads() == ['20260921_0022']
    command.upgrade(config, '20260921_0020')
    path = Path(__file__).parents[1] / 'migrations/versions/20260921_0021_relationship_topology_layers.py'
    spec = importlib.util.spec_from_file_location('layers_migration', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    expected = {key: layer for layer, keys in migration.BUILTIN_LAYERS.items() for key in keys}
    with engine.begin() as db:
        actual_keys = set(db.scalars(text('SELECT key FROM relationship_types WHERE system_defined')))
        assert actual_keys == set(expected) and len(actual_keys) == 28
        # Preserve names/labels and inactive built-ins. Never infer from English.
        db.execute(text("UPDATE relationship_types SET name='Renamed built-in', active=false WHERE key='proxies'"))
        for key, name, system in [('custom_fibre','Connected by fibre',False), ('provided_by','Provided by',False), ('future_builtin','Unknown system type',True)]:
            db.execute(text('INSERT INTO relationship_types (key,name,source_label,target_label,system_defined) VALUES (:k,:n,:n,:n,:s)'), dict(k=key,n=name,s=system))
        w = db.scalar(text("INSERT INTO workspaces (name,slug) VALUES ('Layers','layers') RETURNING id"))
        c = db.scalar(text("INSERT INTO customers (name,workspace_id) VALUES ('Layers',:w) RETURNING id"), dict(w=w))
        s = db.scalar(text("INSERT INTO sites (name,customer_id) VALUES ('Layers',:c) RETURNING id"), dict(c=c))
        ids = [db.scalar(text("INSERT INTO assets (workspace_id,customer_id,site_id,name,asset_type) VALUES (:w,:c,:s,:n,'server') RETURNING id"), dict(w=w,c=c,s=s,n=n)) for n in ('NPM','PVE1')]
        db.execute(text("INSERT INTO asset_relationships (customer_id,site_id,source_asset_id,target_asset_id,relationship_type) VALUES (:c,:s,:a,:b,'runs_on')"), dict(c=c,s=s,a=ids[0],b=ids[1]))
        before = db.execute(text('SELECT * FROM relationship_types ORDER BY id')).all()
        columns = list(before[0]._mapping)
        relationships = db.execute(text('SELECT * FROM asset_relationships ORDER BY id')).all()
        applicability = db.execute(text('SELECT * FROM relationship_type_applicabilities ORDER BY id')).all()
    command.upgrade(config, 'head')
    with engine.begin() as db:
        assert db.execute(text(f"SELECT {','.join(columns)} FROM relationship_types ORDER BY id")).all() == before
        assert db.execute(text('SELECT * FROM asset_relationships ORDER BY id')).all() == relationships
        assert db.execute(text('SELECT * FROM relationship_type_applicabilities ORDER BY id')).all() == applicability
        actual = dict(db.execute(text('SELECT key,topology_layer FROM relationship_types')).all())
        assert actual == {**expected, 'custom_fibre':'other', 'provided_by':'other', 'future_builtin':'other'}
        assert actual['routes'] == actual['related_to'] == 'other'
        db.execute(text("UPDATE relationship_types SET topology_layer='physical_network' WHERE key='custom_fibre'"))
    command.upgrade(config, 'head')
    with engine.connect() as db:
        assert db.scalar(text("SELECT topology_layer FROM relationship_types WHERE key='custom_fibre'")) == 'physical_network'
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text("UPDATE relationship_types SET topology_layer='arbitrary'"))
    command.downgrade(config, '20260921_0020')
    with engine.begin() as db:
        assert db.execute(text('SELECT * FROM relationship_types ORDER BY id')).all() == before
        assert db.execute(text('SELECT * FROM asset_relationships ORDER BY id')).all() == relationships
        # Even a recognized key marked custom must stay safe, not silently classified.
        db.execute(text("UPDATE relationship_types SET system_defined=false WHERE key='connects_to'"))
    command.upgrade(config, 'head')
    with engine.connect() as db:
        assert db.scalar(text("SELECT topology_layer FROM relationship_types WHERE key='connects_to'")) == 'other'
    engine.dispose()
