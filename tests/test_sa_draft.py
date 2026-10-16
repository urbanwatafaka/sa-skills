import json

import pytest

from conftest import write_sections
from sa_artifacts import ArtifactError, split_frontmatter
from sa_draft import assemble, dto_errors, main, openapi_errors, placeholders, plan, stubs, trace_refs
from sa_state import file_sha1, load_state, save_state


def test_trace_refs_and_placeholders():
    text = "Проверка ‹R-01, IM-02› и ‹D-01›. Текст ⚠ Q-PO-02, ещё ⚠ без ID"
    assert trace_refs(text) == ["R-01", "IM-02", "D-01"]
    assert placeholders(text) == ["Q-PO-02", None]


def test_stubs():
    assert stubs("# Конфиги\n\nНе применимо: конфиги не меняются\n") == ["Не применимо"]
    assert stubs("1. Метод\n   - Без изменений\n") == ["Без изменений"]
    assert stubs("Изменений схемы БД не требуется — поле есть.\nИзменений полей нет.\n") == []


def test_assemble(draft_task):
    meta, body = split_frontmatter((draft_task / "draft.md").read_text(encoding="utf-8"))
    assert meta == {
        "status": "черновик", "author": "Иван Петров", "jira": "LKP-DEMO",
        "template": "feature@2.0", "assembled": "2026-10-15",
    }
    assert body.startswith("# Запрет собственного промокода в анкете\n\n# BRD\n")
    assert body.index("# BRD") < body.index("# Архитектура и Процесс") < body.index("# Доработки")
    assert "# Доработки\n\nТекст секции ‹R-01›\n\n---\n\n## Топики Кафка" in body
    assert body.index("# Условия релиза") < body.index("# Открытые вопросы")
    assert "1. **Q-PO-02** Какой текст показать мерчанту, если он указал собственный промокод?<br/>**Ответ**:" in body
    assert "Q-PO-01" not in body
    assert "‹R-01›" in body
    publish = (draft_task / "draft-publish.md").read_text(encoding="utf-8")
    assert publish.startswith(
        "# Запрет собственного промокода в анкете\n\n:::expand Оглавление\n{{toc}}\n:::\n\n---\n\n**Статусы**\n\n"
        "| Параметр | Значение |\n|---|---|\n| Статус задачи | в аналитике |\n| Автор документа | Иван Петров |\n"
    )
    assert "/browse/LKP-DEMO |\n| Ссылка на дизайн | Не требуется |\n\n---\n\n# BRD\n" in publish
    assert "1. Какой текст показать мерчанту, если он указал собственный промокод?<br/>**Ответ**:" in publish
    assert "‹" not in publish
    sections = load_state(draft_task)["sections"]
    assert len(sections) == 9
    assert sections["03-changes"] == {"hash": file_sha1(draft_task / "draft/03-changes.md"), "edited_by_human": False}


def test_assemble_statuses_from_context(draft_task):
    context = draft_task / "context.md"
    text = context.read_text(encoding="utf-8").replace(
        "title: Запрет собственного промокода в анкете\n",
        "title: Промокоды\ntask_status: в оценке\njira: https://jira.example/browse/LKP-DEMO\ndesign: https://figma.example/x\n",
    )
    context.write_text(text, encoding="utf-8")
    assemble(draft_task)
    publish = (draft_task / "draft-publish.md").read_text(encoding="utf-8")
    assert publish.startswith("# Промокоды\n")
    assert "| Статус задачи | в оценке |" in publish
    assert "| Jira ссылка | https://jira.example/browse/LKP-DEMO |" in publish
    assert "| Ссылка на дизайн | https://figma.example/x |" in publish


def test_jira_url_from_key(draft_task, monkeypatch):
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    assemble(draft_task)
    publish = (draft_task / "draft-publish.md").read_text(encoding="utf-8")
    assert "| Jira ссылка | https://jira.tasktracker.help/browse/LKP-DEMO |" in publish
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example/")
    assemble(draft_task)
    publish = (draft_task / "draft-publish.md").read_text(encoding="utf-8")
    assert "| Jira ссылка | https://jira.example/browse/LKP-DEMO |" in publish


