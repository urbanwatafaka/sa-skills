from pathlib import Path

import pytest

from sa_artifacts import ArtifactError
from sa_qa_cases import Case, case_hash, lint_case, parse_cases

FIXTURE = Path(__file__).parent / "fixtures" / "qa" / "cases.md"

MANUAL = """### Проверка вручную

- **Вид:** фронт
- **Приоритет:** Medium
- **Покрывает:** U-02
- **Источник:** ‹R-01›

**Описание:** Описание.

**Предусловия:** Мерчант.

**Шаги:**
1. Открыть экран.

**Ожидаемый результат:** Видно «Логотип».
"""


def make_case(**changes) -> Case:
    fields = dict(
        id="TC-01", title="Кейс", kind="бэкенд", priority="High", covers=["U-01"], sources=["R-01"],
        description="Описание", preconditions="Мерчант", steps=["Вызвать метод `POST /api/files`"],
        expected="Ответ `200`", raw="",
    )
    fields.update(changes)
    return Case(**fields)


def test_parse_fixture():
    cases = parse_cases(FIXTURE.read_text(encoding="utf-8"))
    assert [c.id for c in cases] == ["TC-01", "TC-02", "TC-03"]
    assert cases[0].kind == "бэкенд" and cases[0].covers == ["U-01", "U-04"]
    assert '"merchantId"' in cases[0].steps[0]          # json-тело внутри шага
    assert cases[0].steps[0].splitlines()[1] == "```json"
    assert cases[0].expected.startswith("Ответ `400`")
    assert cases[0].sources == ["R-01", "IM-02", "D-01"]
    assert cases[0].title == "Загрузка логотипа больше 5 МБ отклоняется"
    assert len(cases[0].steps) == 2 and cases[1].priority == "High" and cases[2].kind == "регресс"
    assert cases[2].raw.startswith("### TC-03") and "## Регресс" not in cases[1].raw


def test_parse_error_names_case():
    with pytest.raises(ArtifactError, match="TC-02"):
        parse_cases(FIXTURE.read_text(encoding="utf-8").replace("**Ожидаемый результат:**", "**Итог:**", 2))


@pytest.mark.parametrize(
    "old, new",
    [
        ("**Предусловия:** Мерчант с каналом продаж; файл PNG размером 6 МБ.\n\n**Шаги:**\n1. Открыть",
         "**Предусловия:** Мерчант с каналом продаж; файл PNG размером 6 МБ.\n\n**Шаги:**\nОткрыть экран\n1. Открыть"),
        ("- **Источник:** ‹D-01›\n", "- **Источник:** ‹D-01›\nЛишний текст между полями\n"),
        ("- **Вид:** фронт\n", "- **Вид:** фронт\n- **Вид:** бэкенд\n"),
    ],
)
def test_parse_error_on_manual_breakage(old, new):
    text = FIXTURE.read_text(encoding="utf-8")
    assert old in text
    with pytest.raises(ArtifactError, match="TC-02"):
        parse_cases(text.replace(old, new, 1))


def test_parse_error_unclosed_fence():
    text = FIXTURE.read_text(encoding="utf-8").replace("   ```\n2.", "2.", 1)
    with pytest.raises(ArtifactError, match="TC-01"):
        parse_cases(text)


def test_manual_case_without_id():
    case = parse_cases(MANUAL)[0]
    assert case.id == "" and case.title == "Проверка вручную"


def test_missing_block_is_lint_not_parse_error():
    case = parse_cases(MANUAL.replace("**Предусловия:** Мерчант.\n\n", ""))[0]
    assert case.preconditions == ""
    assert any(e.startswith("предусловия:") for e in lint_case(case))


def test_case_hash_ignores_line_endings():
    case = parse_cases(MANUAL)[0]
    crlf = parse_cases(MANUAL.replace("\n", "\r\n"))[0]
    assert case_hash(case) == case_hash(crlf)
    assert case_hash(case) != case_hash(parse_cases(MANUAL.replace("Открыть экран", "Открыть окно"))[0])


def test_lint_good_case_clean():
    assert lint_case(make_case()) == []
    assert [lint_case(c) for c in parse_cases(FIXTURE.read_text(encoding="utf-8"))] == [[], [], []]


@pytest.mark.parametrize("bad", ["Работает корректно", "Отображается правильно", "Проверить, что работает", "и т.д.", "при необходимости"])
def test_lint_vague(bad):
    assert any("расплывчато" in e for e in lint_case(make_case(expected=bad)))


