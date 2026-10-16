import json

from sa_validate import main, validate_state, validate_task


def _edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"в {path.name} нет фрагмента {old!r}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_demo_task_is_valid(task_dir):
    assert validate_task(task_dir) == []


def test_missing_state(tmp_path):
    errors = validate_task(tmp_path)
    assert len(errors) == 1 and errors[0].startswith("state.json:")


def test_only_present_artifacts_checked(task_dir):
    _edit(task_dir / "sources/BRD.md", "brd_complete: true", "brd_complete: false")
    _edit(task_dir / "sources/BRD.md", "missing: []", "missing: [a]")
    for name in ("impact-map.md", "questions.md", "decisions.md", "context.md"):
        (task_dir / name).unlink()
    assert validate_task(task_dir) == []


def test_duplicate_brd_id(task_dir):
    _edit(task_dir / "sources/BRD.md", "| R-02 |", "| R-01 |")
    assert "sources/BRD.md: R-01: ID повторяется" in validate_task(task_dir)


def test_incomplete_brd_needs_missing_list(task_dir):
    _edit(task_dir / "sources/BRD.md", "brd_complete: true", "brd_complete: false")
    errors = validate_task(task_dir)
    assert any("missing пуст" in e for e in errors)


def test_fact_without_source(task_dir):
    _edit(task_dir / "impact-map.md", "| code: lkp-back/app/Rules/Promocode.php:40 |", "| — |")
    assert any(e.startswith("impact-map.md: IM-02: факт без источника") for e in validate_task(task_dir))


def test_impact_bad_kind_and_unknown_ref(task_dir):
    _edit(task_dir / "impact-map.md", "| R-02       | docs:", "| R-09       | docs:")
    _edit(task_dir / "impact-map.md", "| UI     | изм.", "| экран  | изм.")
    errors = validate_task(task_dir)
    assert "impact-map.md: IM-03: ссылка на несуществующий R-09" in errors
    assert any(e.startswith("impact-map.md: IM-03: вид «экран»") for e in errors)


def test_question_in_wrong_section(task_dir):
    _edit(task_dir / "questions.md", "**Q-SA-01**", "**Q-PO-03**")
    errors = validate_task(task_dir)
    assert "questions.md: Q-PO-03: лежит в секции SA, а адресован PO" in errors


def test_question_unknown_ref(task_dir):
    _edit(task_dir / "questions.md", "[IM-04]", "[IM-99]")
    assert "questions.md: Q-SA-01: ссылка на несуществующий IM-99" in validate_task(task_dir)


def test_question_parse_error_is_reported(task_dir):
    _edit(task_dir / "questions.md", " — *open, blocking*", "")
    assert any(e.startswith("questions.md: Q-PO-02: нет статуса") for e in validate_task(task_dir))


def test_decision_unknown_question_and_bad_date(task_dir):
    _edit(task_dir / "decisions.md", "| Q-PO-01 |", "| Q-PO-07 |")
    _edit(task_dir / "decisions.md", "2026-09-09", "09.09.2026")
    errors = validate_task(task_dir)
    assert "decisions.md: D-01: ссылка на несуществующий Q-PO-07" in errors
    assert "decisions.md: D-01: дата должна быть в формате ГГГГ-ММ-ДД" in errors


def test_state_rules():
    good = {"task": "X-1", "stage": "impact", "plugin_version": "0.1.0", "inputs": {}, "sections": {}}
    assert validate_state(good) == []
    bad = {
        "task": "",
        "stage": "review",
        "template": "Feature",
        "plugin_version": "1",
        "inputs": {"BRD": "abc", "nope": "0" * 40},
        "sections": {"05-api": {"hash": "x"}},
        "access": {"jira": "ftp", "slack": "mcp"},
    }
    errors = validate_state(bad)
    for fragment in ("task:", "stage:", "template:", "plugin_version:", "inputs.BRD", "inputs: неизвестный артефакт nope",
                     "sections.05-api.hash", "sections.05-api.edited_by_human", "access.jira", "access: неизвестный ключ slack"):
        assert any(fragment in e for e in errors), fragment


