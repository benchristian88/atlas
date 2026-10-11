"""Separate OS processes cannot claim overlapping executable ownership."""
import json
import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable PostgreSQL")

CHILD = '''import json,sys
from sqlalchemy import create_engine,text
from sqlalchemy.exc import IntegrityError
request=json.load(sys.stdin)
engine=create_engine(request.pop("url"),hide_parameters=True)
try:
 with engine.begin() as db:
  db.execute(text("INSERT INTO discovery_runs(integration_id,data_source_id,customer_id,site_id,status,started_at,execution_provenance) VALUES (:integration,:source,:customer,:site,'pending',now(),CAST(:provenance AS jsonb))"),request)
 print("created")
except IntegrityError: print("overlap")
finally: engine.dispose()
'''


def test_cross_process_manual_schedule_race_and_cancel_cleanup_ownership():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    records = {}
    with engine.begin() as db:
        records["workspace"] = db.scalar(text("INSERT INTO workspaces(name,slug) VALUES ('I3 concurrency',:slug) RETURNING id"), {"slug": uuid.uuid4().hex})
        records["customer"] = db.scalar(text("INSERT INTO customers(name,workspace_id) VALUES ('I3 concurrency',:workspace) RETURNING id"), records)
        records["site"] = db.scalar(text("INSERT INTO sites(name,customer_id) VALUES ('I3 concurrency',:customer) RETURNING id"), records)
        records["source"] = db.scalar(text("INSERT INTO data_sources(customer_id,site_id,name,source_type) VALUES (:customer,:site,'I3 concurrency','connector') RETURNING id"), records)
        records["integration"] = db.scalar(text("INSERT INTO integrations(customer_id,site_id,name,plugin_id,base_url,username_or_token_id,secret_reference,data_source_id) VALUES (:customer,:site,'I3 concurrency','i3-concurrency','','','',:source) RETURNING id"), records)
    def processes():
        children = []
        for trigger in ["manual", "schedule"]:
            child = subprocess.Popen([sys.executable, "-c", CHILD], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            payload = {**{key: str(value) for key, value in records.items() if key != "workspace"},
                "url": engine.url.render_as_string(hide_password=False), "provenance": json.dumps({"connector_id": "i3-concurrency", "trigger": trigger})}
            child.stdin.write(json.dumps(payload).encode()); child.stdin.close(); children.append(child)
        results = []
        for child in children:
            child.wait(timeout=10); assert child.returncode == 0; results.append(child.stdout.read().decode().strip())
        return sorted(results)
    try:
        assert processes() == ["created", "overlap"]
        with engine.begin() as db:
            db.execute(text("UPDATE discovery_runs SET status='cancelled' WHERE integration_id=:integration"), records)
        assert processes() == ["overlap", "overlap"]
    finally:
        # Only inert test claims exist: no receipts/evidence/source job executed.
        with engine.begin() as db:
            for table, key, expression in [("discovery_runs", "integration", "integration_id"), ("integrations", "integration", "id"),
                    ("data_sources", "source", "id"), ("sites", "site", "id"), ("customers", "customer", "id"), ("workspaces", "workspace", "id")]:
                db.execute(text(f"DELETE FROM {table} WHERE {expression}=:id"), {"id": records[key]})
        engine.dispose()
