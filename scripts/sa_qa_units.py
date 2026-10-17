"""Единицы покрытия QA: проверяемые пункты ТЗ из секций draft/ и их стабильные ID U-xx в qa/units.md."""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from sa_artifacts import ArtifactError, find_refs, find_table, parse_tables
from sa_ids import next_ids

UNITS_FILE = "qa/units.md"
HEADER = ["ID", "Где", "Пункт", "Статус", "Причина"]
STATUSES = ("", "не поведение", "не тестируется", "нужно решение", "удал.")
REMOVED = "удал."
SIMILAR = 0.6

TRACE_RE = re.compile(r"\s*‹([^›]*)›")
ITEM_RE = re.compile(r"^(\s*)(?:\d+\.|[-*•])\s+(.*)$")
SERVICE_RE = re.compile(r"^##\s+\**\[?([^\]*]+?)\]?(?:\([^)]*\))?\**\s*$")
BR_RE = re.compile(r"<br\s*/?>", re.I)


@dataclass
class Unit:
    id: str
    where: str
    text: str
    refs: list[str]
    status: str = ""
    reason: str = ""


def _clean(raw: str) -> tuple[str, list[str]]:
    refs = [r for trace in TRACE_RE.findall(raw) for r in find_refs(trace)]
    text = re.sub(r"\s+", " ", TRACE_RE.sub("", raw)).strip().replace("|", "¦")
    return text, refs


def _list_items(lines: list[str]) -> list[tuple[str, str]]:
    """Пункты списка любой глубины: (номер позиции «1.2.1», текст); строки-продолжения приклеиваются к пункту."""
    items: list[list[str]] = []
    stack: list[list[int]] = []  # [отступ, номер позиции]
    for line in lines:
        if not line.strip():
            continue
        match = ITEM_RE.match(line)
        if match:
            indent = len(match.group(1).expandtabs(4))
            while stack and stack[-1][0] > indent:
                stack.pop()
            if stack and stack[-1][0] == indent:
                stack[-1][1] += 1
            else:
                stack.append([indent, 1])
            items.append([".".join(str(n) for _, n in stack), match.group(2)])
        elif items and line[:1].isspace():
            items[-1][1] += " " + line.strip()
        else:
            break
    return [(path, text) for path, text in items]


def _sections(body: str, level: str = "## ") -> list[tuple[str, list[str]]]:
    parts: list[tuple[str, list[str]]] = [("", [])]
    for line in body.splitlines():
        if line.startswith(level):
            parts.append((line[len(level):].strip(), []))
        else:
            parts[-1][1].append(line)
    return parts


def _after(lines: list[str], marker: str) -> list[str]:
    """Строки после строки-маркера до следующего жирного подзаголовка или заголовка."""
    for i, line in enumerate(lines):
        if line.strip() == marker:
            block = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("#") or nxt.strip().startswith("**"):
                    break
                block.append(nxt)
            return block
    return []


def _units(where: str, items: list[tuple[str, str]]) -> list[Unit]:
    units = []
    for path, raw in items:
        text, refs = _clean(raw)
        if text:
            units.append(Unit("", f"{where}/{path}", text, refs))
    return units


def _read(task_dir: Path, name: str) -> str:
    path = task_dir / "draft" / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _brd_units(body: str) -> list[Unit]:
    units: list[Unit] = []
    sections = dict(_sections(body))
    stories = find_table(parse_tables("\n".join(sections.get("User Stories", []))), ["Критерии приемки"])
    for n, row in enumerate(stories.rows if stories else [], start=1):
        bullets = [part.strip()[1:] for part in BR_RE.split(row["Критерии приемки"]) if part.strip().startswith("•")]
        units += _units(f"01-brd/story-{n}", [(str(k), b) for k, b in enumerate(bullets, start=1)])
    units += _units("01-brd/ui", _list_items(_skip_blank(sections.get("Требования к UI", []))))
    return units


def _skip_blank(lines: list[str]) -> list[str]:
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    return lines[start:]


