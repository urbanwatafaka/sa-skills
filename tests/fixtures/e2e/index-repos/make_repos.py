#!/usr/bin/env python3
"""E2E /sa-index-docs: копирует shop-* в <target> и делает git-репозитории; --change — новый маршрут в shop-api."""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVICES = ("shop-api", "shop-legacy", "shop-front")
NEW_ROUTE = "Route::delete('/api/orders/{id}', [OrderController::class, 'destroy']);\n"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=SA", "-c", "user.email=sa@example.com", *args], check=True)


def main(argv: list[str]) -> int:
    if not argv or len(argv) > 2 or (len(argv) == 2 and argv[1] != "--change"):
        print("usage: make_repos.py <target> [--change]", file=sys.stderr)
        return 2
    target = Path(argv[0]).absolute()
    if len(argv) == 2:
        repo = target / "shop-api"
        routes = repo / "routes" / "api.php"
        routes.write_text(routes.read_text(encoding="utf-8") + NEW_ROUTE, encoding="utf-8")
        git(repo, "commit", "-qam", "delete order route")
        return 0
    for name in SERVICES:
        repo = target / name
        shutil.copytree(HERE / name, repo)
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
