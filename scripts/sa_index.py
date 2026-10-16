#!/usr/bin/env python3
"""Индекс docs/ сервиса: схемы таблиц, проверка, карта репозитория, изменённые файлы, отметка индексации."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from sa_artifacts import ArtifactError, parse_tables
from sa_state import _plugin_version, write_atomic

DOCS = "docs"
STAMP_FILE = ".sa-index.json"
SCHEMAS = {
    "tech.md": {
        "API": ["Метод", "Путь", "Назначение", "Код"],
        "Исходящие вызовы": ["Куда", "Метод или топик", "Назначение", "Код"],
        "Сообщения": ["Брокер", "Топик или очередь", "Направление", "Когда", "Код"],
        "Фоновые задачи": ["Задача", "Запуск", "Что делает", "Код"],
    },
    "DB.md": {
        "Таблицы": ["Таблица", "Назначение", "Ключевые поля", "Код"],
        "Связи": ["Из", "В", "Тип", "Код"],
    },
    "bctc.md": {
        "Сценарии": ["Домен", "Сценарий", "Роль сервиса", "Точки входа", "Код"],
    },
}
DIRECTIONS = ("публикует", "читает")
EMPTY = "нет"
DASH = "—"
CODE_REF_RE = re.compile(r"([^\s,:][^,:]*):(\d+)")
EXCLUDED_DIRS = {".git", "vendor", "node_modules", "bin", "obj", "dist", "build", ".idea", ".vscode"}
SOURCE_EXTS = {
    ".php", ".phtml", ".tpl", ".twig", ".cs", ".cshtml", ".razor", ".js", ".jsx", ".ts", ".tsx",
    ".vue", ".py", ".go", ".java", ".kt", ".rb", ".sql",
}
HINT_NAMES = {
    "routes", "controllers", "migrations", "jobs", "console", "consumers", "listeners", "kafka",
    "templates", "views", "pages", "api", "cron", "models", "entities", "handlers", "workers",
}
DOTNET_EXTS = {".cs", ".cshtml", ".razor"}
SPLIT_THRESHOLD = 1500


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def read_doc(repo: Path, name: str) -> dict[str, list[dict[str, str]]]:
    """Строки таблиц файла индекса по разделам; ArtifactError, если структура не по схеме."""
    path = repo / DOCS / name
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ArtifactError(f"{DOCS}/{name}: не читается ({exc})") from exc
    if not text.startswith("# "):
        raise ArtifactError(f"{DOCS}/{name}: первая строка должна быть заголовком «# <сервис>»")
    sections = _sections(text)
    result = {}
    for section, columns in SCHEMAS[name].items():
        if section not in sections:
            raise ArtifactError(f"{DOCS}/{name}: нет раздела «## {section}»")
        try:
            tables = parse_tables(sections[section])
        except ArtifactError as exc:
            raise ArtifactError(f"{DOCS}/{name}#{section}: {exc}") from exc
        if len(tables) != 1 or tables[0].header != columns:
            raise ArtifactError(f"{DOCS}/{name}#{section}: ожидается одна таблица | {' | '.join(columns)} |")
        result[section] = tables[0].rows
    return result


def code_refs(cell: str) -> list[tuple[str, int]] | None:
    refs = []
    for part in (p.strip() for p in cell.split(",")):
        match = CODE_REF_RE.fullmatch(part)
        if match is None:
            return None
        refs.append((match.group(1), int(match.group(2))))
    return refs


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _ref_errors(repo: Path, where: str, cell: str) -> list[str]:
    refs = code_refs(cell)
    if refs is None:
        return [f"{where}: «Код» — «путь:строка» через «, », а не «{cell}»"]
    errors = []
    for rel, line in refs:
        rel_path = Path(rel)
        target = repo / rel_path
        if rel_path.is_absolute() or ".." in rel_path.parts or not target.is_file():
            errors.append(f"{where}: нет файла {rel}")
        elif not 1 <= line <= _line_count(target):
            errors.append(f"{where}: в {rel} нет строки {line}")
    return errors


def _row_errors(repo: Path, where: str, row: dict[str, str], columns: list[str]) -> list[str]:
    if row[columns[0]] == EMPTY:
        if any(row[c] != DASH for c in columns[1:]):
            return [f"{where}: в строке «нет» остальные ячейки — «—»"]
        return []
    errors = [f"{where}: пустая ячейка «{c}»" for c in columns if not row[c]]
    direction = row.get("Направление")
    if direction and direction not in DIRECTIONS and not direction.startswith("?"):
        errors.append(f"{where}: «Направление» — {' или '.join(DIRECTIONS)}, а не «{direction}»")
    if row["Код"]:
        errors += _ref_errors(repo, where, row["Код"])
    return errors


def check_repo(repo: Path, names: list[str] | None = None) -> list[str]:
    errors = []
    for name in names or list(SCHEMAS):
        if not (repo / DOCS / name).is_file():
            errors.append(f"нет файла {DOCS}/{name}")
            continue
        try:
            doc = read_doc(repo, name)
        except ArtifactError as exc:
            errors.append(str(exc))
            continue
        for section, rows in doc.items():
            columns = SCHEMAS[name][section]
            for number, row in enumerate(rows, start=1):
                errors += _row_errors(repo, f"{DOCS}/{name}#{section}, строка {number}", row, columns)
    return errors


def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotepath=off", *args],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _skipped(rel: Path) -> bool:
    return (bool(rel.parts) and rel.parts[0] == DOCS) or any(p in EXCLUDED_DIRS for p in rel.parts)


def _walk(repo: Path):
    for root, dirs, names in os.walk(repo):
        rel_root = Path(root).relative_to(repo)
        dirs[:] = sorted(d for d in dirs if not _skipped(rel_root / d))
        yield rel_root, dirs, names


def detect_stack(repo: Path, sources: list[Path]) -> list[str]:
    stack = set()
    folders = [repo] + [p for p in sorted(repo.iterdir()) if p.is_dir() and not _skipped(Path(p.name))]
    for folder in folders:
        composer = folder / "composer.json"
        if (folder / "artisan").is_file() or (
            composer.is_file() and "laravel/framework" in composer.read_text(encoding="utf-8", errors="replace")
        ):
            stack.add("laravel")
        package = folder / "package.json"
        if package.is_file():
            stack.add("react" if '"react"' in package.read_text(encoding="utf-8", errors="replace") else "node")
    if any(s.suffix.lower() in DOTNET_EXTS for s in sources) or any(
        Path(n).suffix.lower() in (".csproj", ".sln") for _, _, names in _walk(repo) for n in names
    ):
        stack.add("dotnet")
    if "laravel" not in stack and any(s.suffix.lower() == ".php" for s in sources):
        stack.add("php")
    return sorted(stack)


def load_stamp(repo: Path) -> dict:
    try:
        data = json.loads((repo / DOCS / STAMP_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def doc_hashes(repo: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((repo / DOCS / name).read_bytes()).hexdigest()
        for name in SCHEMAS if (repo / DOCS / name).is_file()
    }


def human_edited(repo: Path, stamp_data: dict) -> list[str]:
    recorded = stamp_data.get("files") or {}
    return [name for name, digest in doc_hashes(repo).items() if recorded.get(name) != digest]


def index_mode(repo: Path, stamp_data: dict) -> tuple[str, str]:
    if _git(repo, "rev-parse", "HEAD") is None:
        return "full", "не git-репозиторий или нет коммитов"
    sha = stamp_data.get("sha")
    if not sha:
        return "full", "индексации ещё не было"
    if _git(repo, "cat-file", "-e", f"{sha}^{{commit}}") is None:
        return "full", f"коммит {sha[:7]} не найден"
    return "incremental", f"с {sha[:7]} от {stamp_data.get('indexed', '?')}"


def branch_status(repo: Path) -> str:
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return "нет"
    name = branch.strip()
    counts = _git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if counts is None:
        return f"{name} (без upstream)"
    behind = int(counts.split()[1])
    if behind:
        return f"{name}, ОТСТАЁТ на {behind} от upstream (по последнему fetch)"
    return f"{name}, не отстаёт от upstream"


def survey(repo: Path) -> dict:
    sources: list[Path] = []
    hints: list[str] = []
    for rel_root, dirs, names in _walk(repo):
        sources += [rel_root / n for n in names if Path(n).suffix.lower() in SOURCE_EXTS]
        hints += [f"{(rel_root / d).as_posix()}/" for d in dirs if d.lower() in HINT_NAMES]
    stamp_data = load_stamp(repo)
    mode, reason = index_mode(repo, stamp_data)
    edited = human_edited(repo, stamp_data)
    docs = {
        name: "нет" if not (repo / DOCS / name).is_file() else "правка человека" if name in edited else "есть"
        for name in SCHEMAS
    }
    return {
        "repo": str(repo), "stack": detect_stack(repo, sources), "sources": len(sources),
        "split": len(sources) > SPLIT_THRESHOLD, "mode": mode, "reason": reason,
        "branch": branch_status(repo), "hints": sorted(hints)[:30], "docs": docs,
    }


def _listing(items: list[str]) -> list[str]:
    return [f"  {item}" for item in items] or ["  нет"]


def format_survey(data: dict) -> str:
    split = f"да (больше {SPLIT_THRESHOLD} исходников)" if data["split"] else "нет"
    docs = "; ".join(f"{name} — {status}" for name, status in data["docs"].items())
    return "\n".join([
        f"repo: {data['repo']}",
        f"stack: {', '.join(data['stack']) or 'не определён'}",
        f"sources: {data['sources']}",
        f"split: {split}",
        f"mode: {data['mode']} ({data['reason']})",
        f"branch: {data['branch']}",
        f"docs: {docs}",
        "hints:", *_listing(data["hints"]),
    ])


def changed(repo: Path) -> dict:
    stamp_data = load_stamp(repo)
    mode, reason = index_mode(repo, stamp_data)
    result = {"mode": mode, "reason": reason, "files": [], "rows": []}
    if mode == "full":
        return result
    diff = _git(repo, "diff", "--name-only", "--no-renames", stamp_data["sha"])
    if diff is None:
        return {"mode": "full", "reason": "git diff не удался", "files": [], "rows": []}
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard") or ""
    files = sorted({f for f in (diff + untracked).splitlines() if f and not _skipped(Path(f))})
    rows = []
    invalid = []
    for name in SCHEMAS:
        if not (repo / DOCS / name).is_file():
            continue
        try:
            doc = read_doc(repo, name)
        except ArtifactError:
            invalid.append(name)
            continue
        for section, table in doc.items():
            first = SCHEMAS[name][section][0]
            for row in table:
                if any(rel in files for rel, _ in code_refs(row["Код"]) or []):
                    rows.append(f"{name}#{section}: {row[first]} — {row['Код']}")
    result.update(files=files, rows=rows, invalid=invalid)
    result["deleted"] = [f for f in files if not (repo / f).exists()]
    return result


def format_changed(data: dict) -> str:
    lines = [f"mode: {data['mode']} ({data['reason']})"]
    if data["mode"] == "full":
        return "\n".join(lines)
    deleted = set(data.get("deleted", []))
    files = [f"{f} (удалён)" if f in deleted else f for f in data["files"]]
    invalid = data.get("invalid") or []
    invalid_line = f"invalid: {', '.join(invalid)} (не по схеме — полный проход)" if invalid else "invalid: нет"
    return "\n".join(lines + [invalid_line, "files:", *_listing(files), "rows:", *_listing(data["rows"])])


def stamp(repo: Path, today: date | None = None) -> list[str]:
    errors = check_repo(repo)
    if errors:
        return errors
    head = _git(repo, "rev-parse", "HEAD")
    data = {
        "sha": head.strip() if head else None,
        "indexed": (today or date.today()).isoformat(),
        "plugin": _plugin_version(),
        "files": doc_hashes(repo),
    }
    write_atomic(repo / DOCS / STAMP_FILE, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return []


USAGE = "usage: sa_index.py survey <repo> | changed <repo> | check <repo> [файл…] | stamp <repo> | aggregate [--force]"


def _repo(raw: str) -> Path | None:
    repo = Path(raw).expanduser().absolute()
    if not repo.is_dir():
        print(f"нет папки {repo}", file=sys.stderr)
        return None
    return repo


def _aggregate_cli(args: list[str]) -> int:
    if args not in ([], ["--force"]):
        print(USAGE, file=sys.stderr)
        return 2
    from sa_index_aggregate import GLOBAL_FILES, aggregate
    from sa_paths import resolve_paths

    paths = resolve_paths()
    if not paths["repos_exists"]:
        print(f"нет папки репозиториев {paths['repos_root']}", file=sys.stderr)
        return 1
    index_dir = Path(paths["index_dir"])
    warnings, refused = aggregate(Path(paths["repos_root"]), index_dir, paths["services"], force=bool(args))
    written = [str(index_dir / n) for n in GLOBAL_FILES if n not in refused]
    print("записано: " + ", ".join(written))
    for warning in warnings:
        print(f"предупреждение: {warning}")
    for name in refused:
        print(f"{name}: файл не собран sa_index.py — не перезаписан; после согласия аналитика запустите aggregate --force")
    return 1 if refused else 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "aggregate":
        return _aggregate_cli(argv[1:])
    commands = {"survey", "changed", "check", "stamp"}
    if not argv or argv[0] not in commands or len(argv) < 2 or (argv[0] != "check" and len(argv) != 2):
        print(USAGE, file=sys.stderr)
        return 2
    repo = _repo(argv[1])
    if repo is None:
        return 1
    if argv[0] == "survey":
        print(format_survey(survey(repo)))
        return 0
    if argv[0] == "changed":
        print(format_changed(changed(repo)))
        return 0
    if argv[0] == "stamp":
        errors = stamp(repo)
        print("\n".join(errors) if errors else f"записано: {repo / DOCS / STAMP_FILE}")
        return 1 if errors else 0
    names = argv[2:] or None
    if names and any(n not in SCHEMAS for n in names):
        print(f"файлы индекса: {', '.join(SCHEMAS)}", file=sys.stderr)
        return 2
    errors = check_repo(repo, names)
    print("\n".join(errors) if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