def test_lint_vague_in_steps_and_negation_allowed():
    assert any("расплывчато" in e for e in lint_case(make_case(steps=["Проверить, что работает"])))
    assert lint_case(make_case(expected="Ответ `400`: некорректный формат файла")) == []


def test_lint_successfully_needs_detail():
    assert any("расплывчато" in e for e in lint_case(make_case(kind="фронт", expected="Файл успешно загружен")))
    assert lint_case(make_case(kind="фронт", expected="Файл успешно загружен, показано «logo.png»")) == []


def test_lint_backend_needs_code():
    assert lint_case(make_case(kind="бэкенд", expected="Файл сохранён"))
    assert not lint_case(make_case(kind="бэкенд", expected="Ответ `200`, в теле `documentId`"))


def test_lint_required_fields():
    errs = lint_case(make_case(description="", preconditions="", steps=[], covers=[]))
    assert {"описание", "предусловия", "шаги", "покрывает"} <= {e.split(":")[0] for e in errs}


def test_lint_kind_priority_expected():
    errs = lint_case(make_case(kind="апи", priority="Срочно", expected=""))
    assert {"вид", "приоритет", "ожидаемый результат"} <= {e.split(":")[0] for e in errs}


def test_lint_source_and_title_required():
    errs = lint_case(make_case(sources=[], title=""))
    assert {"источник", "название"} <= {e.split(":")[0] for e in errs}


def test_heading_inside_fence_does_not_split_case():
    text = FIXTURE.read_text(encoding="utf-8").replace('   {"merchantId"', '   ### не заголовок\n   {"merchantId"', 1)
    text = text.replace("   ### не заголовок", "### не заголовок", 1)
    cases = parse_cases(text)
    assert [c.id for c in cases] == ["TC-01", "TC-02", "TC-03"]
    assert "### не заголовок" in cases[0].steps[0]


@pytest.mark.parametrize(
    "old, new",
    [
        ("**Ожидаемый результат:** Появляется", "**Ожидаемый результат**: Появляется"),
        ("- **Приоритет:** High\n- **Покрывает:** U-03", "- **Приоритет**: High\n- **Покрывает:** U-03"),
    ],
)
def test_colon_outside_bold_is_format_error(old, new):
    text = FIXTURE.read_text(encoding="utf-8")
    assert old in text
    with pytest.raises(ArtifactError, match="TC-02.*двоеточие"):
        parse_cases(text.replace(old, new, 1))


def test_several_code_refs_in_one_source_entry():
    case = parse_cases(MANUAL.replace("‹R-01›", "‹R-01, D-01›; code: svc/a.cs:12, svc/b.cs:40"))[0]
    assert case.sources == ["R-01", "D-01", "code: svc/a.cs:12, svc/b.cs:40"]


def test_lint_backend_code_placeholder_accepted():
    assert lint_case(make_case(kind="бэкенд", expected="Ответ ⚠ Q-QA-02; документ не создан")) == []


STEP_RESULTS = MANUAL.replace(
    "1. Открыть экран.\n",
    "1. Открыть экран ЛК, выбрать файл.\n   - Результат: файл сохранился — показано «logo.png».\n"
    "2. Открыть экран БО, выбрать файл.\n   - Результат: файл сохранился — показано «logo.png».\n",
)


def test_step_results_kept_in_steps():
    case = parse_cases(STEP_RESULTS)[0]
    assert len(case.steps) == 2
    assert case.steps[0].splitlines()[1] == "- Результат: файл сохранился — показано «logo.png»."
    assert lint_case(case) == []


def test_empty_step_result_is_error():
    case = parse_cases(STEP_RESULTS.replace("   - Результат: файл сохранился — показано «logo.png».\n2.", "   - Результат:\n2.", 1))[0]
    assert any(e.startswith("шаги:") and "шаг 1" in e and "результат" in e for e in lint_case(case))


def test_vague_step_result_is_error():
    case = parse_cases(STEP_RESULTS.replace("файл сохранился — показано «logo.png».\n2.", "работает корректно\n2.", 1))[0]
    assert any("расплывчато" in e and "шаг 1" in e for e in lint_case(case))


def test_reference_to_other_case_is_error():
    errors = lint_case(make_case(steps=["Отправить сообщение из шага 1 кейса TC-02"], preconditions="Мерчант из TC-05"))
    assert any("ссылка на другой кейс: TC-02 — шаг 1" in e for e in errors)
    assert any("ссылка на другой кейс: TC-05 — предусловия" in e for e in errors)


def test_own_id_is_not_reference():
    assert not any("ссылка на другой кейс" in e for e in lint_case(make_case(description="Кейс TC-01 проверяет загрузку")))
