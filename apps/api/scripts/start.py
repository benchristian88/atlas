"""Bounded database readiness retry, migrations, definitions, then API exec."""
import os
import subprocess
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.auth import _secret_key
from app.database import engine
from app.release import build_metadata
from scripts.seed_system import main as seed_system


def main() -> None:
    _secret_key()
    build_metadata()
    for attempt in range(30):
        try:
            with engine.connect() as db:
                db.execute(text("SELECT 1"))
            break
        except OperationalError:
            if attempt == 29:
                raise SystemExit("Database unavailable after readiness retries") from None
            time.sleep(min(1 + attempt, 5))
    if subprocess.run(["alembic", "upgrade", "head"]).returncode:
        raise SystemExit("Atlas migration failed")
    seed_system()
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", os.getenv("ATLAS_API_HOST", "0.0.0.0"), "--port", "8000"])


if __name__ == "__main__":
    main()
