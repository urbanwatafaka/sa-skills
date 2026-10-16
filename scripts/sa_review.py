"""Ревью черновика: детерминированные проходы 1–3, матрица покрытия, утверждения о существующем, статусы замечаний."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sa_artifacts import ArtifactError, find_table, parse_tables, split_frontmatter
from sa_draft import (
    block_section, placeholders, section_texts, task_data, task_manifest, trace_refs, untraced_impacts,
)
from sa_state import ARTIFACTS, file_sha1, load_state, write_atomic

SEVERITIES = ("критично", "важно", "совет")
STATUSES = ("открыто", "принято", "отклонено", "закрыто")
REVIEW_COLUMNS = ["ID", "Важность", "Где", "Проблема", "← Ссылка", "Предложение", "Статус"]
COVERAGE_COLUMNS = ["R", "Секции", "Истории"]
WHOLE = ("шапка", "весь черновик")
STORY_COLUMNS = ["Контекст", "User Story", "Критерии приемки"]
COVERED_TYPES = ("функц.", "UI")
PRESERVED_HEADING = "## Сохраняемое поведение"
EXISTING_IMPACT = ("изм.", "удал.")
ROW_ID_RE = re.compile(r"^\|\s*(RV-\d{2,})\s*\|")
PRESERVED = "[сохраняется]"
EXISTING = "[существует]"
NO_SERVICE = "без сервиса"


@dataclass
class Finding:
    severity: str
    where: str
    problem: str
    ref: str
    proposal: str

    def row(self) -> str:
        return f"| {self.severity} | {self.where} | {self.problem} | {self.ref} | {self.proposal} |"


def _context(task_dir: Path):
    state = load_state(task_dir)
    manifest = task_manifest(state)
    return manifest, task_data(task_dir), section_texts(task_dir, manifest)


def story_refs(text: str) -> dict[str, list[str]]:
    """«история N» → R-xx из трассировки её критериев приёмки. N — номер строки таблицы User Stories, кода US-xx в ТЗ нет."""
    table = find_table(parse_tables(text), STORY_COLUMNS)
    if table is None:
        return {}
    return {
        f"история {number}": [r for r in trace_refs(row["Критерии приемки"]) if r.startswith("R-")]
        for number, row in enumerate(table.rows, start=1)
    }


def brd_types(task_dir: Path) -> dict[str, str]:
    path = task_dir / ARTIFACTS["BRD"]
    if not path.exists():
        return {}
    table = find_table(parse_tables(split_frontmatter(path.read_text(encoding="utf-8"))[1]), ["ID", "Требование", "Тип"])
    return {row["ID"]: row["Тип"] for row in table.rows} if table else {}


def coverage(task_dir: Path) -> list[tuple[str, list[str], list[str]]]:
    manifest, data, texts = _context(task_dir)
    stories = story_refs(texts.get(block_section(manifest, "brd") or "", ""))
    return [
        (
            r,
            [sid for sid, text in texts.items() if r in trace_refs(text)],
            [story for story, refs in stories.items() if r in refs],
        )
        for r in data["brd"]
    ]


def coverage_table(task_dir: Path) -> str:
    lines = ["| R | Секции | Истории |", "|---|---|---|"]
    lines += [f"| {r} | {', '.join(s) or '—'} | {', '.join(a) or '—'} |" for r, s, a in coverage(task_dir)]
    return "\n".join(lines)


def _draft_md(task_dir: Path) -> Path:
    path = task_dir / ARTIFACTS["draft"]
    if not path.exists():
        raise ArtifactError("нет draft.md — сначала /tdd-draft")
    return path


def precheck(task_dir: Path) -> list[Finding]:
    _draft_md(task_dir)
    manifest, data, texts = _context(task_dir)
    acceptance = block_section(manifest, "brd") or "весь черновик"
    types = brd_types(task_dir)
    changes = block_section(manifest, "changes") or "весь черновик"
    statuses = {q.id: q.status for q in data["questions"]}
    findings: list[Finding] = []
    for sid, text in texts.items():
        for qid in dict.fromkeys(q for q in placeholders(text) if q):
            if statuses.get(qid) == "open":
                findings.append(Finding("важно", sid, f"⚠ {qid}: неизвестное не закрыто", qid,
                                        f"закрыть {qid} в /tdd-clarify, затем /tdd-update"))
            elif qid not in statuses:
                findings.append(Finding("важно", sid, f"⚠ {qid}: вопрос не найден в questions.md", qid,
                                        f"завести {qid} или убрать плейсхолдер"))
            else:
                findings.append(Finding("важно", sid, f"⚠ {qid} стоит на закрытом вопросе", qid,
                                        "/tdd-update заменит плейсхолдер по решению"))
    for r, sections, stories in coverage(task_dir):
        if not stories and types.get(r) in COVERED_TYPES:
            where = f"есть в {', '.join(sections)}" if sections else "нет ни в одной секции"
            findings.append(Finding("критично", acceptance,
                                    f"{r} ({types[r]}) не покрыт ни одним критерием приёмки User Stories ({where})", r,
                                    f"добавить критерий со ссылкой ‹{r}› в таблицу User Stories"))
    traced = {ref for text in texts.values() for ref in trace_refs(text)}
    for im in untraced_impacts(data, traced, ("в скоупе", "?")):
        findings.append(Finding("важно", changes, f"{im} (новый/изм.) не описан ни в одной секции", im,
                                f"описать в {changes} или исключить в context.md"))
    return findings


def render_precheck(task_dir: Path) -> str:
    findings = precheck(task_dir)
    lines = [f"draft: {file_sha1(_draft_md(task_dir))}", f"Замечания проходов 1–3: {len(findings)}"]
    if findings:
        lines += ["| Важность | Где | Проблема | ← Ссылка | Предложение |", "|---|---|---|---|---|"]
        lines += [f.row() for f in findings]
    return "\n".join(lines)


def _preserved_lines(text: str) -> set[int]:
    """Номера строк-пунктов в подразделе «Сохраняемое поведение»."""
    found: set[int] = set()
    inside = False
    for number, line in enumerate(text.splitlines()):
        if line.startswith("#"):
            inside = line.strip() == PRESERVED_HEADING
        elif inside and line.lstrip().startswith(("- ", "* ")):
            found.add(number)
    return found


def as_is(task_dir: Path) -> dict[str, list[str]]:
    """Утверждения о том, что уже есть в коде, по сервисам.

    [сохраняется] — пункт «Сохраняемое поведение» в «Тестировании и регрессе»: текущее поведение целиком.
    [существует] — строка любой секции со ссылкой на строку карты `изм.`/`удал.` с источником в коде: сверяется,
    что объект есть и сейчас устроен так, как сказано; само изменение — целевое поведение, его не оспаривают.
    """
    manifest, data, texts = _context(task_dir)
    services = {row["ID"]: row["Объект"].split(":", 1)[0].strip() for row in data["impact"]}
    existing = {
        row["ID"] for row in data["impact"]
        if row.get("Влияние") in EXISTING_IMPACT and row.get("Источник", "").startswith("code:")
    }
    testing = block_section(manifest, "testing")
    groups: dict[str, list[str]] = {}
    for sid, text in texts.items():
        preserved = _preserved_lines(text) if sid == testing else set()
        for number, line in enumerate(text.splitlines()):
            refs = trace_refs(line)
            if number in preserved:
                kind = PRESERVED
            elif any(r in existing for r in refs):
                kind = EXISTING
            else:
                continue
            owners = [r for r in refs if r in existing] if kind == EXISTING else refs
            names = list(dict.fromkeys(services[r] for r in owners if r in services)) or [NO_SERVICE]
            text_line = line.strip().removeprefix("- ").removeprefix("* ").strip()
            statement = f"{kind} {sid}: {text_line}"
            for name in names:
                groups.setdefault(name, []).append(statement)
    return groups


def render_as_is(task_dir: Path) -> str:
    groups = as_is(task_dir)
    if not groups:
        return "Утверждений о существующем нет"
    lines: list[str] = []
    for name, statements in groups.items():
        lines.append(f"{name}:")
        lines += [f"  {s}" for s in statements]
    return "\n".join(lines)


def _review_path(task_dir: Path) -> Path:
    path = task_dir / ARTIFACTS["review"]
    if not path.exists():
        raise ArtifactError("нет review.md — сначала /tdd-check")
    return path


def review_rows(task_dir: Path) -> list[dict[str, str]]:
    _, body = split_frontmatter(_review_path(task_dir).read_text(encoding="utf-8"))
    table = find_table(parse_tables(body), REVIEW_COLUMNS)
    if table is None:
        raise ArtifactError("review.md: нет таблицы замечаний")
    return table.rows


def set_status(task_dir: Path, status: str, ids: list[str]) -> list[str]:
    if status not in ("принято", "отклонено"):
        raise ArtifactError("статус: принято или отклонено")
    rows = {row["ID"]: row["Статус"] for row in review_rows(task_dir)}
    targets = [rid for rid, value in rows.items() if value == "открыто"] if ids == ["все"] else ids
    for rid in targets:
        if rid not in rows:
            raise ArtifactError(f"нет замечания {rid}")
        if rows[rid] == "закрыто":
            raise ArtifactError(f"{rid} уже закрыто")
    path = _review_path(task_dir)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        match = ROW_ID_RE.match(line)
        if match and match.group(1) in targets:
            end = "\n" if line.endswith("\n") else ""
            head = line.rstrip("\r\n").rstrip().rstrip("|").rpartition("|")[0]
            lines[i] = f"{head}| {status} |{end}"
    write_atomic(path, "".join(lines))
    return targets


def review_summary(task_dir: Path) -> dict | None:
    if not (task_dir / ARTIFACTS["review"]).exists():
        return None
    try:
        meta, _ = split_frontmatter(_review_path(task_dir).read_text(encoding="utf-8"))
        rows = review_rows(task_dir)
    except ArtifactError:
        return {"broken": True, "open": 0, "critical": 0, "accepted": 0, "stale": True}
    draft = task_dir / ARTIFACTS["draft"]
    return {
        "open": sum(r["Статус"] == "открыто" for r in rows),
        "critical": sum(r["Статус"] == "открыто" and r["Важность"] == "критично" for r in rows),
        "accepted": sum(r["Статус"] == "принято" for r in rows),
        "stale": not draft.exists() or meta.get("draft") != file_sha1(draft),
    }


USAGE = (
    "использование:\n"
    "  sa_review.py precheck <папка задачи>\n"
    "  sa_review.py coverage <папка задачи>\n"
    "  sa_review.py asis <папка задачи>\n"
    "  sa_review.py status <папка задачи> <принято|отклонено> <RV-xx…|все>"
)
RENDER = {"precheck": render_precheck, "coverage": coverage_table, "asis": render_as_is}


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if not ((command in RENDER and len(argv) == 2) or (command == "status" and len(argv) >= 4)):
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "status":
            changed = set_status(task_dir, argv[2], argv[3:])
            print(f"{argv[2]}: {', '.join(changed) if changed else 'нет открытых замечаний'}")
        else:
            print(RENDER[command](task_dir))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