def test_open_questions_approval_and_answer(draft_task):
    questions = draft_task / "questions.md"
    text = questions.read_text(encoding="utf-8")
    text = text.replace(
        "  Варианты: а) не пересчитывать; б) пересчитать — *answered*",
        "  Варианты: а) не пересчитывать; б) пересчитать\n  Ответ в ТЗ: не пересчитывать — *answered*",
    ).replace(
        "собственный промокод? — *open, blocking*",
        "собственный промокод?\n  Согласование: бизнес, архком\n"
        "  Ответ в ТЗ: предварительно — «Промокод недоступен»; согласования пока не было — *open, blocking*",
    )
    questions.write_text(text, encoding="utf-8")
    assemble(draft_task)
    publish = (draft_task / "draft-publish.md").read_text(encoding="utf-8")
    assert (
        "1. Что делать с вознаграждениями, уже начисленными партнёрам за собственные анкеты?"
        "<br/>**Ответ**: не пересчитывать\n" in publish
    )
    assert (
        "2. Какой текст показать мерчанту, если он указал собственный промокод?"
        "<br/>❗**Требует согласования:** Бизнес, Архитектурный комитет"
        "<br/>**Ответ**: предварительно — «Промокод недоступен»; согласования пока не было\n" in publish
    )
    assert "3. Публикует ли lkp-back событие в Kafka при сохранении анкеты?<br/>**Ответ**:\n" in publish


def test_assemble_without_title_uses_manifest(draft_task):
    context = draft_task / "context.md"
    context.write_text(
        context.read_text(encoding="utf-8").replace("title: Запрет собственного промокода в анкете\n", ""),
        encoding="utf-8",
    )
    assemble(draft_task)
    assert "\n# ТЗ на доработку: LKP-DEMO\n" in (draft_task / "draft.md").read_text(encoding="utf-8")


def test_assemble_publish_placeholders(draft_task):
    (draft_task / "draft/03-changes.md").write_text(
        "# Доработки\n\nТекст ошибки ⚠ Q-PO-02. ‹R-02›\n", encoding="utf-8"
    )
    assemble(draft_task)
    publish = (draft_task / "draft-publish.md").read_text(encoding="utf-8")
    assert "Текст ошибки :question:." in publish
    assert "⚠ Q-PO-02" in (draft_task / "draft.md").read_text(encoding="utf-8")


def test_assemble_skips_absent_optional(draft_task):
    for sid in ("04-kafka", "05-dependent", "06-configs", "07-access", "09-release"):
        (draft_task / f"draft/{sid}.md").unlink()
    assemble(draft_task)
    body = (draft_task / "draft.md").read_text(encoding="utf-8")
    assert "Топики Кафка" not in body and "# Конфиги" not in body
    assert "\n---\n" not in split_frontmatter(body)[1]
    assert set(load_state(draft_task)["sections"]) == {"01-brd", "02-architecture", "03-changes", "08-testing"}


def test_assemble_no_open_questions(draft_task):
    questions = draft_task / "questions.md"
    questions.write_text(questions.read_text(encoding="utf-8").replace("*open, blocking*", "*answered*").replace("*open*", "*obsolete*"), encoding="utf-8")
    assemble(draft_task)
    assert "Открытые вопросы" not in (draft_task / "draft.md").read_text(encoding="utf-8")


def test_assemble_inlines_diagram_openapi_and_reuses_author(draft_task):
    (draft_task / "draft/diagrams").mkdir()
    (draft_task / "draft/api").mkdir()
    (draft_task / "draft/diagrams/02-architecture-sequence.puml").write_text(
        '@startuml\nautonumber "<b>[000]"\nA -> B : вызов\n@enduml\n', encoding="utf-8"
    )
    (draft_task / "draft/api/lkp-back.yaml").write_text("openapi: 3.0.3\n", encoding="utf-8")
    (draft_task / "draft/02-architecture.md").write_text(
        "# Архитектура и Процесс\n\n@diagram diagrams/02-architecture-sequence.puml\n", encoding="utf-8"
    )
    (draft_task / "draft/03-changes.md").write_text("# Доработки\n\n**2. API:**\n\n@openapi api/lkp-back.yaml\n", encoding="utf-8")
    assemble(draft_task)
    text = (draft_task / "draft.md").read_text(encoding="utf-8")
    assert '```plantuml\n@startuml\nautonumber "<b>[000]"\nA -> B : вызов\n@enduml\n```' in text
    assert "```openapi\nopenapi: 3.0.3\n```" in text
    assert "author: Иван Петров" in text


def test_assemble_missing_required_section(draft_task):
    (draft_task / "draft/08-testing.md").unlink()
    with pytest.raises(ArtifactError, match="нет обязательных секций: 08-testing"):
        assemble(draft_task)


