"""Подписи интерфейса из файлов переводов фронта (locales/ru-RU.json): по тексту или ключу — точная подпись, ключ, файл:строка."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LOCALE_GLOB = "**/locales/ru*.json"
SKIP_PARTS = {"node_modules", "dist", "build", ".git"}
LIMIT = 20
_KEY_QUERY = re.compile(r"^[A-Za-z_$][\w$-]*(?:\.[\w$-]+)+$|^[a-z][A-Za-z0-9_]*$")


def locale_files(repo: Path) -> list[Path]:
    return sorted(p for p in repo.glob(LOCALE_GLOB) if not SKIP_PARTS & set(p.relative_to(repo).parts))


def entries(path: Path) -> list[tuple[str, str, int]]:
    """(ключ через точку, текст, номер строки) в порядке файла."""
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(text)
    lines = text.splitlines()
    found: list[tuple[str, str, int]] = []
    cursor = 0

    def locate(needle: str) -> int:
        nonlocal cursor
        for i in range(cursor, len(lines)):
            if needle in lines[i]:
                cursor = i
                return i + 1
        return 0

    def walk(node, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                path_key = f"{prefix}.{key}" if prefix else key
                line = locate(json.dumps(key, ensure_ascii=False) + ":") or locate(json.dumps(key, ensure_ascii=False))
                if isinstance(value, str):
                    found.append((path_key, value, line))
                else:
                    walk(value, path_key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, str):
                    found.append((f"{prefix}[{index}]", value, locate(json.dumps(value, ensure_ascii=False)[1:-1])))
                else:
                    walk(value, f"{prefix}[{index}]")

    walk(data, "")
    return found


def _norm(value: str) -> str:
    return " ".join(value.replace("ё", "е").replace("Ё", "Е").lower().split())


def find(repo: Path, query: str) -> list[tuple[str, int, str, str, bool]]:
    """Совпадения (файл, строка, ключ, текст, точное). Сначала точные; запрос-ключ ищется по ключам, текст — по подписям."""
    files = locale_files(repo)
    if not files:
        raise FileNotFoundError(f"в {repo} нет файлов переводов {LOCALE_GLOB}")
    by_key = bool(_KEY_QUERY.match(query))
    wanted = _norm(query)
    hits: list[tuple[str, int, str, str, bool]] = []
    for path in files:
        rel = path.relative_to(repo).as_posix()
        for key, text, line in entries(path):
            if by_key:
                exact = key == query or key.endswith("." + query)
                match = exact or query.lower() in key.lower()
            else:
                exact = _norm(text) == wanted
                match = exact or wanted in _norm(text)
            if match:
                hits.append((rel, line, key, text, exact))
    hits.sort(key=lambda h: not h[4])
    return hits


def render(repo: Path, queries: list[str]) -> str:
    out: list[str] = []
    for query in queries:
        hits = find(repo, query)
        if not hits:
            out.append(f"«{query}»: не найдено — в интерфейсе такой подписи нет (новый текст или другое название)")
            continue
        exact = sum(h[4] for h in hits)
        out.append(f"«{query}»: точных {exact}, всего {len(hits)}" + (f", показаны первые {LIMIT}" if len(hits) > LIMIT else ""))
        out += [
            f"  {'=' if is_exact else '~'} {repo.name}/{rel}:{line} {key} = «{text}»"
            for rel, line, key, text, is_exact in hits[:LIMIT]
        ]
    return "\n".join(out)


USAGE = "использование: sa_locale.py find <папка репозитория фронта> <текст или ключ>..."


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] != "find":
        print(USAGE, file=sys.stderr)
        return 2
    try:
        print(render(Path(argv[1]), argv[2:]))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
