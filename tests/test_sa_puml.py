import subprocess

import pytest

import sa_puml
from sa_puml import (
    MODE_STRUCTURE, check_files, find_renderer, main, parse_syntax_output, sequence_steps, step_ref_errors,
    structural_errors,
)

STEPS_SEQ = """\
@startuml
autonumber "<b>[000]"
actor "Мерчант" as merchant
participant "lkp-back" as back
queue "Kafka" as kafka
' merchant -> back: закомментировано
== Раздел ==
activate merchant
merchant -> back: POST /api/x
back [#red]-> kafka: <color:red>Событие</color>
back -[#red]>> back: самострелка
note right of back: a -> b не шаг
note over back
  c -> d не шаг
end note
back --> merchant: 200
return ok
@enduml
"""


def test_sequence_steps():
    steps = sequence_steps(STEPS_SEQ)
    assert [s[0] for s in steps] == [1, 2, 3, 4, 5]
    assert [s[2] for s in steps] == [
        "merchant -> back: POST /api/x",
        "back [#red]-> kafka: <color:red>Событие</color>",
        "back -[#red]>> back: самострелка",
        "back --> merchant: 200",
        "return ok",
    ]
    assert steps[0][1] == 9


def test_step_ref_errors(tmp_path):
    (tmp_path / "diagrams").mkdir()
    (tmp_path / "diagrams/02-architecture-sequence.puml").write_text(STEPS_SEQ, encoding="utf-8")
    (tmp_path / "diagrams/02-architecture-c2.puml").write_text("@startuml\n@enduml\n", encoding="utf-8")
    ok = ("@diagram diagrams/02-architecture-c2.puml\n:::expand Процесс: П\n"
          "@diagram diagrams/02-architecture-sequence.puml\n1. x **Шаг [001]**\n2. y **Шаги [002]–[005]**\n:::\n")
    assert step_ref_errors(ok, tmp_path) == []
    assert step_ref_errors(ok.replace("[005]", "[007]"), tmp_path) == [
        "02-architecture-sequence.puml: «[007]» — на диаграмме шагов 5; номера — из sa_puml.py steps"
    ]
    assert step_ref_errors(ok.replace("[002]–[005]", "[003]-[004]"), tmp_path) == [
        "02-architecture-sequence.puml: шаги [002], [005] не описаны ни одним пунктом «Описания шагов»"
    ]
    assert step_ref_errors(ok.replace("[002]–[005]", "[005]-[002]"), tmp_path)[0].endswith("конец диапазона раньше начала")
    bare = ":::expand Процесс: П\n@diagram diagrams/02-architecture-sequence.puml\n:::\n1. **Шаг [001]**\n"
    assert step_ref_errors(bare, tmp_path) == [
        "02-architecture-sequence.puml: под диаграммой нет отсылок «**Шаги [00X]-[00Y]**» — опиши шаги [001]-[005]"
    ]


