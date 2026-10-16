#!/usr/bin/env python3
"""Пути плагина из окружения: папка репозиториев, индекс системы, сервисы."""
import os
import sys
from pathlib import Path
from typing import Mapping, Optional

INDEX_NAMES = ("bctc.md", "system_tech.md")


def _absolute(raw: str, env: Mapping[str, str], cwd: Path) -> Path:
    env_home = env.get("HOME")
    if env_home and (raw == "~" or raw.startswith("~/")):
        raw = env_home + raw[1:]
    path = Path(raw).expanduser()
    return path if path.is_absolute() else cwd / path


def resolve_paths(env: Optional[Mapping[str, str]] = None, cwd: Optional[Path] = None) -> dict:
    env = os.environ if env is None else env
    cwd = Path.cwd() if cwd is None else Path(cwd).absolute()
    home = env.get("HOME") or str(Path.home())
    root = _absolute(env.get("SA_REPOS_ROOT") or f"{home}/repos", env, cwd)
    docs_raw = env.get("SA_SYSTEM_DOCS")
    docs = _absolute(docs_raw, env, cwd) if docs_raw else root / "system-docs"
    index_dir = docs / "docs"
    exists = root.is_dir()
    services = []
    if exists:
        docs_resolved = docs.resolve()
        services = sorted(
            p.name for p in root.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.resolve() != docs_resolved
        )
    return {
        "tasks_dir": str(cwd / "tasks"),
        "repos_root": str(root),
        "repos_exists": exists,
        "system_docs": str(docs),
        "index_dir": str(index_dir),
        "index_files": [n for n in INDEX_NAMES if (index_dir / n).is_file()],
        "services": services,
    }


def format_paths(paths: dict) -> str:
    return "\n".join([
        f"tasks_dir: {paths['tasks_dir']}",
        f"repos_root: {paths['repos_root']} ({'есть' if paths['repos_exists'] else 'нет'})",
        f"index_dir: {paths['index_dir']}",
        f"index_files: {', '.join(paths['index_files']) or 'нет'}",
        f"services: {', '.join(paths['services']) or 'нет'}",
    ])


def main(argv: list) -> int:
    if argv:
        print("usage: sa_paths.py", file=sys.stderr)
        return 2
    print(format_paths(resolve_paths()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
