"""Глобальный индекс системы из docs/sa-index/ сервисов: system_tech.md, bctc.md, AGENTS.md."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from sa_artifacts import ArtifactError
from sa_index import DOCS, EMPTY, load_stamp, read_doc
from sa_state import write_atomic

GENERATED_PREFIX = "<!-- Собрано sa_index.py aggregate"
GLOBAL_FILES = ("system_tech.md", "bctc.md", "AGENTS.md")
PARAM_RE = re.compile(r"\$\{[^}]*\}|\{[^}/]*\}|:[A-Za-z_]\w*")
NL = "\n"


def _generated(today: str) -> str:
    return f"{GENERATED_PREFIX} {today}. Не править вручную: файл пересобирает /sa-index-docs. -->"


def http_key(value: str) -> str:
    parts = value.split(None, 1)
    if len(parts) != 2:
        return value.strip().lower()
    path = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/?#]*", "", parts[1].strip()).split("#")[0].split("?")[0]
    path = PARAM_RE.sub("{}", path).rstrip("/") or "/"
    return f"{parts[0].upper()} {path}"


def _rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if next(iter(row.values())) != EMPTY]


def load_services(repos_root: Path, services: list[str]) -> tuple[dict[str, dict], list[str]]:
    docs: dict[str, dict] = {}
    warnings = []
    for service in services:
        repo = repos_root / service
        loaded = {}
        for name in ("tech.md", "bctc.md"):
            if not (repo / DOCS / name).is_file():
                continue
            try:
                loaded[name] = read_doc(repo, name)
            except ArtifactError as exc:
                warnings.append(f"{service}: {exc} — файл пропущен")
        docs[service] = loaded
    return docs, warnings


def _table(header: list[str], rows: list[str]) -> str:
    empty = "| нет |" + " — |" * (len(header) - 1)
    lines = [f"| {' | '.join(header)} |", "|" + "---|" * len(header), *(rows or [empty])]
    return NL.join(lines) + NL


def system_tech(docs: dict[str, dict], today: str) -> str:
    providers = []  # (сервис, отображение, ключ, назначение, через)
    calls = []      # (сервис, куда или None, отображение, ключ, назначение)
    unclear = []    # сообщения с неясным направлением
    for service, loaded in docs.items():
        tech = loaded.get("tech.md")
        if not tech:
            continue
        for row in _rows(tech["API"]):
            shown = f"{row['Метод']} {row['Путь']}"
            providers.append((service, shown, ("HTTP", http_key(shown)), row["Назначение"], "HTTP"))
        for row in _rows(tech["Исходящие вызовы"]):
            shown = row["Метод или топик"]
            calls.append((service, row["Куда"], shown, ("HTTP", http_key(shown)), row["Назначение"]))
        for row in _rows(tech["Сообщения"]):
            shown = f"{row['Брокер']}: {row['Топик или очередь']}"
            key = (row["Брокер"].lower(), row["Топик или очередь"])
            if row["Направление"] == "публикует":
                providers.append((service, shown, key, row["Когда"], row["Брокер"]))
            elif row["Направление"] == "читает":
                calls.append((service, None, shown, key, row["Когда"]))
            else:
                unclear.append(f"| ? | {shown} | {service} | {row['Когда']} — направление неясно |")
    rows, links, matched = [], set(), set()
    users_by = [set() for _ in providers]
    for pi, (provider, shown, key, purpose, via) in enumerate(providers):
        for index, (consumer, target, _, call_key, _) in enumerate(calls):
            if call_key == key and target in (None, provider) and consumer != provider:
                users_by[pi].add(consumer)
                matched.add(index)
                links.add((consumer, provider, via) if via == "HTTP" else (provider, consumer, via))
    for index, (consumer, target, _, call_key, _) in enumerate(calls):
        if not (target and target.startswith("?")):
            continue
        hits = [pi for pi, p in enumerate(providers)
                if p[4] == "HTTP" and p[2] == call_key and p[0] != consumer]
        if len({providers[pi][0] for pi in hits}) != 1:
            continue
        matched.add(index)
        for pi in hits:
            users_by[pi].add("? " + consumer)
        links.add((consumer, providers[hits[0]][0], "HTTP ?"))
    for pi, (provider, shown, _, purpose, _) in enumerate(providers):
        rows.append(f"| {provider} | {shown} | {', '.join(sorted(users_by[pi])) or '—'} | {purpose} |")
    rows += unclear
    for index, (consumer, target, shown, _, purpose) in enumerate(calls):
        if index in matched:
            continue
        label = target or "не найден"
        if not label.startswith("?"):
            label = "? " + label
        rows.append(f"| {label} | {shown} | {consumer} | {purpose} |")
        if target:
            links.add((consumer, target, "HTTP"))
    link_rows = [f"| {a} | {b} | {via} |" for a, b, via in sorted(links)]
    return (
        f"{_generated(today)}{NL}# API и сообщения{NL}{NL}"
        + _table(["Поставщик", "Метод или топик", "Потребители", "Назначение"], rows)
        + f"{NL}## Связи C2{NL}{NL}"
        + _table(["Из", "В", "Через"], link_rows)
    )


def system_bctc(docs: dict[str, dict], today: str) -> str:
    scenarios: dict[str, dict] = {}
    for service, loaded in docs.items():
        bctc = loaded.get("bctc.md")
        if not bctc:
            continue
        for row in _rows(bctc["Сценарии"]):
            entry = scenarios.setdefault(row["Сценарий"], {"domains": [], "services": set()})
            if row["Домен"] not in entry["domains"]:
                entry["domains"].append(row["Домен"])
            entry["services"].add(service)
    rows = [
        f"| {name} | {' / '.join(entry['domains'])} | {', '.join(sorted(entry['services']))} |"
        for name, entry in sorted(scenarios.items())
    ]
    return f"{_generated(today)}{NL}# Сценарии и сервисы{NL}{NL}" + _table(["Сценарий", "Домен", "Сервисы"], rows)


def agents_md(repos_root: Path, services: list[str], today: str) -> str:
    rows = []
    for service in services:
        data = load_stamp(repos_root / service)
        sha = (data.get("sha") or "—")[:7]
        rows.append(f"| {service} | {sha} | {data.get('indexed', 'нет')} |")
    where = [
        "| system_tech.md | Сводная таблица API и сообщений: поставщик, потребители; связи C2 |",
        "| bctc.md | Сценарии → домен → сервисы |",
        "| <сервис>/docs/sa-index/tech.md | API, исходящие вызовы, сообщения, фоновые задачи сервиса со ссылками файл:строка |",
        "| <сервис>/docs/sa-index/DB.md | Таблицы и связи сервиса |",
        "| <сервис>/docs/sa-index/bctc.md | Домены и сценарии сервиса |",
        "| <сервис>/docs/sa-index/.sa-index.json | SHA и дата последней индексации |",
    ]
    rules = [
        "- После значимых изменений сервиса запустите `/sa-index-docs <сервис>`: перечитываются только файлы, изменённые с SHA последней индексации.",
        "- Руками правьте только `docs/sa-index/` сервисов; файлы этой папки пересобираются из них.",
        "- Ячейки, начинающиеся с `?`, — неоднозначности: проверьте и снимите знак.",
        "- Строка с поставщиком `? <имя>` — вызов, для которого не найден метод у поставщика или поставщик не проиндексирован.",
    ]
    return (
        f"{_generated(today)}{NL}# Индекс системы{NL}{NL}## Где что лежит{NL}{NL}"
        + _table(["Файл", "Что внутри"], where)
        + f"{NL}## Сервисы{NL}{NL}"
        + _table(["Сервис", "SHA", "Проиндексирован"], rows)
        + f"{NL}## Правила актуализации{NL}{NL}" + NL.join(rules) + NL
    )


def aggregate(
    repos_root: Path, index_dir: Path, services: list[str], today: date | None = None, force: bool = False,
) -> tuple[list[str], list[str]]:
    stamp_day = (today or date.today()).isoformat()
    docs, warnings = load_services(repos_root, services)
    texts = {
        "system_tech.md": system_tech(docs, stamp_day),
        "bctc.md": system_bctc(docs, stamp_day),
        "AGENTS.md": agents_md(repos_root, services, stamp_day),
    }
    index_dir.mkdir(parents=True, exist_ok=True)
    refused = []
    for name in GLOBAL_FILES:
        path = index_dir / name
        if path.is_file() and not force and not path.read_text(encoding="utf-8", errors="replace").startswith(GENERATED_PREFIX):
            refused.append(name)
            continue
        write_atomic(path, texts[name])
    return warnings, refused