def test_assemble_missing_diagram_and_openapi(draft_task):
    (draft_task / "draft/02-architecture.md").write_text("# Архитектура и Процесс\n\n@diagram diagrams/nope.puml\n", encoding="utf-8")
    with pytest.raises(ArtifactError, match="нет диаграммы draft/diagrams/nope.puml"):
        assemble(draft_task)
    (draft_task / "draft/02-architecture.md").write_text("# Архитектура и Процесс\n\n@openapi api/nope.yaml\n", encoding="utf-8")
    with pytest.raises(ArtifactError, match="нет OpenAPI draft/api/nope.yaml"):
        assemble(draft_task)


def test_assemble_needs_author(task_dir):
    write_sections(task_dir)
    with pytest.raises(ArtifactError, match="укажи автора"):
        assemble(task_dir)


def test_assemble_keeps_human_flag(draft_task):
    state = load_state(draft_task)
    state["sections"]["03-changes"]["edited_by_human"] = True
    save_state(draft_task, state)
    assemble(draft_task)
    assert load_state(draft_task)["sections"]["03-changes"]["edited_by_human"] is True


def test_plan_statuses_and_slices(draft_task):
    (draft_task / "draft/03-changes.md").write_text("# Доработки\n\nПравка аналитика\n", encoding="utf-8")
    (draft_task / "draft/06-configs.md").unlink()
    lines = plan(draft_task).splitlines()
    assert lines[0] == "Шаблон: feature@2.0 — ТЗ на доработку"
    changes = lines.index("03-changes | Доработки | обязательная | блок: blocks/changes.md | диаграммы: er | правка человека — не перезаписывать")
    assert lines[changes + 1] == "  R: R-01, R-02, R-03 · IM: IM-01, IM-02, IM-03, IM-04 · D: D-01"
    kafka = lines.index("04-kafka | Топики Кафка | необязательная | блок: blocks/kafka.md | диаграммы: — | есть")
    assert lines[kafka + 1] == "  R: R-03 · IM: IM-04 · D: —"
    release = lines.index("09-release | Условия релиза | необязательная | блок: blocks/release.md | диаграммы: — | есть")
    assert lines[release + 1] == "  R: R-02 · IM: IM-03 · D: —"
    assert "06-configs | Конфиги | необязательная | блок: blocks/configs.md | диаграммы: — | нет — без содержания не создаётся" in lines
    assert "02-architecture | Архитектура и Процесс | обязательная | блок: blocks/architecture.md | диаграммы: c2, sequence | есть" in lines
    assert load_state(draft_task)["sections"]["03-changes"]["edited_by_human"] is True


def test_plan_excludes_out_of_scope(draft_task):
    context = draft_task / "context.md"
    context.write_text(
        context.read_text(encoding="utf-8").replace("| IM-03 | в скоупе | —", "| IM-03 | вне скоупа | экран не меняем"),
        encoding="utf-8",
    )
    lines = plan(draft_task).splitlines()
    changes = next(i for i, l in enumerate(lines) if l.startswith("03-changes |"))
    assert lines[changes + 1] == "  R: R-01, R-02, R-03 · IM: IM-01, IM-02, IM-04 · D: D-01"


def test_plan_needs_template(task_dir):
    state = json.loads((task_dir / "state.json").read_text(encoding="utf-8"))
    del state["template"]
    (task_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ArtifactError, match="нет template"):
        plan(task_dir)


def test_cli(draft_task, capsys):
    assert main(["plan", str(draft_task)]) == 0
    assert capsys.readouterr().out.startswith("Шаблон: feature@2.0")
    assert main(["assemble", str(draft_task), "Пётр Иванов"]) == 0
    assert "author: Пётр Иванов" in (draft_task / "draft.md").read_text(encoding="utf-8")
    assert main([]) == 2
    (draft_task / "draft/01-brd.md").unlink()
    assert main(["assemble", str(draft_task)]) == 1


GOOD_OPENAPI = """\
openapi: 3.0.3
info:
  title: Payform.Lkp.Back.Api
  version: 1.0.0
tags:
  - name: Api
  - name: Internal
paths:
  /api/questionnaires:
    post:
      tags: [Api]
  '/internal/promocodes/{code}/owner':
    get:
      tags: [Internal]
"""


