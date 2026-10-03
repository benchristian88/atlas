"""Only an explicitly supplied empty disposable database may be migrated."""
import importlib.util
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark=pytest.mark.skipif(not os.getenv('ATLAS_TEST_ROLES_MIGRATION_URL'),reason='requires empty disposable migration database')


def test_upgrade_preserves_knowledge_and_defaults_only_recognized_builtins(monkeypatch):
    url=os.environ['ATLAS_TEST_ROLES_MIGRATION_URL'];engine=create_engine(url)
    assert not inspect(engine).get_table_names(),'Refusing to modify nonempty database'
    monkeypatch.setenv('DATABASE_URL',url)
    config=Config(str(Path(__file__).parents[1]/'alembic.ini'))
    assert ScriptDirectory.from_config(config).get_heads()==['20261004_0024']
    command.upgrade(config,'20260921_0021')
    path=Path(__file__).parents[1]/'migrations/versions/20260921_0022_asset_type_topology_roles.py'
    spec=importlib.util.spec_from_file_location('roles_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    expected={key:role for role,keys in migration.BUILTIN_ROLES.items() for key in keys}
    with engine.begin() as db:
        assert set(db.scalars(text('SELECT key FROM asset_types WHERE system_defined')))==set(expected)
        db.execute(text("UPDATE asset_types SET name='Renamed built-in',active=false,default_icon_url='https://example.test/image.png' WHERE key='firewall'"))
        db.execute(text("UPDATE asset_types SET system_defined=false WHERE key='router'"));expected['router']='automatic'
        for key,system in [('custom',False),('future_builtin',True)]:
            db.execute(text('INSERT INTO asset_types (key,name,system_defined) VALUES (:k,:k,:s)'),dict(k=key,s=system));expected[key]='automatic'
        w=db.scalar(text("INSERT INTO workspaces (name,slug) VALUES ('Roles','roles') RETURNING id"))
        c=db.scalar(text("INSERT INTO customers (name,workspace_id) VALUES ('Roles',:w) RETURNING id"),dict(w=w))
        site=db.scalar(text("INSERT INTO sites (name,customer_id) VALUES ('Roles',:c) RETURNING id"),dict(c=c))
        ids=[db.scalar(text("INSERT INTO assets (workspace_id,customer_id,site_id,name,asset_type) VALUES (:w,:c,:s,:n,'server') RETURNING id"),dict(w=w,c=c,s=site,n=n)) for n in ('One','Two')]
        db.execute(text("INSERT INTO asset_relationships (customer_id,site_id,source_asset_id,target_asset_id,relationship_type) VALUES (:c,:s,:a,:b,'runs_on')"),dict(c=c,s=site,a=ids[0],b=ids[1]))
        snapshots={table:db.execute(text(f'SELECT * FROM {table} ORDER BY id')).all() for table in ('asset_types','assets','asset_categories','asset_relationships','relationship_types')}
        columns=list(snapshots['asset_types'][0]._mapping)
    command.upgrade(config,'20260921_0022')
    with engine.begin() as db:
        for table,before in snapshots.items():
            fields=','.join(columns) if table=='asset_types' else '*'
            assert db.execute(text(f'SELECT {fields} FROM {table} ORDER BY id')).all()==before
        assert dict(db.execute(text('SELECT key,topology_role FROM asset_types')).all())==expected
        db.execute(text("UPDATE asset_types SET topology_role='external' WHERE key='custom'"))
    command.upgrade(config,'20260921_0022')
    with engine.connect() as db:
        assert db.scalar(text("SELECT topology_role FROM asset_types WHERE key='custom'"))=='external'
    for value in ("'arbitrary'",'NULL'):
        with pytest.raises(IntegrityError),engine.begin() as db:
            db.execute(text(f'UPDATE asset_types SET topology_role={value}'))
    command.downgrade(config,'20260921_0021')
    with engine.connect() as db:
        for table,before in snapshots.items():
            assert db.execute(text(f'SELECT * FROM {table} ORDER BY id')).all()==before
    command.upgrade(config,'20260921_0022')
    engine.dispose()