def test_steps_cli(tmp_path, capsys):
    path = tmp_path / "x-sequence.puml"
    path.write_text(STEPS_SEQ, encoding="utf-8")
    assert main(["steps", str(path)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "x-sequence.puml: шагов 5"
    assert out[1] == "[001] строка 9: merchant -> back: POST /api/x"
    assert main(["steps", str(tmp_path / "nope.puml")]) == 1

SEQ = """\
@startuml
participant "lkp-back" as back <<changed>> #FCF3CF
participant "partners-dashboard" as pd <<new>> #D5F5E3
back -> pd : [001] HTTP GET promocode/check-usage
alt промокод свой
  pd --> back : [002] 200 {own: true}
else чужой
  pd --> back : [003] 200 {own: false}
end
note over back
  alt внутри заметки не считается [009]
end note
@enduml
"""

ACTIVITY = """\
@startuml
start
:[001] Ввод промокода;
if ([002] Свой?) then (да)
  #D5F5E3:[003] Отказ;
elseif (пусто) then
  :[004] Пропуск;
else (нет)
  :[005] Принять;
endif
while (повтор?)
  :[006] Повтор;
endwhile
fork
  :[007] A;
fork again
  :[008] B;
end fork
stop
@enduml
"""

ER = """\
@startuml
entity "promocodes" as promocodes <<changed>> #FCF3CF {
  * id : bigint
  --
  owner_inn : varchar(12)
}
entity "partners" as partners {
  * id : bigint
}
partners ||--o{ promocodes
@enduml
"""


def test_kafka_arrows_only_from_service():
    text = '@startuml\nautonumber "<b>[000]"\nparticipant "lkp-back" as back\nqueue "Kafka" as kafka\n' \
        "back -> kafka: Event\nback --> kafka: Event\nkafka -> back: Event\nkafka [#red]--> back: Event\n@enduml\n"
    errors = sa_puml.kind_errors("x-sequence.puml", text)
    assert [e.split(":", 1)[0] for e in errors] == ["строка 7", "строка 8"]
    assert "стрелка из kafka" in errors[0]


def test_gateway_prefix_on_arrows():
    text = '@startuml\nautonumber "<b>[000]"\nA -> B: GET /api/backoffice/v1/orders\nA -> B: GET /backoffice/orders\n@enduml\n'
    errors = sa_puml.kind_errors("x-sequence.puml", text)
    assert errors == ["строка 3: «/api/backoffice…» — префикс шлюза; метод пиши, как он объявлен в сервисе"]


def test_c2_relations_numbered():
    text = '@startuml\nskinparam linetype ortho\nRel_D(a, b, "1) вызов")\nRel_R(b, c, "запрос")\n' \
        'Rel_U(c, d, " 12) ответ", $tags="read")\n@enduml\n'
    assert sa_puml.kind_errors("x-c2.puml", text) == ["строка 4: подпись связи начинается с номера шага: «1) …»"]


@pytest.mark.parametrize("text", [SEQ, ACTIVITY, ER])
def test_valid(text):
    assert structural_errors(text) == []


def _one(text, fragment):
    errors = structural_errors(text)
    assert any(fragment in e for e in errors), errors


def test_start_and_end():
    _one(SEQ.replace("@startuml\n", "", 1), "первая строка должна быть @startuml")
    _one(SEQ.replace("@enduml\n", ""), "последняя строка должна быть @enduml")


def test_unclosed_and_stray():
    _one(SEQ.replace("end\nnote", "note"), "блок «alt» не закрыт")
    _one(SEQ.replace("@enduml", "end\n@enduml"), "«end» без открывающего блока")
    _one(ACTIVITY.replace("endif\n", ""), "блок «if» не закрыт")
    _one(ACTIVITY.replace("end fork\n", ""), "блок «fork» не закрыт")


def test_else_outside():
    _one("@startuml\nelse нет\n@enduml\n", "«else» вне")


def test_names_with_keyword_prefix_are_not_blocks():
    assert structural_errors("@startuml\nif_service -> alt_x : [001] вызов\n@enduml\n") == []


def test_steps():
    assert structural_errors(SEQ.replace("[001]", "[01] items[0]")) == []
    _one(SEQ.replace("[002]", "[004]"), "по возрастанию без повторов")


def test_braces():
    _one(ER.replace("}\nentity", "entity", 1), "незакрытая «{»")
    _one(ER.replace("@enduml", "}\n@enduml"), "лишняя «}»")


def test_parse_syntax_output():
    assert parse_syntax_output("SEQUENCE\n(4 participants)\n") == []
    assert parse_syntax_output("ERROR\n7\nSyntax Error?\n") == ["plantuml: строка 7: Syntax Error?"]


def test_find_renderer(monkeypatch):
    monkeypatch.setattr(sa_puml.shutil, "which", lambda name: "/usr/bin/plantuml" if name == "plantuml" else None)
    assert find_renderer() == ["plantuml", "-syntax"]
    monkeypatch.setattr(sa_puml.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr(sa_puml.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0))
    assert find_renderer() == ["docker", "run", "--rm", "-i", "plantuml/plantuml", "-syntax"]
    monkeypatch.setattr(sa_puml.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1))
    assert find_renderer() is None
    monkeypatch.setattr(sa_puml.shutil, "which", lambda name: None)
    assert find_renderer() is None


def test_check_files_structure_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sa_puml, "find_renderer", lambda: None)
    good, bad = tmp_path / "good.puml", tmp_path / "bad.puml"
    good.write_text(SEQ, encoding="utf-8")
    bad.write_text(SEQ.replace("@enduml\n", ""), encoding="utf-8")
    errors, mode = check_files([good, bad])
    assert mode == MODE_STRUCTURE
    assert errors == ["bad.puml: последняя строка должна быть @enduml"]
    assert main(["check", str(good)]) == 0
    assert capsys.readouterr().out == f"OK: диаграмм 1\nпроверка: {MODE_STRUCTURE}\n"
    assert main(["check", str(bad)]) == 1
    assert main([]) == 2


def test_check_files_with_renderer(tmp_path, monkeypatch):
    monkeypatch.setattr(sa_puml, "find_renderer", lambda: ["plantuml", "-syntax"])
    monkeypatch.setattr(
        sa_puml.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="ERROR\n3\nSyntax Error?\n"),
    )
    path = tmp_path / "x.puml"
    path.write_text(SEQ, encoding="utf-8")
    assert check_files([path]) == (["x.puml: plantuml: строка 3: Syntax Error?"], "plantuml -syntax")


def test_valid_plantuml_forms_accepted():
    body = "\n".join([
        "@startuml", "/' блок", "alt внутри комментария", "'/",
        "title", "alt в заголовке", "end title", "title Один", "legend right", "if x {", "end legend", "endlegend",
        "ref over A, B", "loop", "end ref", "ref over A : x", "split", "split again", "end split",
        'note "text" as N1', "note over A : x", 'note over "A: b"', "if", "end note", "@enduml",
    ])
    body = body.replace("if x {\n", "").replace("end legend\nendlegend", "end legend").replace("\nif\nend note", "\nend note")
    assert structural_errors(body + "\n") == []


def test_syntax_returncode(monkeypatch):
    def fake(code, out):
        monkeypatch.setattr(sa_puml.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, code, stdout=out, stderr="boom"))
        return sa_puml._syntax(["plantuml", "-syntax"], "x")
    assert fake(1, "") is None
    assert fake(0, "SEQUENCE\n") == []
    assert fake(1, "ERROR\n3\nbad\n") == ["plantuml: строка 3: bad"]
