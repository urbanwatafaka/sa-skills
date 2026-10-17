"""Разбор артефактов задачи: frontmatter, markdown-таблицы, вопросы, ID."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

REF_RE = re.compile(r"\bQ-(?:PO|SA|QA)-\d{2,}\b|\b(?:R|IM|D|RV|TC|U|QV)-\d{2,}\b")
# Путь с префиксом шлюза: после префикса раздела идёт ещё один префикс раздела или версия —
# /api/backoffice/v1/orders. Метод в ТЗ пишется так, как объявлен в сервисе: /backoffice/orders.
GATEWAY_PATH_RE = re.compile(r"(?<![\w/])/(?:api|backoffice|public|internal)/(?:api|backoffice|public|internal|v\d+)(?=/|\b)")

ID_PATTERNS = {
    "R": re.compile(r"R-\d{2,}"),
    "IM": re.compile(r"IM-\d{2,}"),
    "Q": re.compile(r"Q-(?:PO|SA|QA)-\d{2,}"),
    "D": re.compile(r"D-\d{2,}"),
    "RV": re.compile(r"RV-\d{2,}"),
    "TC": re.compile(r"TC-\d{2,}"),
    "U": re.compile(r"U-\d{2,}"),
    "QV": re.compile(r"QV-\d{2,}"),
}


class ArtifactError(ValueError):
    """Артефакт не разбирается: сломан формат."""


@dataclass
class Table:
    header: list[str]
    rows: list[dict[str, str]]


@dataclass
class Question:
    id: str
    audience: str
    section: str
    refs: list[str]
    status: str
    blocking: bool
    text: str
    bad_refs: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    approval: list[str] = field(default_factory=list)
    answer: str = ""


def find_refs(text: str) -> list[str]:
    return REF_RE.findall(text)


def ref_prefix(ref: str) -> str:
    return "Q" if ref.startswith("Q-") else ref.split("-", 1)[0]


def is_id(kind: str, value: str) -> bool:
    return ID_PATTERNS[kind].fullmatch(value) is not None


def _scalar(raw: str):
    value = raw.strip()
    if value in ("true", "false"):
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [item.strip() for item in inner.split(",")] if inner else []
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            break
    else:
        raise ArtifactError("frontmatter не закрыт строкой ---")
    meta = {}
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        if ":" not in line:
            raise ArtifactError(f"frontmatter, строка {number}: ожидается «ключ: значение»")
        key, raw = line.split(":", 1)
        meta[key.strip()] = _scalar(raw)
    return meta, "\n".join(lines[end + 1:])


_SEP_RE = re.compile(r"^\|?(\s*:?-{3,}:?\s*\|)*\s*:?-{3,}:?\s*\|?$")


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [cell.strip() for cell in s.split("|")]


def parse_tables(body: str) -> list[Table]:
    lines = body.splitlines()
    tables: list[Table] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if line.startswith("|") and _SEP_RE.match(nxt):
            header = _cells(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = _cells(lines[i])
                if len(cells) != len(header):
                    raise ArtifactError(
                        f"строка таблицы «{lines[i].strip()[:40]}»: "
                        f"{len(cells)} ячеек, в заголовке {len(header)}"
                    )
                rows.append(dict(zip(header, cells)))
                i += 1
            tables.append(Table(header, rows))
        else:
            i += 1
    return tables


def find_table(tables: list[Table], required: list[str]) -> Table | None:
    for table in tables:
        if all(column in table.header for column in required):
            return table
    return None


_Q_START = re.compile(r"^- \*\*(Q-(PO|SA|QA)-\d{2,})\*\*\s*(.*)$")
_Q_REFS = re.compile(r"^\[([^\]]*)\]\s*(.*)$")
_Q_STATUS = re.compile(r"—\s*\*(open|answered|obsolete)(, blocking)?\*\s*$", re.M)
_SECTIONS = {"## Для PO": "PO", "## Для аналитика": "SA"}
_Q_APPROVAL = re.compile(r"^Согласование:\s*(.*)$")
_Q_ANSWER = re.compile(r"^Ответ в ТЗ:\s*(.*)$")


def parse_questions(body: str) -> list[Question]:
    blocks: list[tuple[str, list[str]]] = []
    section = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            section = _SECTIONS.get(stripped, "")
        elif _Q_START.match(stripped):
            blocks.append((section, [stripped]))
        elif blocks and stripped and line.startswith((" ", "\t")):
            blocks[-1][1].append(stripped)

    questions = []
    for section, chunk in blocks:
        start = _Q_START.match(chunk[0])
        qid, audience, rest = start.group(1), start.group(2), start.group(3)
        status = _Q_STATUS.search("\n".join(chunk))
        if status is None:
            raise ArtifactError(f"{qid}: нет статуса вида «— *open*»")
        refs_match = _Q_REFS.match(rest)
        refs: list[str] = []
        bad_refs: list[str] = []
        if refs_match:
            for token in (t.strip() for t in refs_match.group(1).split(",")):
                if not token:
                    continue
                if token == "BRD" or REF_RE.fullmatch(token):
                    refs.append(token)
                else:
                    bad_refs.append(token)
        text = refs_match.group(2) if refs_match else rest
        details = [d for d in (_Q_STATUS.sub("", line).strip() for line in chunk[1:]) if d]
        approval: list[str] = []
        answer = ""
        for line in details:
            if m := _Q_APPROVAL.match(line):
                approval = [t.strip() for t in m.group(1).split(",") if t.strip()]
            elif m := _Q_ANSWER.match(line):
                answer = m.group(1).strip()
        questions.append(
            Question(
                id=qid,
                audience=audience,
                section=section,
                refs=refs,
                status=status.group(1),
                blocking=bool(status.group(2)),
                text=_Q_STATUS.sub("", text).strip(),
                bad_refs=bad_refs,
                details=details,
                approval=approval,
                answer=answer,
            )
        )
    return questions
