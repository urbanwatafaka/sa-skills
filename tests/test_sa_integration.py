import pytest

from sa_integration import DOR_FIELDS, dor_errors, payment_method_errors, subsection

ROW = "| {n} | {field} | Значение. ‹R-01› | PO |"


def _brd(fields=DOR_FIELDS, article=True, json_block=True) -> str:
    rows = "\n".join(ROW.format(n=i, field=f) for i, f in enumerate(fields, start=1))
    text = (
        "# BRD\n\n## Контекст/Проблема\n\nТекст. ‹R-01›\n\n"
        "## Описание интеграции\n\n| № | Поле | Значение | Ответственный |\n|---|---|---|---|\n" + rows + "\n\n"
    )
    if article:
        text += (
            "## Данные для статьи «Платежные методы»\n\n| № | Поле | Значение | Ответственный |\n|---|---|---|---|\n"
            "| 1 | Платежный провайдер | `Code`: `X`<br/>`Name`: X<br/>`Type`: `PaymentSystem` | аналитик |\n"
            "| 2 | Платежный метод | `PaymentMethodCode`: `ApmX`<br/>`MethodType`: `Apm`<br/>`Currency`: `eur`<br/>"
            "`Title`: X<br/>`ShortDescription`: `ApmX`<br/>`ShortDescriptionEoo`: X<br/>`FullDescription`: X<br/>"
            "`LogoUrl`: `null` | аналитик |\n"
            "| 3 | Additional_Settings | См. ниже. | аналитик |\n\n"
        )
        if json_block:
            text += ":::expand additional_settings\n```json\n{}\n```\n:::\n"
    return text + "\n---\n"


def test_dor_ok():
    assert dor_errors(_brd()) == []


def test_dor_missing_sections():
    errors = dor_errors("# BRD\n\nТекст\n")
    assert len(errors) == 2
    assert "Описание интеграции" in errors[0] and "Данные для статьи" in errors[1]


def test_dor_missing_and_extra_rows():
    fields = list(DOR_FIELDS[:-1]) + ["Своё поле"]
    errors = dor_errors(_brd(fields))
    assert any("нет строк Финансовая сверка" in e for e in errors)
    assert any("лишние строки Своё поле" in e for e in errors)


def test_dor_order_and_empty_value():
    fields = list(DOR_FIELDS)
    fields[0], fields[1] = fields[1], fields[0]
    assert any("не по порядку" in e for e in dor_errors(_brd(fields)))
    text = _brd().replace("| 3 | Максимальный лимит день/месяц (по терминалам) | Значение. ‹R-01› |",
                          "| 3 | Максимальный лимит день/месяц (по терминалам) | ‹R-03› |")
    assert any("пустое значение «Максимальный лимит день/месяц" in e for e in dor_errors(text))


def test_dor_article_fields_and_json():
    text = _brd().replace("`LogoUrl`: `null`", "логотип")
    assert any("нет полей LogoUrl" in e for e in dor_errors(text))
    assert any("нет JSON Additional_Settings" in e for e in dor_errors(_brd(json_block=False)))


def test_subsection_stops_at_same_level():
    text = "## A\nа\n### A1\nа1\n## B\nб\n"
    assert subsection(text, "## A") == "а\n### A1\nа1"
    assert subsection(text, "## C") is None


CHANGES = """\
# Доработки

`PaymentMethods`

| Поле | Значение |
|---|---|
| `Id` | `7a409702-93a6-4347-8ee5-2f7294d87400` |
| `ProviderId` | из БД ПФ2 |
| `Title` | X |

`PaymentMethodLocalizations`

| Поле | Значение |
|---|---|
| `Id` | `af94c939-a9d8-4224-9a0b-5b01effdeb01` |
"""


def test_payment_method_ok():
    assert payment_method_errors(CHANGES) == []


@pytest.mark.parametrize(
    "old, new, message",
    [
        ("`PaymentMethodLocalizations`\n", "", "нет таблицы `PaymentMethodLocalizations`"),
        ("`7a409702-93a6-4347-8ee5-2f7294d87400`", "новый", "`Id` = «новый»"),
    ],
)
def test_payment_method_errors(old, new, message):
    assert old in CHANGES
    errors = payment_method_errors(CHANGES.replace(old, new, 1))
    assert any(message in e for e in errors), errors