def test_openapi_errors():
    assert openapi_errors(GOOD_OPENAPI) == []
    bad = GOOD_OPENAPI.replace("3.0.3", "3.1.0").replace("Payform.Lkp.Back.Api", "lkp-back").replace("  version: 1.0.0\n", "")
    bad = bad.replace("/api/questionnaires", "/questionnaires")
    assert openapi_errors(bad) == [
        "нет шапки «openapi: 3.0.3»",
        "info.title «lkp-back» — ожидается <Namespace сервиса>.Api",
        "нет info.version",
        "путь /questionnaires без префикса /api, /backoffice, /public или /internal",
    ]
    assert openapi_errors("openapi: 3.0.3\n") == ["нет info.title", "нет info.version", "нет paths"]


def test_openapi_tag_matches_prefix():
    bad = GOOD_OPENAPI.replace("      tags: [Internal]", "      tags:\n        - Api")
    bad = bad.replace("      tags: [Api]", "      tags: [Backoffice]")
    assert openapi_errors(bad) == [
        "POST /api/questionnaires: тег Backoffice, а по префиксу пути — Api",
        "GET /internal/promocodes/{code}/owner: тег Api, а по префиксу пути — Internal",
    ]


def test_dto_errors(task_dir):
    assert dto_errors(task_dir, "SavedEvent") == ["нет файла draft/dto/SavedEvent.json для {{DTO:SavedEvent}}"]
    (task_dir / "draft/dto").mkdir(parents=True)
    (task_dir / "draft/dto/SavedEvent.json").write_text('{"key": "1"}', encoding="utf-8")
    assert dto_errors(task_dir, "SavedEvent") == ["draft/dto/SavedEvent.json: нет поля $type"]
    (task_dir / "draft/dto/SavedEvent.json").write_text('{"key": "1", "$type": "SavedEvent"}', encoding="utf-8")
    assert dto_errors(task_dir, "SavedEvent") == []


import sa_puml
from sa_draft import gaps
from sa_puml import MODE_STRUCTURE


def test_gaps_demo(draft_task, monkeypatch):
    monkeypatch.setattr(sa_puml, "find_renderer", lambda: None)
    (draft_task / "draft/03-changes.md").write_text("# Доработки\n\nМетод ‹IM-01› ⚠ Q-PO-02, ещё ⚠ Q-PO-02\n", encoding="utf-8")
    (draft_task / "draft/06-configs.md").write_text("# Конфиги\n\nНе применимо: конфиги не меняются ‹R-01›\n", encoding="utf-8")
    (draft_task / "draft/07-access.md").unlink()
    assert gaps(draft_task).splitlines() == [
        "Обязательные секции: все на месте",
        "Необязательные не созданы: 07-access",
        "Плейсхолдеры ⚠: 03-changes (Q-PO-02)",
        "Плейсхолдеры на закрытые вопросы: нет",
        "Открытые блокирующие вопросы: Q-PO-02",
        "Нерешённый скоуп: IM-04 (ждём ответа на Q-SA-01)",
        "R без трассировки: R-02, R-03",
        "IM (новый/изм., в скоупе) без трассировки: IM-02, IM-03",
        "Заглушки вместо содержания: 06-configs",
        "Диаграммы: нет",
    ]


def test_gaps_missing_sections_and_diagrams(draft_task, monkeypatch):
    monkeypatch.setattr(sa_puml, "find_renderer", lambda: None)
    (draft_task / "draft/08-testing.md").unlink()
    diagrams = draft_task / "draft/diagrams"
    diagrams.mkdir()
    (diagrams / "02-architecture-sequence.puml").write_text('@startuml\nautonumber "<b>[000]"\nA -> B : x\n@enduml\n', encoding="utf-8")
    (diagrams / "03-changes-er.puml").write_text("@startuml\nhide circle\nentity a {\n", encoding="utf-8")
    lines = gaps(draft_task).splitlines()
    assert lines[0] == "Нет обязательных секций: 08-testing"
    assert lines[9] == f"Диаграммы: 2, проверка: {MODE_STRUCTURE}"
    assert lines[10:] == [
        "  03-changes-er.puml: последняя строка должна быть @enduml",
        "  03-changes-er.puml: строка 3: незакрытая «{»",
    ]


def test_gaps_cli(draft_task, monkeypatch, capsys):
    monkeypatch.setattr(sa_puml, "find_renderer", lambda: None)
    assert main(["gaps", str(draft_task)]) == 0
    assert capsys.readouterr().out.startswith("Обязательные секции: все на месте\n")
