"""Черновик ТЗ: план секций, сборка draft.md, отчёт о пробелах."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import sa_puml
from sa_artifacts import GATEWAY_PATH_RE, ArtifactError, find_refs, find_table, parse_questions, parse_tables, split_frontmatter
from sa_state import ARTIFACTS, PUBLISH_FILE, file_sha1, load_state, save_state, write_atomic
from sa_template import Manifest, Section, load_manifest

TRACE_RE = re.compile(r"‹([^›]*)›")
TRACE_STRIP_RE = re.compile(r"[ \t]*‹[^›]*›")
PLACEHOLDER_RE = re.compile(r"⚠(?:[ \t]*(Q-(?:PO|SA)-\d{2,}))?")
DIAGRAM_RE = re.compile(r"^@diagram[ \t]+(\S+)[ \t]*$", re.M)
DIAGRAM_REF_RE = re.compile(r"diagrams/[A-Za-z0-9_.-]+\.puml")
OPENAPI_RE = re.compile(r"^@openapi[ \t]+(\S+)[ \t]*$", re.M)
OPENAPI_REF_RE = re.compile(r"api/[A-Za-z0-9_.-]+\.ya?ml")
DTO_RE = re.compile(r"\{\{DTO:([A-Za-z0-9_]+)\}\}")
STUB_RE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?(Не применимо|Изменения не требуются|Без изменений)(?![\w-])", re.M | re.I)
CODE_REF_RE = re.compile(r"(?<![\w-])(?:code|код):[ \t]*[\w./-]+:\d+")
ITEM_REF_RE = re.compile(r"(?<![\w.])п\.[ \t]?(\d+)\b")
TOP_ITEM_RE = re.compile(r"^(\d+)\.[ \t]", re.M)
API_PREFIXES = ("/api", "/backoffice", "/public", "/internal")
PREFIX_TAGS = {"/api": "Api", "/backoffice": "Backoffice", "/public": "Public", "/internal": "Internal"}
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}
QUESTION_MARK = ":question:"
OPEN_QUESTIONS = "# Открытые вопросы"
HEADER_KEYS = ("status", "author", "jira", "template", "assembled")
DEFAULT_JIRA_BASE = "https://jira.tasktracker.help"
APPROVALS = {"бизнес": "Бизнес", "архком": "Архитектурный комитет"}
DEFAULT_TASK_STATUS = "в аналитике"
NO_LINK = "Не требуется"
ROW_SOURCES = (
    ("BRD", ["ID", "Требование", "Тип"]),
    ("impact-map", ["ID", "Объект", "Вид", "Влияние", "← R"]),
    ("decisions", ["ID", "← Q", "Решение"]),
)
_CONTEXT_COLUMNS = ["← IM", "Скоуп", "Комментарий"]
_IN_SCOPE = ("в скоупе", "")


def trace_refs(text: str) -> list[str]:
    return [token.strip() for group in TRACE_RE.findall(text) for token in group.split(",") if token.strip()]


def placeholders(text: str) -> list[str | None]:
    return [match.group(1) for match in PLACEHOLDER_RE.finditer(text)]


def item_refs(text: str) -> list[int]:
    """Номера из ссылок «п.N» / «п. N» на пункты нумерованного списка."""
    return [int(n) for n in ITEM_REF_RE.findall(text)]


def top_items(text: str) -> int:
    """Наибольший номер пункта верхнего уровня (без отступа) в секции; 0 — нумерованных пунктов нет."""
    return max((int(n) for n in TOP_ITEM_RE.findall(text)), default=0)


def stubs(text: str) -> list[str]:
    return [match.group(1) for match in STUB_RE.finditer(text)]


def task_manifest(state: dict) -> Manifest:
    template = state.get("template")
    if not isinstance(template, str) or "@" not in template:
        raise ArtifactError("в state.json нет template — сначала /tdd-start")
    return load_manifest(template.split("@", 1)[0])


def section_path(task_dir: Path, section_id: str) -> Path:
    return task_dir / "draft" / f"{section_id}.md"


def present_sections(task_dir: Path, manifest: Manifest) -> list[Section]:
    return [s for s in manifest.sections if section_path(task_dir, s.id).exists()]


def _entries(state: dict) -> dict:
    sections = state.get("sections")
    return sections if isinstance(sections, dict) else {}


def is_human(entry: dict | None, path: Path) -> bool:
    """Секция правлена человеком: стоит отметка или файл не совпадает ни со сборкой, ни с последней записью плагина."""
    if not isinstance(entry, dict):
        return False
    if entry.get("edited_by_human"):
        return True
    known = {entry.get("hash"), entry.get("generated")} - {None}
    return bool(known) and file_sha1(path) not in known


def _claim(task_dir: Path, section_ids: list[str], force: bool) -> None:
    state = load_state(task_dir)
    manifest = task_manifest(state)
    names = {s.id for s in manifest.sections}
    sections = _entries(state)
    for sid in section_ids:
        if sid not in names:
            raise ArtifactError(f"секции {sid} нет в шаблоне {manifest.name}")
        path = section_path(task_dir, sid)
        if not path.exists():
            raise ArtifactError(f"нет файла draft/{sid}.md")
        entry = sections.get(sid) if isinstance(sections.get(sid), dict) else {}
        if entry.get("edited_by_human") and not force:
            raise ArtifactError(
                f"{sid}: правка человека — не перезаписывай; снять отметку можно только по слову аналитика: "
                f"sa_draft.py release <папка задачи> {sid}"
            )
        sha = file_sha1(path)
        sections[sid] = {"hash": entry.get("hash", sha), "edited_by_human": False, "generated": sha}
    state["sections"] = sections
    save_state(task_dir, state)


def mark(task_dir: Path, section_ids: list[str]) -> None:
    """Секцию записал плагин — не считать её правкой человека."""
    _claim(task_dir, section_ids, force=False)


def release(task_dir: Path, section_ids: list[str]) -> None:
    """Снять отметку правки человека — только по слову аналитика."""
    _claim(task_dir, section_ids, force=True)


def section_texts(task_dir: Path, manifest: Manifest) -> dict[str, str]:
    return {
        s.id: section_path(task_dir, s.id).read_text(encoding="utf-8")
        for s in manifest.sections if section_path(task_dir, s.id).exists()
    }


def block_section(manifest: Manifest, block: str) -> str | None:
    return next((s.id for s in manifest.sections if s.block == block), None)


def context_meta(task_dir: Path) -> dict:
    path = task_dir / ARTIFACTS["context"]
    if not path.exists():
        return {}
    try:
        return split_frontmatter(path.read_text(encoding="utf-8"))[0]
    except ArtifactError:
        return {}


def doc_title(task_dir: Path, manifest: Manifest, task: str) -> str:
    title = context_meta(task_dir).get("title")
    return str(title) if title else f"{manifest.title}: {task}"


def _block(lines: list[str], key: str) -> list[str] | None:
    """Строки с отступом под ключом верхнего уровня YAML или None, если ключа нет."""
    for number, line in enumerate(lines):
        if not line[:1].isspace() and line.split(":", 1)[0].strip() == key:
            body = []
            for nested in lines[number + 1:]:
                if nested.strip() and not nested[:1].isspace():
                    break
                body.append(nested)
            return body
    return None


def openapi_errors(text: str) -> list[str]:
    lines = text.splitlines()
    errors: list[str] = []
    if "openapi: 3.0.3" not in (line.strip() for line in lines if not line[:1].isspace()):
        errors.append("нет шапки «openapi: 3.0.3»")
    info = [line.strip() for line in _block(lines, "info") or []]
    title = next((line.split(":", 1)[1].strip().strip("'\"") for line in info if line.startswith("title:")), "")
    if not title:
        errors.append("нет info.title")
    elif not title.endswith(".Api"):
        errors.append(f"info.title «{title}» — ожидается <Namespace сервиса>.Api")
    if not any(line.startswith("version:") for line in info):
        errors.append("нет info.version")
    paths_block = _block(lines, "paths")
    if paths_block is None:
        return errors + ["нет paths"]
    indents = [len(line) - len(line.lstrip()) for line in paths_block if line.strip()]
    step = min(indents) if indents else 0
    paths = [
        line.strip()[:-1].strip("'\"")
        for line in paths_block
        if line.strip() and len(line) - len(line.lstrip()) == step and line.rstrip().endswith(":")
    ]
    if not paths:
        errors.append("в paths нет методов")
    for path in paths:
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in API_PREFIXES):
            errors.append(f"путь {path} без префикса /api, /backoffice, /public или /internal")
        elif GATEWAY_PATH_RE.match(path):
            errors.append(f"путь {path} с префиксом шлюза — пиши путь, как он объявлен в сервисе")
    errors += _tag_errors(paths_block, step)
    return errors


def _tag_errors(paths_block: list[str], step: int) -> list[str]:
    """Тег операции совпадает с разделом по префиксу пути: /api → Api, /backoffice → Backoffice и т.д."""
    errors: list[str] = []
    path, method, method_indent, in_tags = "", "", 0, False
    for line in paths_block:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        text = line.strip()
        if indent == step and text.endswith(":"):
            path, method, in_tags = text[:-1].strip("'\""), "", False
            continue
        key = text.split(":", 1)[0].strip().lower()
        if indent > step and key in HTTP_METHODS and text.endswith(":"):
            method, method_indent, in_tags = key, indent, False
            continue
        if not method or indent <= method_indent:
            in_tags = False
            continue
        tags: list[str] = []
        if text.startswith("tags:"):
            value = text[5:].strip()
            if value.startswith("["):
                tags = [t.strip().strip("'\"") for t in value.strip("[]").split(",") if t.strip()]
            in_tags = not value
        elif in_tags and text.startswith("- "):
            tags = [text[2:].strip().strip("'\"")]
        else:
            in_tags = False
        expected = next((tag for prefix, tag in PREFIX_TAGS.items() if path == prefix or path.startswith(prefix + "/")), None)
        for tag in tags:
            if expected and tag != expected:
                errors.append(f"{method.upper()} {path}: тег {tag}, а по префиксу пути — {expected}")
    return errors


def dto_errors(task_dir: Path, name: str) -> list[str]:
    path = task_dir / "draft" / "dto" / f"{name}.json"
    if not path.exists():
        return [f"нет файла draft/dto/{name}.json для {{{{DTO:{name}}}}}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"draft/dto/{name}.json: невалидный JSON ({exc})"]
    if not isinstance(data, dict) or "$type" not in data:
        return [f"draft/dto/{name}.json: нет поля $type"]
    return []


def _diagram(task_dir: Path, rel: str) -> str:
    path = task_dir / "draft" / rel
    if not DIAGRAM_REF_RE.fullmatch(rel) or not path.exists():
        raise ArtifactError(f"нет диаграммы draft/{rel}")
    return "```plantuml\n" + path.read_text(encoding="utf-8").strip() + "\n```"


def _openapi(task_dir: Path, rel: str) -> str:
    path = task_dir / "draft" / rel
    if not OPENAPI_REF_RE.fullmatch(rel) or not path.exists():
        raise ArtifactError(f"нет OpenAPI draft/{rel}")
    return "```openapi\n" + path.read_text(encoding="utf-8").strip() + "\n```"


def open_questions(task_dir: Path, publish: bool = False) -> str:
    path = task_dir / ARTIFACTS["questions"]
    if not path.exists():
        return ""
    body = split_frontmatter(path.read_text(encoding="utf-8"))[1]
    questions = [q for q in parse_questions(body) if q.status == "open" or (q.status == "answered" and q.answer)]
    if not questions:
        return ""
    items = []
    for number, q in enumerate(questions, start=1):
        text = q.text if publish else f"**{q.id}** {q.text}"
        if q.approval:
            who = ", ".join(APPROVALS.get(a, a) for a in q.approval)
            text += f"<br/>❗**Требует согласования:** {who}"
        answer = f" {q.answer}" if q.answer else ""
        items.append(f"{number}. {text}<br/>**Ответ**:{answer}")
    return OPEN_QUESTIONS + "\n\n" + "\n".join(items)


def without_open_questions(text: str) -> str:
    """Тело черновика без раздела «Открытые вопросы»: его собирают из questions.md, и ответы в /tdd-clarify
    не должны делать черновик устаревшим."""
    marker = "\n" + OPEN_QUESTIONS + "\n"
    head, found, _ = text.partition(marker)
    return head if found else text


def render_body(task_dir: Path, manifest: Manifest, task: str, publish: bool = False) -> str:
    parts = [f"# {doc_title(task_dir, manifest, task)}"]
    for section in present_sections(task_dir, manifest):
        text = section_path(task_dir, section.id).read_text(encoding="utf-8").strip()
        text = DIAGRAM_RE.sub(lambda m: _diagram(task_dir, m.group(1)), text)
        text = OPENAPI_RE.sub(lambda m: _openapi(task_dir, m.group(1)), text)
        if publish:
            text = TRACE_STRIP_RE.sub("", text)
            text = PLACEHOLDER_RE.sub(QUESTION_MARK, text)
        if section.level > 1:
            parts.append("---")
        parts.append(text)
    questions = open_questions(task_dir, publish)
    if questions:
        parts.append(questions)
    return "\n\n".join(parts) + "\n"


def jira_url(task: str) -> str:
    """Голый URL задачи из ключа: Confluence разворачивает его в виджет."""
    if not task:
        return NO_LINK
    base = (os.environ.get("JIRA_BASE_URL") or DEFAULT_JIRA_BASE).rstrip("/")
    return f"{base}/browse/{task}"


def statuses_table(task_dir: Path, task: str, author: str) -> str:
    ctx = context_meta(task_dir)
    rows = [
        ("Статус задачи", ctx.get("task_status") or DEFAULT_TASK_STATUS),
        ("Автор документа", author),
        ("Jira ссылка", ctx.get("jira") or jira_url(task)),
        ("Ссылка на дизайн", ctx.get("design") or NO_LINK),
    ]
    return "| Параметр | Значение |\n|---|---|\n" + "\n".join(f"| {key} | {value} |" for key, value in rows)


def assemble(task_dir: Path, author: str | None = None, today: date | None = None) -> list[Path]:
    state = load_state(task_dir)
    manifest = task_manifest(state)
    missing = [s.id for s in manifest.sections if s.required and not section_path(task_dir, s.id).exists()]
    if missing:
        raise ArtifactError(f"нет обязательных секций: {', '.join(missing)}")
    draft = task_dir / ARTIFACTS["draft"]
    if not author and draft.exists():
        author = split_frontmatter(draft.read_text(encoding="utf-8"))[0].get("author")
    if not author:
        raise ArtifactError("укажи автора: sa_draft.py assemble <папка задачи> <автор>")
    if any(ch in author for ch in "\n\r|"):
        raise ArtifactError("автор: без переводов строки и символа |")
    task = str(state.get("task", ""))
    meta = {
        "status": "черновик",
        "author": author,
        "jira": task,
        "template": state["template"],
        "assembled": (today or date.today()).isoformat(),
    }
    header = "---\n" + "".join(f"{key}: {value}\n" for key, value in meta.items()) + "---\n"
    body = render_body(task_dir, manifest, task)
    title, rest = render_body(task_dir, manifest, task, publish=True).split("\n\n", 1)
    statuses = statuses_table(task_dir, task, author)
    write_atomic(draft, header + body)
    publish = task_dir / PUBLISH_FILE
    write_atomic(
        publish,
        f"{title}\n\n:::expand Оглавление\n{{{{toc}}}}\n:::\n\n---\n\n**Статусы**\n\n{statuses}\n\n---\n\n{rest}",
    )
    prior = _entries(state)
    sections = {}
    for s in present_sections(task_dir, manifest):
        path = section_path(task_dir, s.id)
        sections[s.id] = {"hash": file_sha1(path), "edited_by_human": is_human(prior.get(s.id), path)}
    state["sections"] = sections
    state["rows"] = row_hashes(task_dir)
    save_state(task_dir, state)
    return [draft, publish]


def _body(task_dir: Path, name: str) -> str:
    path = task_dir / ARTIFACTS[name]
    return split_frontmatter(path.read_text(encoding="utf-8"))[1] if path.exists() else ""


def _rows(body: str, columns: list[str]) -> list[dict[str, str]]:
    table = find_table(parse_tables(body), columns)
    return table.rows if table else []


def task_data(task_dir: Path) -> dict:
    scope: dict[str, tuple[str, str]] = {}
    for row in _rows(_body(task_dir, "context"), _CONTEXT_COLUMNS):
        for ref in find_refs(row["← IM"]):
            if ref.startswith("IM-"):
                scope[ref] = (row["Скоуп"], row["Комментарий"])
    return {
        "brd": [row["ID"] for row in _rows(_body(task_dir, "BRD"), ["ID", "Требование", "Тип"])],
        "impact": _rows(_body(task_dir, "impact-map"), ["ID", "Вид", "Влияние", "← R"]),
        "scope": scope,
        "questions": parse_questions(_body(task_dir, "questions")),
        "decisions": _rows(_body(task_dir, "decisions"), ["ID", "← Q", "Решение"]),
    }


def row_hashes(task_dir: Path) -> dict[str, str]:
    """Снимок строк BRD, карты и решений на момент сборки: по нему /tdd-update видит, что изменилось."""
    hashes: dict[str, str] = {}
    for name, columns in ROW_SOURCES:
        for row in _rows(_body(task_dir, name), columns):
            text = " | ".join(row[column] for column in columns)
            hashes[row["ID"]] = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return hashes


def scope_of(data: dict, im_id: str) -> str:
    return data["scope"].get(im_id, ("в скоупе", ""))[0]


def untraced_impacts(data: dict, traced: set[str], scopes: tuple[str, ...] = ("в скоупе",)) -> list[str]:
    return [
        row["ID"] for row in data["impact"]
        if row["Влияние"] in ("новый", "изм.") and scope_of(data, row["ID"]) in scopes and row["ID"] not in traced
    ]


def _slice(section: Section, data: dict) -> tuple[list[str], list[str], list[str]]:
    rows = [row for row in data["impact"] if scope_of(data, row["ID"]) != "вне скоупа"]
    if section.im_kinds:
        rows = [row for row in rows if row["Вид"] in section.im_kinds]
        linked = {r for row in rows for r in find_refs(row["← R"]) if r.startswith("R-")}
        r_ids = [r for r in data["brd"] if r in linked]
    else:
        r_ids = list(data["brd"])
    im_ids = [row["ID"] for row in rows]
    keys = set(r_ids) | set(im_ids)
    q_refs = {q.id: set(q.refs) for q in data["questions"]}
    d_ids = []
    for row in data["decisions"]:
        q_ids = [r for r in find_refs(row["← Q"]) if r.startswith("Q-")]
        if not q_ids or any(q not in q_refs or q_refs[q] & keys for q in q_ids):
            d_ids.append(row["ID"])
    return r_ids, im_ids, d_ids


def _fmt(ids: list[str]) -> str:
    return ", ".join(ids) if ids else "—"


def plan(task_dir: Path) -> str:
    state = load_state(task_dir)
    manifest = task_manifest(state)
    data = task_data(task_dir)
    sections = _entries(state)
    lines = [f"Шаблон: {manifest.name}@{manifest.version} — {manifest.title}"]
    if state["template"] != f"{manifest.name}@{manifest.version}":
        lines.append(f"ВНИМАНИЕ: в state.json {state['template']}, а манифест {manifest.name}@{manifest.version}")
    changed = False
    for s in manifest.sections:
        path = section_path(task_dir, s.id)
        entry = sections.get(s.id) if isinstance(sections.get(s.id), dict) else None
        if not path.exists():
            status = "нет" if s.required else "нет — без содержания не создаётся"
        elif is_human(entry, path):
            if not entry.get("edited_by_human"):
                entry["edited_by_human"] = True
                changed = True
            status = "правка человека — не перезаписывать"
        else:
            status = "есть"
        block = f"blocks/{s.block}.md" if s.block else "—"
        kind = "обязательная" if s.required else "необязательная"
        lines.append(f"{s.id} | {s.title} | {kind} | блок: {block} | диаграммы: {_fmt(s.diagrams)} | {status}")
        r_ids, im_ids, d_ids = _slice(s, data)
        lines.append(f"  R: {_fmt(r_ids)} · IM: {_fmt(im_ids)} · D: {_fmt(d_ids)}")
    if changed:
        state["sections"] = sections
        save_state(task_dir, state)
    return "\n".join(lines)


def _fmt_none(items: list[str]) -> str:
    return ", ".join(items) if items else "нет"


def gaps(task_dir: Path) -> str:
    state = load_state(task_dir)
    manifest = task_manifest(state)
    data = task_data(task_dir)
    texts = section_texts(task_dir, manifest)
    missing = [s.id for s in manifest.sections if s.required and s.id not in texts]
    skipped = [s.id for s in manifest.sections if not s.required and s.id not in texts]
    lines = [f"Нет обязательных секций: {', '.join(missing)}" if missing else "Обязательные секции: все на месте"]
    lines.append(f"Необязательные не созданы: {_fmt_none(skipped)}")
    marks = []
    for sid, text in texts.items():
        ids = list(dict.fromkeys(qid or "без ID" for qid in placeholders(text)))
        if ids:
            marks.append(f"{sid} ({', '.join(ids)})")
    lines.append("Плейсхолдеры ⚠: " + ("; ".join(marks) if marks else "нет"))
    closed = {q.id for q in data["questions"] if q.status != "open"}
    closed_marks = []
    for sid, text in texts.items():
        ids = list(dict.fromkeys(qid for qid in placeholders(text) if qid in closed))
        if ids:
            closed_marks.append(f"{sid} ({', '.join(ids)})")
    lines.append("Плейсхолдеры на закрытые вопросы: " + ("; ".join(closed_marks) if closed_marks else "нет"))
    blocking = [q.id for q in data["questions"] if q.status == "open" and q.blocking]
    lines.append(f"Открытые блокирующие вопросы: {_fmt_none(blocking)}")
    unresolved = [f"{im} ({comment})" for im, (scope, comment) in data["scope"].items() if scope == "?"]
    lines.append(f"Нерешённый скоуп: {_fmt_none(unresolved)}")
    traced = {ref for text in texts.values() for ref in trace_refs(text)}
    lines.append(f"R без трассировки: {_fmt_none([r for r in data['brd'] if r not in traced])}")
    untraced = untraced_impacts(data, traced)
    lines.append(f"IM (новый/изм., в скоупе) без трассировки: {_fmt_none(untraced)}")
    lines.append(f"Заглушки вместо содержания: {_fmt_none([sid for sid, text in texts.items() if stubs(text)])}")
    diagrams_dir = task_dir / "draft" / "diagrams"
    diagrams = sorted(diagrams_dir.glob("*.puml")) if diagrams_dir.is_dir() else []
    if diagrams:
        errors, mode = sa_puml.check_files(diagrams)
        lines.append(f"Диаграммы: {len(diagrams)}, проверка: {mode}")
        lines += [f"  {e}" for e in errors]
    else:
        lines.append("Диаграммы: нет")
    return "\n".join(lines)


USAGE = (
    "использование:\n"
    "  sa_draft.py plan <папка задачи>\n"
    "  sa_draft.py assemble <папка задачи> [автор]\n"
    "  sa_draft.py gaps <папка задачи>\n"
    "  sa_draft.py mark <папка задачи> <секция>...\n"
    "  sa_draft.py release <папка задачи> <секция>..."
)
ARITY = {"plan": (2, 2), "assemble": (2, 3), "gaps": (2, 2), "mark": (3, 99), "release": (3, 99)}


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if command not in ARITY or not ARITY[command][0] <= len(argv) <= ARITY[command][1]:
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "plan":
            print(plan(task_dir))
        elif command == "assemble":
            paths = assemble(task_dir, argv[2] if len(argv) == 3 else None)
            print("собраны: " + ", ".join(p.name for p in paths))
        elif command == "mark":
            mark(task_dir, argv[2:])
            print("отмечены: " + ", ".join(argv[2:]))
        elif command == "release":
            release(task_dir, argv[2:])
            print("сняты отметки правки человека: " + ", ".join(argv[2:]))
        else:
            print(gaps(task_dir))
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
