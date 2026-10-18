"""Тест-кейсы QA в qa/cases.md: разбор строгого формата, проверка полей и формулировок, хэш кейса."""
from __future__ import annotations

import hashlib
import re
import textwrap
from dataclasses import dataclass

from sa_artifacts import ArtifactError

KINDS = ("бэкенд", "фронт", "регресс")
PRIORITIES = ("High", "Medium", "Low")
VAGUE = ("корректно", "правильно", "проверить, что работает", "и т.д.", "при необходимости")

HEAD_RE = re.compile(r"^###\s+(?:(TC-\d{2,})\b\s*)?(.*)$")
FIELD_RE = re.compile(r"^- \*\*(Вид|Приоритет|Покрывает|Источник):\*\*\s*(.*)$")
STEP_RESULT_RE = re.compile(r"- Результат:\s*")  # подшаг-результат без текста
COLON_OUTSIDE_RE =re.compile(r"^(?:- )?\*\*([^*:]+)\*\*\s*:")
SOURCE_PREFIXES = ("code:", "код:", "docs:")
BLOCK_RE = re.compile(r"^\*\*([^*]+?):\*\*\s*(.*)$")
STEP_RE = re.compile(r"^\d+\.\s+(.*)$")
BLOCKS = {"Описание": "description", "Предусловия": "preconditions", "Шаги": "steps", "Ожидаемый результат": "expected"}
QA_PLACEHOLDER_RE = re.compile(r"⚠\s*Q-QA-\d{2,}")  # код ответа ждёт ответа аналитика
CODE_RE = re.compile(r"(?<!\d)[1-5]\d\d(?!\d)")
DETAIL_RE = re.compile(r"(?<!\d)[1-5]\d\d(?!\d)|«|`")


@dataclass
class Case:
    id: str
    title: str
    kind: str
    priority: str
    covers: list[str]
    sources: list[str]
    description: str
    preconditions: str
    steps: list[str]
    expected: str
    raw: str


def _split(text: str) -> list[list[str]]:
    chunks: list[list[str]] = []
    inside = fence = False
    for line in text.replace("\r\n", "\n").split("\n"):
        marker = line.strip().startswith("```")
        if fence or marker:
            if marker:
                fence = not fence
            if inside:
                chunks[-1].append(line)  # заголовок внутри блока кода — текст шага, не новый кейс
        elif line.startswith("### "):
            chunks.append([line])
            inside = True
        elif line.startswith(("# ", "## ")):
            inside = False  # раздел «Бэкенд/Фронт/Регресс» закрывает кейс
        elif inside:
            chunks[-1].append(line)
    return chunks


def _steps(lines: list[str], errors: list[str]) -> list[str]:
    steps: list[list[str]] = []
    for line in lines:
        match = STEP_RE.match(line)
        if match and not line[:1].isspace():
            steps.append([match.group(1)])
        elif not line.strip():
            if steps:
                steps[-1].append("")
        elif steps:
            steps[-1].append(line)
        else:
            errors.append(f"шаги: ожидается нумерованный список, а не «{line.strip()[:40]}»")
            return []
    result = []
    for first, *rest in steps:
        tail = textwrap.dedent("\n".join(rest)).strip("\n")
        result.append(first + ("\n" + tail if tail else ""))
    return result