def test_cli(task_dir, capsys):
    assert main([str(task_dir)]) == 0
    assert capsys.readouterr().out.startswith("OK:")
    state = json.loads((task_dir / "state.json").read_text(encoding="utf-8"))
    state["stage"] = "oops"
    (task_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert main([str(task_dir)]) == 1
    assert "stage:" in capsys.readouterr().out
    assert main([]) == 2


def test_brd_bad_fetched_date(task_dir):
    _edit(task_dir / "sources/BRD.md", "fetched: 2026-10-15", "fetched: 15.10.2026")
    assert "sources/BRD.md: fetched должен быть в формате ГГГГ-ММ-ДД" in validate_task(task_dir)


def test_brd_bad_type(task_dir):
    _edit(task_dir / "sources/BRD.md", "| UI     |", "| экран  |")
    assert any(e.startswith("sources/BRD.md: R-02: тип «экран»") for e in validate_task(task_dir))


def test_no_index_caps_confidence(task_dir):
    _edit(task_dir / "impact-map.md", "index_used: true", "index_used: false")
    assert any("без индекса не выше средняя" in e for e in validate_task(task_dir))


def test_state_malformed_types_do_not_raise():
    errors = validate_state({"task": "X", "stage": ["x"], "plugin_version": "0.1.0", "access": {"jira": ["x"]}})
    assert any(e.startswith("stage:") for e in errors)
    assert any(e.startswith("access.jira") for e in errors)


def test_brd_ref_allowed_for_po(task_dir):
    _edit(task_dir / "questions.md", "**Q-PO-02** [R-02]", "**Q-PO-02** [BRD]")
    assert validate_task(task_dir) == []


def test_brd_ref_forbidden_for_sa(task_dir):
    _edit(task_dir / "questions.md", "**Q-SA-01** [IM-04]", "**Q-SA-01** [BRD]")
    assert "questions.md: Q-SA-01: ссылка [BRD] допустима только в вопросах PO" in validate_task(task_dir)


def test_bad_ref_token(task_dir):
    _edit(task_dir / "questions.md", "**Q-PO-02** [R-02]", "**Q-PO-02** [цель]")
    assert "questions.md: Q-PO-02: «цель» — не ID и не BRD" in validate_task(task_dir)


def test_confidence_above_cap(task_dir):
    _edit(task_dir / "impact-map.md", "confidence_cap: высокая", "confidence_cap: средняя")
    errors = validate_task(task_dir)
    assert any("уверенность выше потолка confidence_cap (средняя)" in e for e in errors)


def test_po_question_text_must_not_have_refs(task_dir):
    _edit(task_dir / "questions.md", "промокод? — *open, blocking*", "промокод? (см. R-03) — *open, blocking*")
    assert (
        "questions.md: Q-PO-02: в тексте вопроса PO не должно быть ссылок R-03 — оставь их только в [..] в начале"
        in validate_task(task_dir)
    )


def test_po_question_details_must_not_have_refs(task_dir):
    _edit(task_dir / "questions.md", "промокод? — *open, blocking*", "промокод? — *open, blocking*\n  Связано с IM-04")
    assert any("Q-PO-02: в тексте вопроса PO не должно быть ссылок IM-04" in e for e in validate_task(task_dir))


def test_po_question_may_mention_other_question(task_dir):
    _edit(task_dir / "questions.md", "промокод? — *open, blocking*", "промокод? после Q-PO-01 — *open, blocking*")
    assert not any("не должно быть ссылок" in e for e in validate_task(task_dir))


def test_context_out_of_scope_needs_reason(task_dir):
    _edit(task_dir / "context.md", "| IM-03 | в скоупе | —                      |", "| IM-03 | вне скоупа | — |")
    assert "context.md: IM-03: для «вне скоупа» нужна причина в колонке Комментарий" in validate_task(task_dir)


def test_context_every_impact_row_listed(task_dir):
    _edit(task_dir / "context.md", "| IM-04 | ?        | ждём ответа на Q-SA-01 |\n", "")
    assert "context.md: IM-04: пункт карты влияния не распределён в «Границах»" in validate_task(task_dir)


def test_context_unknown_im_and_bad_scope(task_dir):
    _edit(task_dir / "context.md", "| IM-04 | ?        |", "| IM-09 | может    |")
    errors = validate_task(task_dir)
    assert "context.md: IM-09: ссылка на несуществующий IM-09" in errors
    assert any(e.startswith("context.md: IM-09: скоуп «может»") for e in errors)


def test_context_template_must_match_state(task_dir):
    _edit(task_dir / "context.md", "template: feature@2.0", "template: integration@1.0")
    assert "context.md: template integration@1.0 не совпадает с state.json (feature@2.0)" in validate_task(task_dir)


def test_context_required_sections_and_keys(task_dir):
    _edit(task_dir / "context.md", "## Цель", "## Зачем")
    _edit(task_dir / "context.md", "release: 2026-11\n", "")
    errors = validate_task(task_dir)
    assert "context.md: нет раздела «## Цель»" in errors
    assert "context.md: во frontmatter нет ключа release" in errors


def test_context_question_scope_needs_question_ref(task_dir):
    _edit(task_dir / "context.md", "ждём ответа на Q-SA-01", "ждём ответа")
    assert "context.md: IM-04: для «?» укажи в Комментарии ID вопроса, который решит скоуп" in validate_task(task_dir)


def test_context_question_scope_unknown_question(task_dir):
    _edit(task_dir / "context.md", "Q-SA-01 |", "Q-SA-09 |")
    assert "context.md: IM-04: ссылка на несуществующий Q-SA-09" in validate_task(task_dir)


def test_context_template_type_must_be_known(task_dir):
    _edit(task_dir / "context.md", "template: feature@2.0", "template: foo@1.0")
    _edit(task_dir / "state.json", "feature@2.0", "foo@1.0")
    assert "context.md: template: тип foo не из списка: feature, integration" in validate_task(task_dir)


def test_context_duplicate_im_row(task_dir):
    _edit(task_dir / "context.md", "| IM-02 | в скоупе | —                      |", "| IM-01 | в скоупе | —                      |")
    assert "context.md: IM-01: IM повторяется в «Границах»" in validate_task(task_dir)


def test_context_cell_with_two_ims(task_dir):
    _edit(task_dir / "context.md", "| IM-01 |", "| IM-01, IM-02 |")
    assert "context.md: «IM-01, IM-02»: в колонке ← IM нужен ровно один IM-xx" in validate_task(task_dir)


def test_complete_brd_without_impact_map(task_dir):
    (task_dir / "impact-map.md").unlink()
    errors = validate_task(task_dir)
    assert "impact-map.md: нет файла, а BRD полный — карта влияния должна быть построена" in errors
    assert "questions.md: Q-SA-01: ссылка на IM-04, но impact-map.md нет" in errors
    assert "context.md: IM-01: ссылка на IM-01, но impact-map.md нет" in errors


def test_incomplete_brd_without_impact_map_and_refs(task_dir):
    _edit(task_dir / "sources/BRD.md", "brd_complete: true", "brd_complete: false")
    _edit(task_dir / "sources/BRD.md", "missing: []", "missing: [a]")
    for name in ("impact-map.md", "context.md"):
        (task_dir / name).unlink()
    _edit(task_dir / "questions.md", "[IM-04]", "[R-01]")
    assert validate_task(task_dir) == []


def _write(task, section_id, heading, body):
    (task / "draft" / f"{section_id}.md").write_text(f"{heading}\n\n{body}\n", encoding="utf-8")


def _assemble(task):
    from sa_draft import assemble

    assemble(task)


def test_draft_valid(draft_task):
    assert validate_task(draft_task) == []


def test_draft_missing_and_extra_sections(draft_task):
    (draft_task / "draft/08-testing.md").unlink()
    (draft_task / "draft/06-configs.md").unlink()
    (draft_task / "draft/99-extra.md").write_text("# Лишнее\n", encoding="utf-8")
    errors = validate_task(draft_task)
    assert "draft/08-testing.md: нет обязательной секции «Тестирование и регресс»" in errors
    assert not any("06-configs" in e for e in errors)
    assert "draft/99-extra.md: секции нет в шаблоне feature" in errors
    assert not any("устарел" in e for e in errors)


def test_draft_optional_section_absent_is_valid(draft_task):
    (draft_task / "draft/06-configs.md").unlink()
    _assemble(draft_task)
    assert validate_task(draft_task) == []


def test_draft_heading(draft_task):
    (draft_task / "draft/03-changes.md").write_text("## Доработки\n\nтекст\n", encoding="utf-8")
    (draft_task / "draft/04-kafka.md").write_text("# Топики Кафка\n\nтекст\n", encoding="utf-8")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/03-changes.md: первая строка должна быть «# Доработки»",
        "draft/04-kafka.md: первая строка должна быть «## Топики Кафка»",
    ]


