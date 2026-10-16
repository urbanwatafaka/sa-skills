import subprocess

import pytest

import sa_puml
from sa_puml import MODE_STRUCTURE, check_files, find_renderer, main, parse_syntax_output, structural_errors

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