def _parse_one(lines: list[str]) -> tuple[Case, list[str]]:
    head = HEAD_RE.match(lines[0])
    cid, title = head.group(1) or "", head.group(2).strip()
    errors: list[str] = []
    fields: dict[str, str] = {}
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    fence = False
    for line in lines[1:]:
        if fence:
            blocks[current].append(line)
            if line.strip().startswith("```"):
                fence = False
            continue
        field = FIELD_RE.match(line)
        block = BLOCK_RE.match(line)
        misplaced = COLON_OUTSIDE_RE.match(line)
        if misplaced:
            name = misplaced.group(1).strip()
            errors.append(f"«{name}»: двоеточие вне жирного — пиши **{name}:**")
            current = None
        elif field:
            if field.group(1) in fields:
                errors.append(f"поле «{field.group(1)}» повторяется")
            fields[field.group(1)] = field.group(2).strip()
            current = None
        elif block:
            name = block.group(1).strip()
            if name not in BLOCKS:
                errors.append(f"неизвестный блок «{name}»; допустимы: {', '.join(BLOCKS)}")
                current = None
                continue
            if name in blocks:
                errors.append(f"блок «{name}» повторяется")
            current = name
            blocks[name] = [block.group(2)] if block.group(2).strip() else []
        elif current is not None:
            blocks[current].append(line)
            if line.strip().startswith("```"):
                fence = True
        elif line.strip():
            errors.append(f"лишний текст «{line.strip()[:40]}» вне полей и блоков")
    if fence:
        errors.append("блок кода ``` не закрыт")
    steps = _steps(blocks.get("Шаги", []), errors)
    text = {key: "\n".join(blocks.get(key, [])).strip() for key in ("Описание", "Предусловия", "Ожидаемый результат")}
    raw = "\n".join(lines).rstrip()
    case = Case(
        id=cid,
        title=title,
        kind=fields.get("Вид", ""),
        priority=fields.get("Приоритет", ""),
        covers=_tokens(fields.get("Покрывает", "")),
        sources=_sources(fields.get("Источник", "")),
        description=text["Описание"],
        preconditions=text["Предусловия"],
        steps=steps,
        expected=text["Ожидаемый результат"],
        raw=raw,
    )
    return case, errors


def _tokens(value: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,;]", value) if t.strip()]


def _sources(value: str) -> list[str]:
    """ID ТЗ через запятую; ссылка на код или индекс — целиком до «;», в ней могут быть запятые."""
    result = []
    for part in value.replace("‹", "").replace("›", "").split(";"):
        part = part.strip()
        if part.startswith(SOURCE_PREFIXES):
            result.append(part)
        else:
            result += [t.strip() for t in part.split(",") if t.strip()]
    return result


def parse_cases(text: str) -> list[Case]:
    cases, problems = [], []
    for chunk in _split(text):
        case, errors = _parse_one(chunk)
        name = case.id or f"«{case.title}»"
        problems += [f"{name}: {e}" for e in errors]
        cases.append(case)
    if problems:
        raise ArtifactError("qa/cases.md: " + "; ".join(problems))
    return cases


def _vague(text: str) -> list[str]:
    low = text.lower()
    found = [w for w in VAGUE if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low)]
    if re.search(r"(?<!\w)успешно(?!\w)", low) and not DETAIL_RE.search(text):
        found.append("успешно")
    return found


def lint_case(case: Case) -> list[str]:
    errors = []
    if not case.title:
        errors.append("название: пусто")
    if case.kind not in KINDS:
        errors.append(f"вид: «{case.kind}» — допустимы {', '.join(KINDS)}")
    if case.priority not in PRIORITIES:
        errors.append(f"приоритет: «{case.priority}» — допустимы {', '.join(PRIORITIES)}")
    if not case.covers:
        errors.append("покрывает: пусто — укажи единицы U-xx")
    if not case.sources:
        errors.append("источник: пусто — укажи ID строк ТЗ ‹R-xx, IM-xx, D-xx›")
    if not case.description:
        errors.append("описание: пусто")
    if not case.preconditions:
        errors.append("предусловия: пусто")
    if not case.steps:
        errors.append("шаги: нет ни одного шага")
    for n, step in enumerate(case.steps, start=1):
        if any(STEP_RESULT_RE.fullmatch(line.strip()) for line in step.splitlines()[1:]):
            errors.append(f"шаги: шаг {n} — пустой результат «- Результат:»")
    if not case.expected:
        errors.append("ожидаемый результат: пусто")
    elif case.kind == "бэкенд" and not CODE_RE.search(case.expected) and not QA_PLACEHOLDER_RE.search(case.expected):
        errors.append("ожидаемый результат: у бэкенд-кейса нет кода ответа")
    for where, text in [*((f"шаг {n}", s) for n, s in enumerate(case.steps, start=1)), ("ожидаемый результат", case.expected)]:
        errors += [f"расплывчато: «{w}» — {where}; назови конкретное значение" for w in _vague(text)]
    return errors


def case_hash(case: Case) -> str:
    raw = "\n".join(line.rstrip() for line in case.raw.replace("\r\n", "\n").split("\n")).strip()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
