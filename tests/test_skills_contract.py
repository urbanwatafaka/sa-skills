from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _skill(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def _assert_contains(text: str, fragments: tuple[str, ...]) -> None:
    missing = [f for f in fragments if f not in text]
    assert not missing, f"нет фрагментов: {missing}"


def test_tdd_impact_contract():
    _assert_contains(
        _skill("tdd-impact"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_state.py init tasks/<KEY> <KEY>",
            "sa_ids.py next tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> BRD",
            "sa_state.py set tasks/<KEY> stage impact",
            "sa_questions.py export tasks/<KEY> PO",
            "sa-skills:source-reader",
            "brd-checklist.md",
            "question-routing.md",
            "adapters.md",
            "[BRD]",
            "SA_SYSTEM_DOCS",
        ),
    )


def test_tdd_start_contract():
    _assert_contains(
        _skill("tdd-start"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_status.py tasks/<KEY>",
            "sa_ids.py next tasks/<KEY>",
            "sa_state.py set tasks/<KEY> template",
            "sa_template.py version feature",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> impact-map",
            "sa_state.py set tasks/<KEY> stage start",
            "sa_questions.py export tasks/<KEY> PO",
            "question-routing.md",
            "`feature`",
            "`integration`",
            "questions.md",
            "## Для PO",
        ),
    )


def test_tdd_clarify_contract():
    _assert_contains(
        _skill("tdd-clarify"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_status.py tasks/<KEY>",
            "sa_ids.py next tasks/<KEY> D",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> context impact-map",
            "sa_state.py set tasks/<KEY> stage clarify",
            "sa_questions.py export tasks/<KEY> PO",
            "sa_questions.py export tasks/<KEY> SA",
            "question-routing.md",
            "*obsolete*",
            "*open, blocking*",
            "*answered*",
            "context.md",
            "| ID | ← Q | Решение | Кто/где | Дата |",
            "## Для PO",
        ),
    )


def test_stage_skills_use_sa_paths():
    for name in ("tdd-impact", "tdd-start", "tdd-clarify", "tdd-draft", "tdd-check", "tdd-update"):
        assert "sa_paths.py" in _skill(name), name


def test_stage_skills_read_shared_writing_rules():
    for name in ("tdd-impact", "tdd-start", "tdd-clarify", "tdd-draft", "tdd-check", "tdd-update"):
        assert "shared/rules/artifact-writing.md" in _skill(name), name


def test_tdd_start_context_sample_validates(task_dir):
    import re

    from sa_validate import validate_task

    text = _skill("tdd-start")
    sample = next(b for b in re.findall(r"```markdown\n(.*?)```", text, re.S) if "## Границы" in b)
    # Образец использует IM-01..IM-03 и Q-PO-01: из карты фикстуры убираем IM-04,
    # а вопрос, ссылавшийся на него, перенаправляем на IM-03.
    impact = task_dir / "impact-map.md"
    impact.write_text(
        "".join(l for l in impact.read_text(encoding="utf-8").splitlines(keepends=True) if not l.startswith("| IM-04")),
        encoding="utf-8",
    )
    questions = task_dir / "questions.md"
    questions.write_text(questions.read_text(encoding="utf-8").replace("[IM-04]", "[IM-03]"), encoding="utf-8")
    # убираем отступ образца внутри списка скила
    lines = [l[5:] if l.startswith("     ") else l for l in sample.splitlines()]
    (task_dir / "context.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert validate_task(task_dir) == []


PUML_SKILLS = ("puml-c2", "puml-sequence", "puml-activity", "puml-er", "puml-state")


def test_puml_skills_contract():
    import re

    from sa_puml import kind_errors, structural_errors

    for name in PUML_SKILLS:
        text = _skill(name)
        _assert_contains(
            text,
            (
                "allowed-tools: Bash(python3:*)",
                "## Когда применять",
                "## Каркас",
                "## Соглашения",
                "## Чек-лист",
                "## Проверка",
                "<плагин>/shared/blocks/diagrams.md",
                "sa_puml.py check",
                "карт",
            ),
        )
        sample = re.search(r"```plantuml\n(.*?)```", text, re.S)
        assert sample, f"{name}: нет каркаса"
        kind = name.split("-", 1)[1]
        assert structural_errors(sample.group(1)) + kind_errors(f"x-{kind}.puml", sample.group(1)) == [], name
        if name != "puml-c2":
            assert "<color:red>" in text, name
    c2 = _skill("puml-c2")
    assert "!includeurl https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml" in c2
    assert "SystemQueue(kafka" in c2
    assert 'autonumber "<b>[000]"' in _skill("puml-sequence")
    assert "[001]" in _skill("puml-activity")


def test_tdd_draft_contract():
    _assert_contains(
        _skill("tdd-draft"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_paths.py",
            "sa_status.py tasks/<KEY>",
            "sa_draft.py gaps tasks/<KEY>",
            "sa_draft.py plan tasks/<KEY>",
            "sa_draft.py assemble tasks/<KEY>",
            "sa_draft.py mark tasks/<KEY>",
            "sa_state.py set tasks/<KEY> published",
            "sa_ids.py next tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> BRD impact-map context questions",
            "sa_state.py set tasks/<KEY> stage draft",
            "<плагин>/shared/blocks/diagrams.md",
            "<плагин>/skills/puml-",
            "@diagram diagrams/",
            "⚠ Q-",
            "‹R-01, IM-02, D-01›",
            "не создаётся",
            "@openapi api/",
            "{{DTO:",
            "sa-skills:source-reader",
            "## Текст",
            "пространство и родительская страница",
            "правка человека",
            "draft-publish.md",
            "adapters.md",
            "writing-style.md",
            "<tasks_dir>/<KEY>/draft/",
        ),
    )


def test_stage_skills_write_absolute_paths():
    for name in ("tdd-impact", "tdd-start", "tdd-clarify", "tdd-draft", "tdd-check", "tdd-update"):
        assert "<tasks_dir>/<KEY>/" in _skill(name), name


def test_tdd_check_contract():
    _assert_contains(
        _skill("tdd-check"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_paths.py",
            "sa_status.py tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "sa_review.py precheck tasks/<KEY>",
            "sa_review.py coverage tasks/<KEY>",
            "sa_review.py asis tasks/<KEY>",
            "sa_ids.py next tasks/<KEY> RV",
            "sa_state.py record tasks/<KEY> draft",
            "sa_state.py set tasks/<KEY> stage check",
            "sa-skills:tdd-reviewer",
            "sa-skills:source-reader",
            "--code",
            "<tasks_dir>/<KEY>/review.md",
            "`открыто`",
            "`принято`",
            "`отклонено`",
            "`закрыто`",
            "/tdd-update",
            "stage done",
        ),
    )


def test_tdd_update_contract():
    _assert_contains(
        _skill("tdd-update"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_paths.py",
            "sa_status.py tasks/<KEY>",
            "sa_review.py status tasks/<KEY> принято",
            "sa_review.py status tasks/<KEY> отклонено",
            "sa_update.py plan tasks/<KEY>",
            "sa_update.py diff tasks/<KEY>",
            "sa_update.py apply tasks/<KEY>",
            "sa_update.py drop tasks/<KEY>",
            "sa_draft.py plan tasks/<KEY>",
            "sa_draft.py mark tasks/<KEY>",
            "sa_draft.py assemble tasks/<KEY>",
            "sa_draft.py gaps tasks/<KEY>",
            "sa_ids.py next tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "sa_state.py record tasks/<KEY> BRD impact-map context questions",
            "sa_state.py set tasks/<KEY> stage draft",
            "sa_state.py set tasks/<KEY> published",
            "<tasks_dir>/<KEY>/draft/",
            "<tasks_dir>/<KEY>/proposals/",
            "‹R-01, IM-02, D-01›",
            "⚠ Q-",
            "правка человека",
            "Без привязки",
            "/tdd-check",
        ),
    )


def test_artifact_writing_lists_all_stages():
    text = (ROOT / "shared/rules/artifact-writing.md").read_text(encoding="utf-8")
    for stage in ("/tdd-impact", "/tdd-start", "/tdd-clarify", "/tdd-draft", "/tdd-check", "/tdd-update"):
        assert stage in text, stage


def test_sa_index_docs_contract():
    _assert_contains(
        _skill("sa-index-docs"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_paths.py",
            "sa_index.py survey <repos_root>/<сервис>",
            "sa_index.py changed <repos_root>/<сервис>",
            "sa_index.py check <repos_root>/<сервис>",
            "sa_index.py stamp <repos_root>/<сервис>",
            "sa_index.py aggregate",
            "aggregate --force",
            "sa-skills:docs-indexer",
            "--full",
            "правка человека",
            "split",
            "<repos_root>/<сервис>/docs/sa-index/",
            "<плагин>/shared/index/docs-schema.md",
            "без веток и коммитов",
        ),
    )


QA_SKILLS = ("qa-cases", "qa-check", "qa-export", "qa-update")


def test_qa_cases_contract():
    _assert_contains(
        _skill("qa-cases"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_qa.py units tasks/<KEY>",
            "sa_ids.py next tasks/<KEY> TC",
            "sa-skills:source-reader",
            "code:",
            "нужно решение",
            "qa-cases.md",
            "sa_qa.py mark tasks/<KEY>",
            "sa_validate.py tasks/<KEY>",
            "Q-QA",
        ),
    )


def test_qa_check_contract():
    _assert_contains(
        _skill("qa-check"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_qa.py precheck tasks/<KEY>",
            "sa_qa.py coverage tasks/<KEY>",
            "sa-skills:qa-reviewer",
            "qa/review.md",
            "QV-",
        ),
    )


def test_qa_export_contract():
    _assert_contains(
        _skill("qa-export"),
        ("allowed-tools: Bash(python3:*)", "sa_qa.py preview tasks/<KEY>", "sa_qa.py export tasks/<KEY>", "загружай", "allure-import.csv"),
    )


def test_qa_update_contract():
    _assert_contains(
        _skill("qa-update"),
        (
            "allowed-tools: Bash(python3:*)",
            "sa_qa.py affected tasks/<KEY>",
            "sa_qa.py human tasks/<KEY>",
            "правка человека",
            "qa/proposals/",
            "sa_qa.py mark tasks/<KEY>",
            "QV-",
        ),
    )


def test_qa_skills_paths_and_scope():
    for name in QA_SKILLS:
        text = _skill(name)
        assert "sa_paths.py" in text, name
        assert "<tasks_dir>/<KEY>/qa/" in text, name
