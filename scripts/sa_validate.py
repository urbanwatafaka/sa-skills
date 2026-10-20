"""Проверка артефактов задачи по схемам из shared/schemas/artifacts.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sa_artifacts import (
    GATEWAY_PATH_RE,
    ArtifactError,
    find_refs,
    find_table,
    is_id,
    parse_questions,
    parse_tables,
    ref_prefix,
    split_frontmatter,
)
from sa_draft import (
    CODE_REF_RE,
    DIAGRAM_RE,
    DIAGRAM_REF_RE,
    DTO_RE,
    APPROVALS,
    HEADER_KEYS,
    OPENAPI_RE,
    OPENAPI_REF_RE,
    dto_errors,
    openapi_errors,
    placeholders,
    item_refs,
    render_body,
    row_hashes,
    top_items,
    without_open_questions,
    section_path,
    stubs,
    task_manifest,
    trace_refs,
)
from sa_puml import kind_errors, step_ref_errors, structural_errors
from sa_review import COVERAGE_COLUMNS, REVIEW_COLUMNS, SEVERITIES, STATUSES, WHOLE, coverage
from sa_state import ACCESS_KEYS, ACCESS_MODES, ARTIFACTS, STAGES, TEMPLATE_RE, file_sha1, load_state

KINDS = {"процесс", "сервис", "модуль", "API", "Kafka", "БД", "роль", "UI", "конфиг"}
IMPACTS = {"новый", "изм.", "удал.", "?"}
IM_STATUSES = {"факт", "допущение"}
CONFIDENCE = {"высокая", "средняя", "низкая"}
CONFIDENCE_RANK = {"высокая": 2, "средняя": 1, "низкая": 0}
BRD_TYPES = {"функц.", "UI", "данные", "интеграция", "НФТ", "ограничение"}
EMPTY = {"", "—", "-"}

BRD_COLUMNS = ["ID", "Требование", "Тип"]
IMPACT_COLUMNS = ["ID", "Объект", "Вид", "Влияние", "← R", "Источник", "Статус", "Уверенность"]
DECISION_COLUMNS = ["ID", "← Q", "Решение", "Кто/где", "Дата"]
CONTEXT_COLUMNS = ["← IM", "Скоуп", "Комментарий"]
SCOPES = {"в скоупе", "вне скоупа", "?"}
CONTEXT_SECTIONS = ["## Цель", "## Границы"]
TEMPLATE_TYPES = {"feature", "integration"}
TRACE_KINDS = ("R", "IM", "D")

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
SHA1_RE = re.compile(r"[0-9a-f]{40}")


def _one_of(values: set[str]) -> str:
    return ", ".join(sorted(values))


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in ids:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.add(item)
    return duplicates


QA_PREFIXES = ("TC", "U", "QV")


def _unknown(refs: list[str], known: dict) -> list[str]:
    qa = [f"{r} (ID QA — в артефактах аналитика не используется)" for r in refs if ref_prefix(r) in QA_PREFIXES]
    return qa + [r for r in refs if r != "BRD" and known.get(ref_prefix(r)) is not None and r not in known[ref_prefix(r)]]


def _qa_question_ids(task_dir: Path) -> set[str]:
    """Q-QA из qa/questions.md: аналитик переносит ответ в decisions.md со ссылкой на вопрос QA."""
    path = task_dir / "qa" / "questions.md"
    if not path.exists():
        return set()
    try:
        return {q.id for q in parse_questions(path.read_text(encoding="utf-8")) if q.audience == "QA"}
    except ArtifactError:
        return set()  # формат qa/questions.md проверяет validate_qa


def validate_brd(text: str) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    for key in ("source", "fetched", "brd_complete", "missing"):
        if key not in meta:
            errors.append(f"во frontmatter нет ключа {key}")
    if "fetched" in meta and not DATE_RE.fullmatch(str(meta["fetched"])):
        errors.append("fetched должен быть в формате ГГГГ-ММ-ДД")
    if "brd_complete" in meta and not isinstance(meta["brd_complete"], bool):
        errors.append("brd_complete должен быть true или false")
    if "missing" in meta and not isinstance(meta["missing"], list):
        errors.append("missing должен быть списком вида [a, b]")
    if meta.get("brd_complete") is False and meta.get("missing") == []:
        errors.append("brd_complete: false, но missing пуст — укажи, чего не хватает")
    table = find_table(parse_tables(body), BRD_COLUMNS)
    if table is None:
        return errors + [f"нет таблицы с колонками {', '.join(BRD_COLUMNS)}"], None
    ids = [row["ID"] for row in table.rows]
    for row in table.rows:
        if not is_id("R", row["ID"]):
            errors.append(f"{row['ID']}: ID должен быть вида R-01")
        if row["Требование"] in EMPTY:
            errors.append(f"{row['ID']}: пустое требование")
        if row["Тип"] not in BRD_TYPES:
            errors.append(f"{row['ID']}: тип «{row['Тип']}» не из списка: {_one_of(BRD_TYPES)}")
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def validate_impact_map(text: str, known: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    if not isinstance(meta.get("index_used"), bool):
        errors.append("во frontmatter нужен index_used: true или false")
    if meta.get("confidence_cap") not in CONFIDENCE:
        errors.append(f"confidence_cap должен быть одним из: {_one_of(CONFIDENCE)}")
    if meta.get("index_used") is False and meta.get("confidence_cap") == "высокая":
        errors.append("index_used: false, но confidence_cap: высокая — без индекса не выше средняя")
    table = find_table(parse_tables(body), IMPACT_COLUMNS)
    if table is None:
        return errors + [f"нет таблицы с колонками {', '.join(IMPACT_COLUMNS)}"], None
    ids = [row["ID"] for row in table.rows]
    for row in table.rows:
        rid = row["ID"]
        if not is_id("IM", rid):
            errors.append(f"{rid}: ID должен быть вида IM-01")
        if row["Вид"] not in KINDS:
            errors.append(f"{rid}: вид «{row['Вид']}» не из списка: {_one_of(KINDS)}")
        if row["Влияние"] not in IMPACTS:
            errors.append(f"{rid}: влияние «{row['Влияние']}» не из списка: {_one_of(IMPACTS)}")
        if row["Статус"] not in IM_STATUSES:
            errors.append(f"{rid}: статус «{row['Статус']}» не из списка: {_one_of(IM_STATUSES)}")
        if row["Уверенность"] not in CONFIDENCE:
            errors.append(f"{rid}: уверенность «{row['Уверенность']}» не из списка: {_one_of(CONFIDENCE)}")
        cap = meta.get("confidence_cap")
        if (
            cap in CONFIDENCE
            and row["Уверенность"] in CONFIDENCE
            and CONFIDENCE_RANK[row["Уверенность"]] > CONFIDENCE_RANK[cap]
        ):
            errors.append(f"{rid}: уверенность выше потолка confidence_cap ({cap})")
        if row["Статус"] == "факт" and row["Источник"] in EMPTY:
            errors.append(f"{rid}: факт без источника — укажи источник или поменяй статус на допущение")
        refs = [r for r in find_refs(row["← R"]) if ref_prefix(r) == "R"]
        if not refs:
            errors.append(f"{rid}: нет ссылки на пункт BRD в колонке ← R")
        errors += [f"{rid}: ссылка на несуществующий {r}" for r in _unknown(refs, known)]
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def validate_questions(text: str, known: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    _, body = split_frontmatter(text)
    questions = parse_questions(body)
    for q in questions:
        if q.section == "":
            errors.append(f"{q.id}: вопрос вне секций «## Для PO» и «## Для аналитика»")
        elif q.section != q.audience:
            errors.append(f"{q.id}: лежит в секции {q.section}, а адресован {q.audience}")
        if not q.refs:
            errors.append(f"{q.id}: нет ссылки [R-xx] или [IM-xx]")
        if "BRD" in q.refs and q.audience != "PO":
            errors.append(f"{q.id}: ссылка [BRD] допустима только в вопросах PO")
        errors += [f"{q.id}: «{t}» — не ID и не BRD" for t in q.bad_refs]
        errors += [
            f"{q.id}: согласование «{a}» — ожидается {' или '.join(APPROVALS)}" for a in q.approval if a not in APPROVALS
        ]
        if q.answer and q.status == "obsolete":
            errors.append(f"{q.id}: «Ответ в ТЗ» у неактуального вопроса — убери строку или смени статус")
        errors += [f"{q.id}: ссылка на несуществующий {r}" for r in _unknown(q.refs, known)]
        if q.audience == "PO":
            found = list(dict.fromkeys(
                r for line in [q.text, *q.details] for r in find_refs(line) if ref_prefix(r) in {"R", "IM", "D", "RV"}
            ))
            if found:
                errors.append(
                    f"{q.id}: в тексте вопроса PO не должно быть ссылок {', '.join(found)} — оставь их только в [..] в начале"
                )
    ids = [q.id for q in questions]
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def validate_decisions(text: str, known: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    _, body = split_frontmatter(text)
    table = find_table(parse_tables(body), DECISION_COLUMNS)
    if table is None:
        return [f"нет таблицы с колонками {', '.join(DECISION_COLUMNS)}"], None
    ids = [row["ID"] for row in table.rows]
    for row in table.rows:
        did = row["ID"]
        if not is_id("D", did):
            errors.append(f"{did}: ID должен быть вида D-01")
        if row["← Q"] not in EMPTY:
            refs = [r for r in find_refs(row["← Q"]) if ref_prefix(r) == "Q"]
            if not refs:
                errors.append(f"{did}: в колонке ← Q ожидается Q-PO-xx, Q-SA-xx или —")
            errors += [f"{did}: ссылка на несуществующий {r}" for r in _unknown(refs, known)]
        if row["Решение"] in EMPTY:
            errors.append(f"{did}: пустое решение")
        if not DATE_RE.fullmatch(row["Дата"]):
            errors.append(f"{did}: дата должна быть в формате ГГГГ-ММ-ДД")
    errors += [f"{d}: ID повторяется" for d in _duplicates(ids)]
    return errors, set(ids)


def validate_context(text: str, known: dict, template: str | None) -> tuple[list[str], None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    value = meta.get("template")
    if not (isinstance(value, str) and TEMPLATE_RE.fullmatch(value)):
        errors.append("template: формат имя@мажор.минор, например feature@1.0")
    else:
        name = value.split("@")[0]
        if name not in TEMPLATE_TYPES:
            errors.append(f"template: тип {name} не из списка: feature, integration")
        if template is not None and value != template:
            errors.append(f"template {value} не совпадает с state.json ({template})")
    for key in ("release", "po"):
        if meta.get(key) in (None, ""):
            errors.append(f"во frontmatter нет ключа {key}")
    lines = {line.strip() for line in body.splitlines()}
    errors += [f"нет раздела «{section}»" for section in CONTEXT_SECTIONS if section not in lines]
    table = find_table(parse_tables(body), CONTEXT_COLUMNS)
    if table is None:
        return errors + [f"нет таблицы с колонками {', '.join(CONTEXT_COLUMNS)}"], None
    listed: list[str] = []
    for row in table.rows:
        refs = [r for r in find_refs(row["← IM"]) if ref_prefix(r) == "IM"]
        if len(refs) != 1:
            errors.append(f"«{row['← IM']}»: в колонке ← IM нужен ровно один IM-xx")
            continue
        rid = refs[0]
        listed.append(rid)
        if row["Скоуп"] not in SCOPES:
            errors.append(f"{rid}: скоуп «{row['Скоуп']}» не из списка: {_one_of(SCOPES)}")
        if row["Скоуп"] == "вне скоупа" and row["Комментарий"] in EMPTY:
            errors.append(f"{rid}: для «вне скоупа» нужна причина в колонке Комментарий")
        errors += [f"{rid}: ссылка на несуществующий {r}" for r in _unknown([rid], known)]
        if row["Скоуп"] == "?":
            q_refs = [r for r in find_refs(row["Комментарий"]) if ref_prefix(r) == "Q"]
            if not q_refs:
                errors.append(f"{rid}: для «?» укажи в Комментарии ID вопроса, который решит скоуп")
            errors += [f"{rid}: ссылка на несуществующий {r}" for r in _unknown(q_refs, known)]
    errors += [f"{d}: IM повторяется в «Границах»" for d in _duplicates(listed)]
    if known.get("IM") is not None:
        missing = sorted(known["IM"] - set(listed))
        errors += [f"{m}: пункт карты влияния не распределён в «Границах»" for m in missing]
    return errors, None


def _is_sha1(value) -> bool:
    return isinstance(value, str) and SHA1_RE.fullmatch(value) is not None


def validate_state(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task: нужна непустая строка с ключом задачи")
    if not (isinstance(data.get("stage"), str) and data["stage"] in STAGES):
        errors.append(f"stage: одно из {', '.join(STAGES)}")
    template = data.get("template")
    if template is not None and not (isinstance(template, str) and TEMPLATE_RE.fullmatch(template)):
        errors.append("template: формат имя@мажор.минор, например feature@1.0")
    version = data.get("plugin_version")
    if not (isinstance(version, str) and SEMVER_RE.fullmatch(version)):
        errors.append("plugin_version: формат x.y.z")

    inputs = data.get("inputs", {})
    if not isinstance(inputs, dict):
        errors.append("inputs: ожидается объект")
    else:
        for name, value in inputs.items():
            if name not in ARTIFACTS:
                errors.append(f"inputs: неизвестный артефакт {name}")
            if not _is_sha1(value):
                errors.append(f"inputs.{name}: ожидается sha1")

    sections = data.get("sections", {})
    if not isinstance(sections, dict):
        errors.append("sections: ожидается объект")
    else:
        for name, section in sections.items():
            section = section if isinstance(section, dict) else {}
            if not _is_sha1(section.get("hash")):
                errors.append(f"sections.{name}.hash: ожидается sha1")
            if not isinstance(section.get("edited_by_human"), bool):
                errors.append(f"sections.{name}.edited_by_human: true или false")
            if "generated" in section and not _is_sha1(section["generated"]):
                errors.append(f"sections.{name}.generated: ожидается sha1")

    rows = data.get("rows", {})
    if not isinstance(rows, dict):
        errors.append("rows: ожидается объект")
    else:
        for rid, value in rows.items():
            if not any(is_id(kind, rid) for kind in TRACE_KINDS):
                errors.append(f"rows: «{rid}» — не R-xx, IM-xx или D-xx")
            if not _is_sha1(value):
                errors.append(f"rows.{rid}: ожидается sha1")

    access = data.get("access", {})
    if not isinstance(access, dict):
        errors.append("access: ожидается объект")
    else:
        for key, mode in access.items():
            if not (isinstance(key, str) and key in ACCESS_KEYS):
                errors.append(f"access: неизвестный ключ {key}; допустимы {_one_of(ACCESS_KEYS)}")
            if not (isinstance(mode, str) and mode in ACCESS_MODES):
                errors.append(f"access.{key}: режим одно из {_one_of(ACCESS_MODES)}")

    published = data.get("published")
    if published is not None:
        if not isinstance(published, dict):
            errors.append("published: ожидается объект")
        else:
            if not (isinstance(published.get("url"), str) and published["url"].strip()):
                errors.append("published.url: непустая ссылка на страницу")
            if not _is_sha1(published.get("hash")):
                errors.append("published.hash: ожидается sha1")
            version = published.get("version")
            if version is not None and not (type(version) is int and version > 0):
                errors.append("published.version: целое число больше нуля")
    return errors


def _run(task_dir: Path, name: str, check, errors: list[str]) -> set[str] | None:
    path = task_dir / ARTIFACTS[name]
    if not path.exists():
        return None
    try:
        found, ids = check(path.read_text(encoding="utf-8"))
    except ArtifactError as exc:
        found, ids = [str(exc)], None
    errors.extend(f"{ARTIFACTS[name]}: {message}" for message in found)
    return ids


def _missing_impact_map_errors(task_dir: Path) -> list[str]:
    errors: list[str] = []
    brd = task_dir / ARTIFACTS["BRD"]
    if brd.exists():
        try:
            meta, _ = split_frontmatter(brd.read_text(encoding="utf-8"))
        except ArtifactError:
            meta = {}
        if meta.get("brd_complete") is True:
            errors.append("impact-map.md: нет файла, а BRD полный — карта влияния должна быть построена")
    gone = "но impact-map.md нет"
    questions = task_dir / ARTIFACTS["questions"]
    if questions.exists():
        try:
            _, body = split_frontmatter(questions.read_text(encoding="utf-8"))
            for q in parse_questions(body):
                errors += [
                    f"{ARTIFACTS['questions']}: {q.id}: ссылка на {r}, {gone}"
                    for r in q.refs if ref_prefix(r) == "IM"
                ]
        except ArtifactError:
            pass
    context = task_dir / ARTIFACTS["context"]
    if context.exists():
        try:
            _, body = split_frontmatter(context.read_text(encoding="utf-8"))
            table = find_table(parse_tables(body), CONTEXT_COLUMNS)
            for row in table.rows if table else []:
                errors += [
                    f"{ARTIFACTS['context']}: {r}: ссылка на {r}, {gone}"
                    for r in find_refs(row["← IM"]) if ref_prefix(r) == "IM"
                ]
        except ArtifactError:
            pass
    return errors


def _question_statuses(task_dir: Path) -> dict[str, str]:
    path = task_dir / ARTIFACTS["questions"]
    if not path.exists():
        return {}
    try:
        return {q.id: q.status for q in parse_questions(split_frontmatter(path.read_text(encoding="utf-8"))[1])}
    except ArtifactError:
        return {}


def validate_draft(task_dir: Path, state: dict, known: dict) -> list[str]:
    draft_dir = task_dir / "draft"
    draft_md = task_dir / ARTIFACTS["draft"]
    if not (draft_dir.is_dir() or draft_md.exists() or state.get("stage") in ("draft", "check", "done")):
        return []
    try:
        manifest = task_manifest(state)
    except ArtifactError as exc:
        return [f"draft: {exc}"]
    errors: list[str] = []
    statuses = _question_statuses(task_dir)
    names = {s.id for s in manifest.sections}
    if draft_dir.is_dir():
        errors += [
            f"draft/{p.name}: секции нет в шаблоне {manifest.name}"
            for p in sorted(draft_dir.glob("*.md")) if p.stem not in names
        ]
    complete = True
    for s in manifest.sections:
        path = section_path(task_dir, s.id)
        rel = f"draft/{s.id}.md"
        if not path.exists():
            if s.required:
                errors.append(f"{rel}: нет обязательной секции «{s.title}»")
                complete = False
            continue
        text = path.read_text(encoding="utf-8")
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first != s.heading:
            errors.append(f"{rel}: первая строка должна быть «{s.heading}»")
        for stub in stubs(text):
            errors.append(f"{rel}: заглушка «{stub}» — раздел или пункт без содержания не создаётся")
        for ref in CODE_REF_RE.findall(text):
            errors.append(f"{rel}: «{ref}» — ссылки на код остаются в артефактах задачи, не в ТЗ")
        changes = section_path(task_dir, "03-changes")
        limit = max(top_items(text), top_items(changes.read_text(encoding="utf-8")) if changes.exists() else 0)
        for number in dict.fromkeys(n for n in item_refs(text) if n > limit):
            errors.append(f"{rel}: «п.{number}» — такого пункта нет; номера пунктов при правке не сдвигай, ссылки сверь")
        for path in dict.fromkeys(m.group(0) for m in GATEWAY_PATH_RE.finditer(text)):
            errors.append(f"{rel}: «{path}…» — префикс шлюза; метод пиши, как он объявлен в сервисе")
        for token in trace_refs(text):
            if not any(is_id(kind, token) for kind in TRACE_KINDS):
                errors.append(f"{rel}: «{token}» в ‹…› — не R-xx, IM-xx или D-xx")
            elif token not in (known.get(ref_prefix(token)) or set()):
                errors.append(f"{rel}: ссылка на несуществующий {token}")
        for qid in placeholders(text):
            if qid is None:
                errors.append(f"{rel}: ⚠ без ID вопроса — пиши «⚠ Q-PO-xx» или «⚠ Q-SA-xx»")
            elif qid not in statuses:
                errors.append(f"{rel}: ⚠ {qid} — такого вопроса нет")
        for ref in DIAGRAM_RE.findall(text):
            if not DIAGRAM_REF_RE.fullmatch(ref):
                errors.append(f"{rel}: @diagram {ref} — путь вида diagrams/<имя>.puml")
                complete = False
            elif not (draft_dir / ref).exists():
                errors.append(f"{rel}: нет файла draft/{ref}")
                complete = False
        errors += [f"{rel}: {e}" for e in step_ref_errors(text, draft_dir)]
        for ref in OPENAPI_RE.findall(text):
            if not OPENAPI_REF_RE.fullmatch(ref):
                errors.append(f"{rel}: @openapi {ref} — путь вида api/<сервис>.yaml")
                complete = False
            elif not (draft_dir / ref).exists():
                errors.append(f"{rel}: нет файла draft/{ref}")
                complete = False
            else:
                errors += [f"draft/{ref}: {e}" for e in openapi_errors((draft_dir / ref).read_text(encoding="utf-8"))]
        for name in dict.fromkeys(DTO_RE.findall(text)):
            errors += [f"{rel}: {e}" for e in dto_errors(task_dir, name)]
    diagrams = draft_dir / "diagrams"
    for puml in sorted(diagrams.glob("*.puml")) if diagrams.is_dir() else []:
        puml_text = puml.read_text(encoding="utf-8")
        found = structural_errors(puml_text) + kind_errors(puml.name, puml_text)
        errors += [f"draft/diagrams/{puml.name}: {e}" for e in found]
    if not draft_md.exists():
        return errors + ["draft.md: нет файла — собери: sa_draft.py assemble tasks/<KEY>"]
    try:
        meta, body = split_frontmatter(draft_md.read_text(encoding="utf-8"))
    except ArtifactError as exc:
        return errors + [f"draft.md: {exc}"]
    errors += [f"draft.md: во frontmatter нет ключа {key}" for key in HEADER_KEYS if meta.get(key) in (None, "")]
    if meta.get("template") not in (None, "", state.get("template")):
        errors.append(f"draft.md: template {meta['template']} не совпадает с state.json ({state.get('template')})")
    if complete and without_open_questions(body).strip() != without_open_questions(
        render_body(task_dir, manifest, str(state.get("task", "")))
    ).strip():
        errors.append("draft.md: устарел или правился вручную — правь секции в draft/ и запусти sa_draft.py assemble")
    return errors


def validate_review(text: str, known: dict, task_dir: Path, state: dict) -> tuple[list[str], set[str] | None]:
    errors: list[str] = []
    meta, body = split_frontmatter(text)
    if not _is_sha1(meta.get("draft")):
        errors.append("draft: sha1 draft.md, по которому делалось ревью")
    if not DATE_RE.fullmatch(str(meta.get("reviewed", ""))):
        errors.append("reviewed должен быть в формате ГГГГ-ММ-ДД")
    round_ = meta.get("round")
    if not (isinstance(round_, int) and not isinstance(round_, bool) and round_ >= 1):
        errors.append("round: целое число ≥ 1")
    try:
        places: set[str] | None = {s.id for s in task_manifest(state).sections} | set(WHOLE)
    except ArtifactError:
        places = None
    tables = parse_tables(body)
    table = find_table(tables, REVIEW_COLUMNS)
    ids: set[str] | None = None
    if table is None:
        errors.append(f"нет таблицы замечаний с колонками {', '.join(REVIEW_COLUMNS)}")
    else:
        for row in table.rows:
            rid = row["ID"]
            if not is_id("RV", rid):
                errors.append(f"{rid}: ID должен быть вида RV-01")
            if row["Важность"] not in SEVERITIES:
                errors.append(f"{rid}: важность «{row['Важность']}» не из списка: {_one_of(set(SEVERITIES))}")
            if places is not None and row["Где"] not in places:
                errors.append(f"{rid}: где «{row['Где']}» — id секции шаблона, шапка или весь черновик")
            if row["Проблема"] in EMPTY:
                errors.append(f"{rid}: пустая проблема")
            if row["← Ссылка"] not in EMPTY:
                tokens = [t.strip() for t in row["← Ссылка"].split(",") if t.strip()]
                errors += [f"{rid}: «{t}» в ← Ссылка — не ID" for t in tokens if find_refs(t) != [t]]
                refs = [t for t in tokens if find_refs(t) == [t]]
                if row["Статус"] not in ("принято", "отклонено", "закрыто"):
                    errors += [f"{rid}: ссылка на несуществующий {r}" for r in _unknown(refs, known)]
            if row["Статус"] not in STATUSES:
                errors.append(f"{rid}: статус «{row['Статус']}» не из списка: {_one_of(set(STATUSES))}")
        ids_list = [row["ID"] for row in table.rows]
        errors += [f"{d}: ID повторяется" for d in _duplicates(ids_list)]
        ids = set(ids_list)
    matrix = find_table(tables, COVERAGE_COLUMNS)
    if matrix is None:
        return errors + [f"нет таблицы покрытия с колонками {', '.join(COVERAGE_COLUMNS)}"], ids
    listed = [row["R"] for row in matrix.rows]
    errors += [f"{d}: R повторяется в матрице покрытия" for d in _duplicates(listed)]
    draft = task_dir / ARTIFACTS["draft"]
    if draft.exists() and meta.get("draft") == file_sha1(draft):
        if known.get("R") is not None:
            errors += [f"{r}: нет в матрице покрытия" for r in sorted(known["R"] - set(listed))]
        expected = {r: (", ".join(s) or "—", ", ".join(a) or "—") for r, s, a in coverage(task_dir)}
        actual = {row["R"]: (row["Секции"], row["Истории"]) for row in matrix.rows}
        if any(actual[r] != expected[r] for r in actual if r in expected) or set(actual) - set(expected):
            errors.append("матрица покрытия не совпадает с черновиком — вставь вывод sa_review.py coverage")
    return errors, ids


QA_NEEDS_REASON = ("не поведение", "не тестируется", "нужно решение")


def validate_qa(task_dir: Path) -> list[str]:
    """Артефакты QA в qa/: формат кейсов, единиц и вопросов, дубли ID, Источник на строки ТЗ, причины статусов."""
    from sa_qa import CASES_FILE, QUESTIONS_FILE, STATE_FILE, load_cases, load_state
    from sa_qa_units import STATUSES as UNIT_STATUSES
    from sa_qa_units import UNITS_FILE, load_units

    if not (task_dir / "qa").is_dir():
        return []
    errors: list[str] = []
    try:
        cases = load_cases(task_dir)
    except ArtifactError as exc:
        errors.append(str(exc))
        cases = []
    try:
        known = set(row_hashes(task_dir))
    except ArtifactError:
        known = None
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            errors.append(f"{CASES_FILE}: {case.id} повторяется")
        seen.add(case.id)
        name = case.id or f"«{case.title}»"
        for token in case.sources:
            if token.startswith(("code:", "код:", "docs:")):
                continue
            if not any(is_id(kind, token) for kind in ("R", "IM", "D")):
                errors.append(f"{CASES_FILE}: {name}: Источник «{token}» — не ID R/IM/D, не code: и не docs:")
            elif known is not None and token not in known:
                errors.append(f"{CASES_FILE}: {name}: Источник {token} — нет такой строки в BRD, карте влияния или решениях")
    try:
        units = load_units(task_dir)
    except ArtifactError as exc:
        errors.append(f"{UNITS_FILE}: {exc}")
        units = []
    seen = set()
    for unit in units:
        if not is_id("U", unit.id):
            errors.append(f"{UNITS_FILE}: «{unit.id}» — не ID U-xx")
        elif unit.id in seen:
            errors.append(f"{UNITS_FILE}: {unit.id} повторяется")
        seen.add(unit.id)
        if unit.status not in UNIT_STATUSES:
            errors.append(f"{UNITS_FILE}: {unit.id}: статус «{unit.status}» — допустимы пусто, {', '.join(UNIT_STATUSES[1:])}")
        elif unit.status in QA_NEEDS_REASON and not unit.reason:
            errors.append(f"{UNITS_FILE}: {unit.id}: статус «{unit.status}» без причины")
    questions_path = task_dir / QUESTIONS_FILE
    if questions_path.exists():
        try:
            for q in parse_questions(questions_path.read_text(encoding="utf-8")):
                if q.audience != "QA":
                    errors.append(f"{QUESTIONS_FILE}: {q.id} — здесь только вопросы Q-QA-xx")
                elif q.section != "SA":
                    errors.append(f"{QUESTIONS_FILE}: {q.id} — должен лежать в секции «## Для аналитика»")
        except ArtifactError as exc:
            errors.append(f"{QUESTIONS_FILE}: {exc}")
    try:
        load_state(task_dir)
    except ValueError as exc:
        errors.append(f"{STATE_FILE}: не разбирается — {exc}")
    return errors


def validate_task(task_dir: Path) -> list[str]:
    try:
        state = load_state(task_dir)
    except ArtifactError as exc:
        return [f"state.json: {exc}"]
    errors = [f"state.json: {message}" for message in validate_state(state)]
    known: dict = {"R": None, "IM": None, "Q": None, "D": None}
    known["R"] = _run(task_dir, "BRD", validate_brd, errors)
    known["IM"] = _run(task_dir, "impact-map", lambda t: validate_impact_map(t, known), errors)
    known["Q"] = _run(task_dir, "questions", lambda t: validate_questions(t, known), errors)
    if known["Q"] is not None:
        known["Q"] = known["Q"] | _qa_question_ids(task_dir)
    template = state.get("template") if isinstance(state.get("template"), str) else None
    _run(task_dir, "context", lambda t: validate_context(t, known, template), errors)
    known["D"] = _run(task_dir, "decisions", lambda t: validate_decisions(t, known), errors)
    if not (task_dir / ARTIFACTS["impact-map"]).exists():
        errors += _missing_impact_map_errors(task_dir)
    errors += validate_draft(task_dir, state, known)
    if (task_dir / ARTIFACTS["review"]).exists():
        _run(task_dir, "review", lambda t: validate_review(t, known, task_dir, state), errors)
    elif state.get("stage") in ("check", "done"):
        errors.append("review.md: нет файла — запусти /tdd-check")
    errors += validate_qa(task_dir)
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("использование: sa_validate.py <папка задачи>", file=sys.stderr)
        return 2
    task_dir = Path(argv[0])
    errors = validate_task(task_dir)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {task_dir}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