def _changes_units(body: str) -> list[Unit]:
    units: list[Unit] = []
    for heading, lines in _sections(body)[1:]:
        match = SERVICE_RE.match(f"## {heading}")
        service = match.group(1).strip() if match else heading
        for sub, sub_lines in _sections("\n".join(lines), "### "):
            if sub == "Back":
                block = _after(sub_lines, "**1. Описание изменений:**")
                units += _units(f"03-changes/{service}/Back", _list_items(_skip_blank(block)))
            elif sub.startswith("Экран:"):
                screen = sub[len("Экран:"):].strip()
                block = _after(sub_lines, "**Что изменить:**")
                units += _units(f"03-changes/{service}/Front/{screen}", _list_items(_skip_blank(block)))
    return units


def _testing_units(body: str) -> list[Unit]:
    sections = dict(_sections(body))
    units = _units("08-testing/new", _list_items(_skip_blank(sections.get("Новое поведение", []))))
    return units + _units("08-testing/keep", _list_items(_skip_blank(sections.get("Сохраняемое поведение", []))))


def extract_units(task_dir: Path) -> list[Unit]:
    """Все проверяемые пункты ТЗ в порядке документа, без ID."""
    return (
        _brd_units(_read(task_dir, "01-brd"))
        + _changes_units(_read(task_dir, "03-changes"))
        + _testing_units(_read(task_dir, "08-testing"))
    )


def _format_text(unit: Unit) -> str:
    return unit.text + (f" ‹{', '.join(unit.refs)}›" if unit.refs else "")


def load_units(task_dir: Path) -> list[Unit]:
    path = task_dir / UNITS_FILE
    if not path.exists():
        return []
    table = find_table(parse_tables(path.read_text(encoding="utf-8")), HEADER)
    if table is None:
        raise ArtifactError(f"{UNITS_FILE}: нет таблицы | {' | '.join(HEADER)} |")
    units = []
    for row in table.rows:
        text, refs = _clean(row["Пункт"])
        units.append(Unit(row["ID"], row["Где"], text, refs, row["Статус"], row["Причина"]))
    return units


def write_units(task_dir: Path, units: list[Unit]) -> None:
    lines = [
        "# Единицы покрытия",
        "",
        "Статус: пусто — тестируется; «не поведение», «не тестируется», «нужно решение» — с причиной; "
        "«удал.» — пункта больше нет в ТЗ.",
        "",
        "| " + " | ".join(HEADER) + " |",
        "|" + "---|" * len(HEADER),
    ]
    for u in units:
        lines.append(f"| {u.id} | {u.where} | {_format_text(u)} | {u.status} | {u.reason} |".replace("|  |", "| |"))
    path = task_dir / UNITS_FILE
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _group(where: str) -> str:
    return where.split("/", 1)[0]


def sync_units(task_dir: Path) -> list[Unit]:
    """Сопоставить пункты ТЗ с сохранёнными единицами: ID, статус и причина сохраняются; пропавшие — «удал.»."""
    saved = load_units(task_dir)
    current = extract_units(task_dir)
    match: dict[int, int] = {}
    free = list(range(len(saved)))

    def take(i: int, j: int) -> None:
        match[i] = j
        free.remove(j)

    for same_where in (True, False):
        for i, unit in enumerate(current):
            if i in match:
                continue
            for j in free:
                if saved[j].text == unit.text and (not same_where or saved[j].where == unit.where):
                    take(i, j)
                    break
    pairs = []
    for i, unit in enumerate(current):
        if i in match:
            continue
        for j in free:
            if _group(saved[j].where) != _group(unit.where):
                continue
            ratio = SequenceMatcher(None, saved[j].text, unit.text).ratio()
            if ratio >= SIMILAR:
                pairs.append((ratio + (0.01 if saved[j].where == unit.where else 0), i, j))
    for _, i, j in sorted(pairs, key=lambda p: (-p[0], p[1], p[2])):
        if i not in match and j in free:
            take(i, j)

    fresh = [i for i in range(len(current)) if i not in match]
    new_ids = next_ids(task_dir, "U", len(fresh)) if fresh else []
    result = []
    for i, unit in enumerate(current):
        if i in match:
            old = saved[match[i]]
            unit.id = old.id
            if old.status != REMOVED:
                unit.status, unit.reason = old.status, old.reason
        else:
            unit.id = new_ids[fresh.index(i)]
        result.append(unit)
    for j in free:
        removed = saved[j]
        removed.status = REMOVED
        result.append(removed)
    write_units(task_dir, result)
    return result
