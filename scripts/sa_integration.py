"""Проверки ТЗ на интеграцию платёжного метода: таблицы DoR в BRD и строки справочников в «Доработках».

Поля DoR — по шаблону DoR интеграции (Confluence 80282060), оформление — по эталону 110167970.
Подключаются к секциям манифеста ключом addons: dor — к 01-brd, payment-method — к 03-changes.
"""
from __future__ import annotations

import re

from sa_artifacts import ArtifactError, Table, parse_tables

DOR_HEADING = "## Описание интеграции"
ARTICLE_HEADING = "## Данные для статьи «Платежные методы»"
DOR_COLUMNS = ["№", "Поле", "Значение", "Ответственный"]
DOR_FIELDS = (
    "Минимальный лимит транзакции (по терминалам)",
    "Максимальный лимит транзакции (по терминалам)",
    "Максимальный лимит день/месяц (по терминалам)",
    "Управление callback'ами",
    "Контакты сервиса",
    "Локализация платежных методов",
    "Ссылки и документация банка",
    "Терминалы и доступы",
    "Условия выбора карточного метода (для сервиса роутинга)",
    "Данные тестовой карты для оплаты",
    "Тестовая среда и доступы",
    "Продовая среда и доступы",
    "Комиссия для Продамуса / банковская комиссия",
    "Комиссия для мерчанта / комиссия Продамуса",
    "Доступные валюты заказа",
    "Доступные валюты авторизации",
    "Маркап",
    "На чьей стороне расчёт курсов валют",
    "Рекуррентные платежи",
    "PF1 aggregator_contract_number",
    "Особенности реализации на ПФ1 (для PF2xPF1)",
    "Финансовая сверка",
)
ARTICLE_FIELDS = {
    "Платежный провайдер": ("Code", "Name", "Type"),
    "Платежный метод": (
        "PaymentMethodCode", "MethodType", "Currency", "Title",
        "ShortDescription", "ShortDescriptionEoo", "FullDescription", "LogoUrl",
    ),
    "Additional_Settings": (),
}
GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# Поля-идентификаторы новых строк справочников: значение — GUID, «из БД ПФ1» или ⚠ вопрос.
ID_FIELDS = {"Id", "id", "ProviderId", "mapping_id", "PaymentMethodId", "GroupViewId", "ParentGroupViewId"}
ID_ALLOWED_RE = re.compile(r"из БД|null|⚠\s*Q-", re.I)
REQUIRED_TABLES = ("PaymentMethods", "PaymentMethodLocalizations")


def subsection(text: str, heading: str) -> str | None:
    """Текст подраздела от заголовка до следующего заголовка того же или старшего уровня."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = next((i for i, line in enumerate(lines) if line.strip() == heading), None)
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip()
        hashes = len(stripped) - len(stripped.lstrip("#"))
        if 0 < hashes <= level and stripped[hashes:hashes + 1] == " ":
            end = i
            break
    return "\n".join(lines[start + 1:end])


def _table(chunk: str, columns: list[str]) -> Table | None:
    for table in parse_tables(chunk):
        if table.header == columns:
            return table
    return None


def _plain(cell: str) -> str:
    """Ячейка без трассировки ‹…› и разметки."""
    return re.sub(r"‹[^›]*›", "", cell).replace("`", "").strip()


def dor_errors(text: str) -> list[str]:
    """Таблицы «Описание интеграции» и «Данные для статьи «Платежные методы»» в BRD."""
    errors: list[str] = []
    chunk = subsection(text, DOR_HEADING)
    if chunk is None:
        errors.append(f"нет подраздела «{DOR_HEADING[3:]}» — таблица DoR из {len(DOR_FIELDS)} строк (blocks/dor.md)")
    else:
        try:
            table = _table(chunk, DOR_COLUMNS)
        except ArtifactError as exc:
            table, errors = None, errors + [f"«{DOR_HEADING[3:]}»: {exc}"]
        if table is None:
            errors.append(f"«{DOR_HEADING[3:]}»: нет таблицы с колонками {' | '.join(DOR_COLUMNS)}")
        else:
            fields = [_plain(row["Поле"]) for row in table.rows]
            if fields != list(DOR_FIELDS):
                missing = [f for f in DOR_FIELDS if f not in fields]
                extra = [f for f in fields if f not in DOR_FIELDS]
                if missing:
                    errors.append(f"«{DOR_HEADING[3:]}»: нет строк {'; '.join(missing)}")
                if extra:
                    errors.append(f"«{DOR_HEADING[3:]}»: лишние строки {'; '.join(extra)}")
                if not missing and not extra:
                    errors.append(f"«{DOR_HEADING[3:]}»: строки не по порядку шаблона DoR")
            for row in table.rows:
                if not _plain(row["Значение"]):
                    errors.append(f"«{DOR_HEADING[3:]}»: пустое значение «{_plain(row['Поле'])}» — значение, «Нет» или ⚠ вопрос")
                if not _plain(row["Ответственный"]):
                    errors.append(f"«{DOR_HEADING[3:]}»: не указан ответственный за «{_plain(row['Поле'])}»")
    chunk = subsection(text, ARTICLE_HEADING)
    if chunk is None:
        errors.append(f"нет подраздела «{ARTICLE_HEADING[3:]}» — провайдер, метод и Additional_Settings (blocks/dor.md)")
        return errors
    try:
        table = _table(chunk, DOR_COLUMNS)
    except ArtifactError as exc:
        return errors + [f"«{ARTICLE_HEADING[3:]}»: {exc}"]
    if table is None:
        return errors + [f"«{ARTICLE_HEADING[3:]}»: нет таблицы с колонками {' | '.join(DOR_COLUMNS)}"]
    rows = {_plain(row["Поле"]): row["Значение"] for row in table.rows}
    for name, keys in ARTICLE_FIELDS.items():
        if name not in rows:
            errors.append(f"«{ARTICLE_HEADING[3:]}»: нет строки «{name}»")
            continue
        missing = [k for k in keys if not re.search(rf"`{k}`\s*:", rows[name])]
        if missing:
            errors.append(f"«{ARTICLE_HEADING[3:]}», «{name}»: нет полей {', '.join(missing)}")
    if "```json" not in chunk:
        errors.append(f"«{ARTICLE_HEADING[3:]}»: нет JSON Additional_Settings в блоке ```json")
    return errors


def payment_method_errors(text: str) -> list[str]:
    """Справочники платёжного метода в «Доработках»: таблицы поле — значение и GUID у новых строк."""
    errors: list[str] = []
    for name in REQUIRED_TABLES:
        if not re.search(rf"^`{name}`\s*$", text, re.M):
            errors.append(f"нет таблицы `{name}` (строка «`{name}`» и таблица «Поле | Значение» под ней, blocks/payment-method.md)")
    try:
        tables = parse_tables(text)
    except ArtifactError as exc:
        return errors + [str(exc)]
    for table in tables:
        if not table.header or table.header[0] != "Поле":
            continue
        for row in table.rows:
            field = _plain(row["Поле"])
            if field not in ID_FIELDS:
                continue
            for column in table.header[1:]:
                value = row[column]
                if not (GUID_RE.search(value) or ID_ALLOWED_RE.search(value)):
                    errors.append(
                        f"`{field}` = «{_plain(value)}» — у новой строки справочника GUID, «из БД ПФ1» или ⚠ вопрос"
                    )
    return errors


ADDON_CHECKS = {"dor": dor_errors, "payment-method": payment_method_errors}
