"""Print the number of active users as a single integer on the last line.

Used by termux/lib-debian-backend.sh:seed_admin() to detect a database that was
wiped/rebuilt (e.g. by scripts/temp_clean_database.py) after the phone-side
`.admin_seeded` marker was written: the marker proves a past seed run, not that
a login still exists. This script never prints credentials.
"""

import sys
from pathlib import Path

# Allow running as `python scripts/count_active_users.py` from any directory:
# Python only puts the script's own folder (backend/scripts) on sys.path, so
# point at the backend root to make `app` importable without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy import func, select


def main() -> None:
    try:
        with SessionLocal() as session:
            count = session.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
        print(int(count or 0))
    except Exception:
        print(0)


if __name__ == "__main__":
    main()
