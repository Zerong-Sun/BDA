from __future__ import annotations

import argparse
import getpass

from backend_v2.app.core.database import session_scope
from backend_v2.app.identity.service import bootstrap_admin


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first BDA v2 administrator")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password")
    args = parser.parse_args()
    password = args.password or getpass.getpass("Admin password: ")
    with session_scope() as session:
        user = bootstrap_admin(session, username=args.username, password=password)
        print(f"Administrator ready: {user.id} ({user.username})")


if __name__ == "__main__":
    main()
