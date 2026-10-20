"""Ревью черновика: детерминированные проходы 1–3, матрица покрытия, утверждения о существующем, статусы замечаний."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sa_artifacts import ArtifactError, find_refs, find_table, parse_tables, split_frontmatter
from sa_draft import (
    block_section, placeholders, section_texts, task_data, task_manifest, trace_refs, untraced_impacts,
)
from sa_ids import next_ids
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
MENTIONS = "[упоминает]"
NO_SERVICE = "без сервиса"
# Пункт про новый объект («Новый метод…», «**Новое поле** в таблице…»): сам объект не сверяется, только упомянутые в нём существующие.
NEW_OBJECT_RE = re.compile(r"^\s*(?:[-*]\s+|\d+(?:\.\d+)*\.?\s+)?(?:\*\*)?Нов(?:ый|ая|ое|ые)\b")


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
    [упоминает] — такая же строка про новый объект («Новое поле … в таблице …»): новый объект не ищут, сверяют только
    упомянутые в ней существующие (таблица, метод, топик, экран) — что они есть и так называются.
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
                kind = MENTIONS if NEW_OBJECT_RE.match(line) else EXISTING
            else:
                continue
            owners = [r for r in refs if r in existing] if kind in (EXISTING, MENTIONS) else refs
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


# Проблемы, которые формулирует precheck: такое замечание закрывается, когда precheck его больше не находит.
SCRIPT_PROBLEM_RE = re.compile(r"^⚠ Q-|не покрыт ни одним критерием приёмки|не описан ни в одной секции")
KEEP_OPEN = ("открыто", "принято")


def _cell(value: str) -> str:
    return " ".join(str(value).replace("|", "¦").split()) or "—"


def _existing_ids(data: dict) -> set[str]:
    return (
        set(data["brd"]) | {row["ID"] for row in data["impact"]}
        | {row["ID"] for row in data["decisions"]} | {q.id for q in data["questions"]}
    )


def build_review(task_dir: Path, new: list[dict], close: list[str], today: str | None = None) -> dict:
    """Собирает review.md: прошлые строки (меняется только статус), замечания precheck и переданные, шапка, матрица.

    new — замечания ревьюера и сверки с кодом: {severity, where, problem, ref, proposal}; close — ID прошлых
    замечаний, которые ревьюер признал закрытыми. Замечания precheck скрипт берёт и закрывает сам.
    """
    from datetime import date

    draft = _draft_md(task_dir)
    state = load_state(task_dir)
    path = task_dir / ARTIFACTS["review"]
    old_rows: list[dict[str, str]] = []
    round_no = 1
    if path.exists():
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        old_rows = review_rows(task_dir)
        round_no = int(meta.get("round") or 0) + 1
    by_id = {row["ID"]: row for row in old_rows}
    for rid in close:
        if rid not in by_id:
            raise ArtifactError(f"нет замечания {rid}")
        if by_id[rid]["Статус"] not in KEEP_OPEN:
            raise ArtifactError(f"{rid} — {by_id[rid]['Статус']}, его статус не меняют")
    found = precheck(task_dir)
    script_keys = {(f.where, f.problem) for f in found}
    existing = _existing_ids(task_data(task_dir))
    closed: list[str] = []
    for row in old_rows:
        if row["Статус"] not in KEEP_OPEN:
            continue
        key = (row["Где"], row["Проблема"])
        lost = row["Статус"] == "открыто" and any(
            r not in existing for r in find_refs(row["← Ссылка"]) if not r.startswith(("RV-", "TC-", "U-", "QV-", "Q-QA-"))
        )
        if row["ID"] in close or (SCRIPT_PROBLEM_RE.search(row["Проблема"]) and key not in script_keys) or lost:
            row["Статус"] = "закрыто"
            closed.append(row["ID"])
    candidates = [Finding(f.severity, f.where, f.problem, f.ref, f.proposal) for f in found]
    for item in new:
        try:
            finding = Finding(*(_cell(item[k]) for k in ("severity", "where", "problem", "ref", "proposal")))
        except KeyError as exc:
            raise ArtifactError(f"в замечании нет поля {exc.args[0]}") from None
        if finding.severity not in SEVERITIES:
            raise ArtifactError(f"важность «{finding.severity}»: {', '.join(SEVERITIES)}")
        candidates.append(finding)
    seen = {(row["Где"], row["Проблема"]) for row in old_rows if row["Статус"] in ("открыто", "принято", "отклонено")}
    fresh: list[Finding] = []
    for f in candidates:
        f = Finding(_cell(f.severity), _cell(f.where), _cell(f.problem), _cell(f.ref), _cell(f.proposal))
        if (f.where, f.problem) not in seen:
            seen.add((f.where, f.problem))
            fresh.append(f)
    ids = next_ids(task_dir, "RV", len(fresh)) if fresh else []
    lines = [
        "---",
        f"draft: {file_sha1(draft)}",
        f"reviewed: {today or date.today().isoformat()}",
        f"round: {round_no}",
        "---",
        f"# Ревью черновика {state.get('task', task_dir.name)}",
        "",
        "## Замечания",
        "",
        "| " + " | ".join(REVIEW_COLUMNS) + " |",
        "|" + "---|" * len(REVIEW_COLUMNS),
    ]
    lines += ["| " + " | ".join(row[c] for c in REVIEW_COLUMNS) + " |" for row in old_rows]
    lines += [f"| {rid} {f.row()} открыто |" for rid, f in zip(ids, fresh)]
    lines += ["", "## Покрытие BRD", "", coverage_table(task_dir), ""]
    write_atomic(path, "\n".join(lines))
    rows = old_rows + [{"Важность": f.severity, "Статус": "открыто"} for f in fresh]
    return {
        "round": round_no,
        "closed": closed,
        "new": ids,
        "open": sum(r["Статус"] == "открыто" for r in rows),
        "critical": sum(r["Статус"] == "открыто" and r["Важность"] == "критично" for r in rows),
    }


def render_write(task_dir: Path, source: Path) -> str:
    import json

    try:
        text = source.read_text(encoding="utf-8")
        payload = json.loads(text) if text.strip() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"{source}: не читается как JSON — {exc}") from None
    if not isinstance(payload, dict):
        raise ArtifactError(f"{source}: ожидается объект {{\"new\": [...], \"close\": [...]}}")
    result = build_review(task_dir, payload.get("new") or [], payload.get("close") or [])
    return "\n".join([
        f"round: {result['round']}",
        f"закрыто: {', '.join(result['closed']) or '—'}",
        f"новых: {', '.join(result['new']) or '—'}",
        f"открыто всего: {result['open']}, из них критичных: {result['critical']}",
    ])


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
    "  sa_review.py status <папка задачи> <принято|отклонено> <RV-xx…|все>\n"
    "  sa_review.py write <папка задачи> <файл.json с {\"new\": [...], \"close\": [...]}>"
)
RENDER = {"precheck": render_precheck, "coverage": coverage_table, "asis": render_as_is}


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if not (
        (command in RENDER and len(argv) == 2) or (command == "status" and len(argv) >= 4)
        or (command == "write" and len(argv) == 3)
    ):
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "write":
            print(render_write(task_dir, Path(argv[2])))
        elif command == "status":
            changed = set_status(task_dir, argv[2], argv[3:])
            print(f"{argv[2]}: {', '.join(changed) if changed else 'нет открытых замечаний'}")
        else:
            print(RENDER[command](task_dir))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