def test_draft_traces(draft_task):
    _write(draft_task, "03-changes", "# Доработки", "Метод ‹R-99, X-1, D-05, IM-01, D-01›")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/03-changes.md: ссылка на несуществующий R-99",
        "draft/03-changes.md: «X-1» в ‹…› — не R-xx, IM-xx или D-xx",
        "draft/03-changes.md: ссылка на несуществующий D-05",
    ]


def test_draft_placeholders(draft_task):
    _write(draft_task, "03-changes", "# Доработки", "Текст ⚠ Q-PO-02. Ещё ⚠ Q-PO-01, ⚠ Q-SA-09 и ⚠ просто")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/03-changes.md: ⚠ Q-SA-09 — такого вопроса нет",
        "draft/03-changes.md: ⚠ без ID вопроса — пиши «⚠ Q-PO-xx» или «⚠ Q-SA-xx»",
    ]


def test_draft_stubs(draft_task):
    _write(draft_task, "08-testing", "# Тестирование и регресс", "Не применимо: нечего проверять ‹R-01›")
    _write(draft_task, "06-configs", "# Конфиги", "- Без изменений")
    _write(draft_task, "03-changes", "# Доработки", "**3. БД:**\n\nИзменений схемы БД не требуется — поле есть. ‹R-01›")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/06-configs.md: заглушка «Без изменений» — раздел или пункт без содержания не создаётся",
        "draft/08-testing.md: заглушка «Не применимо» — раздел или пункт без содержания не создаётся",
    ]


def test_draft_code_refs(draft_task):
    _write(draft_task, "03-changes", "# Доработки", "Правило ‹R-01› (код: lkp-back/app/Rules/Promocode.php:40)")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/03-changes.md: «код: lkp-back/app/Rules/Promocode.php:40» — ссылки на код остаются в артефактах задачи, не в ТЗ"
    ]


def test_draft_diagrams(draft_task):
    diagrams = draft_task / "draft/diagrams"
    diagrams.mkdir()
    (diagrams / "02-architecture-sequence.puml").write_text(
        "@startuml\nA -> B: <color:#red>x</color>\nalt x\n@enduml\n", encoding="utf-8"
    )
    _write(draft_task, "02-architecture", "# Архитектура и Процесс", "@diagram diagrams/02-architecture-sequence.puml")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/diagrams/02-architecture-sequence.puml: строка 3: блок «alt» не закрыт",
        "draft/diagrams/02-architecture-sequence.puml: строка 2: цвет по имени без «#»: <color:red>, «#» — только с HEX",
        'draft/diagrams/02-architecture-sequence.puml: нет строки autonumber "<b>[000]"',
        "draft/diagrams/02-architecture-sequence.puml: строка 3: «alt» — ветки разделами == == и заметками note",
    ]
    _write(draft_task, "02-architecture", "# Архитектура и Процесс", "@diagram diagrams/nope.puml")
    errors = validate_task(draft_task)
    assert "draft/02-architecture.md: нет файла draft/diagrams/nope.puml" in errors
    assert not any("устарел" in e for e in errors)


def test_draft_openapi(draft_task):
    (draft_task / "draft/api").mkdir()
    (draft_task / "draft/api/lkp-back.yaml").write_text(
        "openapi: 3.0.3\ninfo:\n  title: Payform.Lkp.Back.Api\n  version: 1.0.0\npaths:\n  /questionnaires:\n    post: {}\n",
        encoding="utf-8",
    )
    _write(draft_task, "03-changes", "# Доработки", "**2. API:**\n\n@openapi api/lkp-back.yaml")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/api/lkp-back.yaml: путь /questionnaires без префикса /api, /backoffice, /public или /internal"
    ]
    _write(draft_task, "03-changes", "# Доработки", "@openapi api/nope.yaml")
    assert "draft/03-changes.md: нет файла draft/api/nope.yaml" in validate_task(draft_task)


def test_draft_dto(draft_task):
    _write(draft_task, "04-kafka", "## Топики Кафка", "| `t` | x | a | b | {{DTO:SavedEvent}} | — |")
    _assemble(draft_task)
    assert validate_task(draft_task) == [
        "draft/04-kafka.md: нет файла draft/dto/SavedEvent.json для {{DTO:SavedEvent}}"
    ]


def test_draft_stale(draft_task):
    _write(draft_task, "03-changes", "# Доработки", "Новый текст ‹R-01›")
    assert validate_task(draft_task) == [
        "draft.md: устарел или правился вручную — правь секции в draft/ и запусти sa_draft.py assemble"
    ]


def test_draft_header(draft_task):
    _edit(draft_task / "draft.md", "label: ИИ-черновик", "label: готово")
    _edit(draft_task / "draft.md", "author: Иван Петров\n", "")
    assert validate_task(draft_task) == [
        "draft.md: во frontmatter нет ключа author",
        "draft.md: label должен быть ИИ-черновик",
    ]


def test_draft_md_required(draft_task):
    (draft_task / "draft.md").unlink()
    assert validate_task(draft_task) == ["draft.md: нет файла — собери: sa_draft.py assemble tasks/<KEY>"]


def test_stage_draft_without_draft(task_dir):
    _edit(task_dir / "state.json", '"stage": "clarify"', '"stage": "draft"')
    errors = validate_task(task_dir)
    assert "draft/01-brd.md: нет обязательной секции «BRD»" in errors
    assert errors[-1] == "draft.md: нет файла — собери: sa_draft.py assemble tasks/<KEY>"


def test_draft_without_template(draft_task):
    state = json.loads((draft_task / "state.json").read_text(encoding="utf-8"))
    del state["template"]
    (draft_task / "state.json").write_text(json.dumps(state), encoding="utf-8")
    errors = validate_task(draft_task)
    assert "draft: в state.json нет template — сначала /tdd-start" in errors
