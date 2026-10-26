"""Проверка диаграмм PlantUML: структура и, если доступен, plantuml -syntax."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

DOCKER_IMAGE = "plantuml/plantuml"
MODE_STRUCTURE = "только структура (plantuml недоступен)"
STEP_RE = re.compile(r"\[(\d{3})\]")
QUOTED_RE = re.compile(r'"[^"]*"')
NOTE_AS_RE = re.compile(r'"\s+as\s')
TEXT_BLOCKS = {"note", "legend", "title", "ref"}
WORD_RE = re.compile(r"[a-z]+(?![a-z0-9_])")
SEQ_BLOCKS = {"alt", "opt", "loop", "par", "break", "critical", "group"}
ELSE_PARENTS = {"alt", "par", "critical", "if"}
CLOSERS = (
    (("end note", "endnote"), {"note"}),
    (("end box",), {"box"}),
    (("end fork", "end merge"), {"fork"}),
    (("endif", "end if"), {"if"}),
    (("endwhile", "end while"), {"while"}),
    (("repeat while", "repeatwhile"), {"repeat"}),
    (("end group",), {"group"}),
    (("end legend", "endlegend"), {"legend"}),
    (("end title", "endtitle"), {"title"}),
    (("end ref", "endref"), {"ref"}),
    (("end split",), {"split"}),
)


def structural_errors(text: str) -> list[str]:
    lines = text.splitlines()
    content = [line.strip() for line in lines if line.strip()]
    errors: list[str] = []
    if not content or not content[0].startswith("@startuml"):
        errors.append("первая строка должна быть @startuml")
    if not content or content[-1] != "@enduml":
        errors.append("последняя строка должна быть @enduml")
    stack: list[tuple[str, int]] = []
    braces: list[int] = []
    steps: list[int] = []

    def close(expected: set[str], number: int, line: str) -> None:
        if stack and stack[-1][0] in expected:
            stack.pop()
        else:
            errors.append(f"строка {number}: «{line}» без открывающего блока")

    in_comment = False
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        low = line.lower()
        if in_comment:
            in_comment = "'/" not in line
            continue
        if low.startswith("/'"):
            in_comment = "'/" not in line[2:]
            continue
        if not low or low.startswith("'"):
            continue
        closer = next((names for prefixes, names in CLOSERS if low.startswith(prefixes)), None)
        if stack and stack[-1][0] in TEXT_BLOCKS and stack[-1][0] not in (closer or ()):
            continue
        if closer is not None:
            close(closer, number, line)
            continue
        match = WORD_RE.match(low)
        word = match.group(0) if match else ""
        if word == "end":
            close(SEQ_BLOCKS, number, line)
        elif word in SEQ_BLOCKS or word in ("if", "while", "repeat", "box"):
            stack.append((word, number))
        elif word == "fork":
            if low.startswith("fork again"):
                if not (stack and stack[-1][0] == "fork"):
                    errors.append(f"строка {number}: «fork again» вне fork")
            else:
                stack.append(("fork", number))
        elif word in ("else", "elseif"):
            parents = {"if"} if word == "elseif" else ELSE_PARENTS
            if not (stack and stack[-1][0] in parents):
                where = "if" if word == "elseif" else "alt/par/critical/if"
                errors.append(f"строка {number}: «{word}» вне {where}")
        elif word == "legend":
            stack.append(("legend", number))
        elif word == "title" and low == "title":
            stack.append(("title", number))
        elif word == "ref" and low.startswith("ref over") and ":" not in QUOTED_RE.sub("", low):
            stack.append(("ref", number))
        elif word == "split":
            if not low.startswith("split again"):
                stack.append(("split", number))
        elif word in ("note", "hnote", "rnote"):
            if ":" not in QUOTED_RE.sub("", low) and not NOTE_AS_RE.search(low):
                stack.append(("note", number))
        if low.endswith("{"):
            braces.append(number)
        elif low.startswith("}"):
            if braces:
                braces.pop()
            else:
                errors.append(f"строка {number}: лишняя «}}»")
        for digits in STEP_RE.findall(line):
            steps.append(int(digits))
    errors += [f"строка {n}: блок «{name}» не закрыт" for name, n in stack]
    errors += [f"строка {n}: незакрытая «{{»" for n in braces]
    if any(b <= a for a, b in zip(steps, steps[1:])):
        errors.append("номера шагов [NNN] должны идти по возрастанию без повторов")
    return errors


COLOR_HASH_NAME_RE = re.compile(r"<color:#(?![0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?>)")
COLOR_SPLIT_RE = re.compile(r"<color:[^>]*>(?:(?!</color>).)*?\\n")
INCLUDE_RE = re.compile(r"^!include(?:url)?[ \t]+(\S+)", re.I)
SEQ_FORBIDDEN = ("alt", "loop", "opt", "par", "break", "critical", "group")
AUTONUMBER = 'autonumber "<b>[000]"'
QUEUE_RE = re.compile(r'^queue[ \t]+(?:"[^"]*"[ \t]+as[ \t]+(\w+)|(\w+))', re.I)
C2_REL_RE = re.compile(r'^Rel_(?:D|U|L|R|Down|Up|Left|Right)\(\s*([\w.]+)\s*,\s*([\w.]+)\s*,\s*"([^"]*)"')
C2_NUMBER_RE = re.compile(r"^\d+\)")
C2_QUEUE_RE = re.compile(r"^(?:System|Container)Queue(?:_Ext)?\(\s*(\w+)")
# Подпись стрелки в Kafka: «<топик> — <сообщение>»; топик как в коде (с «.», «-» или «_») или ХХХХХ, пока не согласован.
KAFKA_LABEL_RE = re.compile(r"^(?:[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)+|ХХХХХ)\s+—\s+\S")
COLOR_TAG_RE = re.compile(r"</?color[^>]*>")
KAFKA_LABEL_ERROR = "подпись стрелки в Kafka — «<топик> — <сообщение>»: pf-payment-receipt-cmds — CreateReceiptCommandEvent"
# Поле ER-таблицы с описанием после «//»: «OriginalReceiptId : uuid//Id исходного чека, который заменяет этот».
ER_FIELD_NOTE_RE = re.compile(r"//\s*\S")
ER_FIELD_NOTE_ERROR = "поле без описания — «Имя : тип//что хранит поле»"


def _kafka_label_ok(label: str) -> bool:
    return bool(KAFKA_LABEL_RE.match(COLOR_TAG_RE.sub("", label).strip()))
GATEWAY_PATH_RE = re.compile(r"(?<![\w/])/(?:api|backoffice|public|internal)/(?:api|backoffice|public|internal|v\d+)(?=/|\b)")


def kind_errors(name: str, text: str) -> list[str]:
    """Правила оформления по виду диаграммы — вид из суффикса имени файла: -sequence, -c2, -er."""
    errors: list[str] = []
    lines = [line.strip() for line in text.splitlines()]
    for number, line in enumerate(lines, start=1):
        if COLOR_HASH_NAME_RE.search(line):
            errors.append(f"строка {number}: цвет по имени без «#»: <color:red>, «#» — только с HEX")
        if COLOR_SPLIT_RE.search(line):
            errors.append(f"строка {number}: перенос \\n внутри <color:…> — отдельный тег на каждую строку")
        gateway = GATEWAY_PATH_RE.search(line)
        if gateway:
            errors.append(f"строка {number}: «{gateway.group(0)}…» — префикс шлюза; метод пиши, как он объявлен в сервисе")
        include = INCLUDE_RE.match(line)
        if include and not include.group(1).startswith("https://"):
            errors.append(f"строка {number}: !include — только полный https:// URL")
    stem = Path(name).stem
    kind = re.sub(r"-\d+$", "", stem).rsplit("-", 1)[-1]
    if kind == "sequence":
        if AUTONUMBER not in lines:
            errors.append(f"нет строки {AUTONUMBER}")
        for number, line in enumerate(lines, start=1):
            match = WORD_RE.match(line.lower())
            if match and match.group(0) in SEQ_FORBIDDEN:
                errors.append(f"строка {number}: «{match.group(0)}» — ветки разделами == == и заметками note")
        queues = {m.group(1) or m.group(2) for m in map(QUEUE_RE.match, lines) if m}
        for number, line in enumerate(lines, start=1):
            for queue in queues:
                if re.match(rf"{re.escape(queue)}\s*(?:\[[^\]]*\])?\s*-+>", line):
                    errors.append(
                        f"строка {number}: стрелка из {queue} — Kafka только со стрелками от сервиса: "
                        "запись Svc -> Kafka, чтение Svc --> Kafka"
                    )
                to_queue = re.match(rf"[\w.]+\s*(?:\[[^\]]*\])?\s*-+(?:\[[^\]]*\])?-?>+\s*{re.escape(queue)}\s*:(.*)$", line)
                if to_queue and not _kafka_label_ok(to_queue.group(1)):
                    errors.append(f"строка {number}: {KAFKA_LABEL_ERROR}")
    elif kind == "c2":
        queues = {m.group(1) for m in map(C2_QUEUE_RE.match, lines) if m}
        if "skinparam linetype ortho" not in lines:
            errors.append("нет skinparam linetype ortho")
        for number, line in enumerate(lines, start=1):
            if line.startswith(("Rel(", "BiRel(")):
                errors.append(f"строка {number}: связи только Rel_D/Rel_U/Rel_L/Rel_R")
            rel = C2_REL_RE.match(line)
            if rel and not C2_NUMBER_RE.match(rel.group(3).strip()):
                errors.append(f"строка {number}: подпись связи начинается с номера шага: «1) …»")
            if rel and queues & {rel.group(1), rel.group(2)}:
                if not _kafka_label_ok(C2_NUMBER_RE.sub("", rel.group(3).strip())):
                    errors.append(f"строка {number}: {KAFKA_LABEL_ERROR}")
    elif kind == "er":
        if "hide circle" not in lines:
            errors.append("нет hide circle")
        in_entity = False
        for number, line in enumerate(lines, start=1):
            if line.lower().startswith("entity") and line.endswith("{"):
                in_entity = True
            elif in_entity and line.startswith("}"):
                in_entity = False
            elif in_entity and line and not line.startswith(("--", "..", "==", "'")):
                if not ER_FIELD_NOTE_RE.search(COLOR_TAG_RE.sub("", line)):
                    errors.append(f"строка {number}: {ER_FIELD_NOTE_ERROR}")
    return errors


def find_renderer() -> list[str] | None:
    if shutil.which("plantuml"):
        return ["plantuml", "-syntax"]
    if shutil.which("docker"):
        try:
            found = subprocess.run(
                ["docker", "image", "inspect", DOCKER_IMAGE], capture_output=True, timeout=20
            ).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            found = False
        if found:
            return ["docker", "run", "--rm", "-i", DOCKER_IMAGE, "-syntax"]
    return None


def parse_syntax_output(out: str) -> list[str]:
    lines = [line.strip() for line in out.strip().splitlines()]
    if lines and lines[0] == "ERROR":
        where = lines[1] if len(lines) > 1 else "?"
        message = lines[2] if len(lines) > 2 else "синтаксическая ошибка"
        return [f"plantuml: строка {where}: {message}"]
    return []


def _syntax(renderer: list[str], text: str) -> list[str] | None:
    try:
        proc = subprocess.run(renderer, input=text, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    first = proc.stdout.strip().splitlines()[:1]
    if proc.returncode != 0 and first != ["ERROR"]:
        return None
    return parse_syntax_output(proc.stdout)


def check_files(paths: list[Path]) -> tuple[list[str], str]:
    renderer = find_renderer()
    if renderer is None:
        mode = MODE_STRUCTURE
    else:
        mode = "plantuml -syntax" if renderer[0] == "plantuml" else "plantuml в Docker"
    errors: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        found = structural_errors(text) + kind_errors(path.name, text)
        if not found and renderer is not None:
            result = _syntax(renderer, text)
            if result is None:
                renderer, mode = None, "только структура (plantuml не ответил)"
            else:
                found = result
        errors += [f"{path.name}: {e}" for e in found]
    return errors, mode


# Сообщение sequence: участник, необязательный цвет, стрелка, участник — `back [#red]-> pd: …`, `pd --> kafka`, `a -[#red]>> b`.
_PARTY = r'(?:"[^"]*"|[\w.]+|\[|\]|\?)'
MESSAGE_RE = re.compile(
    rf"^{_PARTY}\s*(?:\[[^\]]*\]\s*)?(?P<arrow>[<ox\\/]{{0,2}}-{{1,2}}(?:\[[^\]]*\])?-?[>ox\\/]{{0,2}})\s*{_PARTY}"
)
_NOTE_BLOCK_RE = re.compile(r"^[hr]?note\b")


def sequence_steps(text: str) -> list[tuple[int, int, str]]:
    """Сообщения sequence-диаграммы в порядке autonumber: (номер шага, строка файла, текст строки)."""
    steps: list[tuple[int, int, str]] = []
    in_note = in_comment = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        low = line.lower()
        if in_comment:
            in_comment = "'/" not in line
            continue
        if low.startswith("/'"):
            in_comment = "'/" not in line[2:]
            continue
        if in_note:
            in_note = not low.startswith("end note") and low not in ("endnote", "end hnote", "end rnote")
            continue
        if not low or low.startswith("'"):
            continue
        if _NOTE_BLOCK_RE.match(low):
            in_note = ":" not in QUOTED_RE.sub("", low) and not NOTE_AS_RE.search(low)
            continue
        match = MESSAGE_RE.match(line)
        if (match and ("<" in match.group("arrow") or ">" in match.group("arrow"))) or low.startswith("return "):
            steps.append((len(steps) + 1, number, line))
    return steps


STEP_REF_RE = re.compile(r"\*\*Шаги?\s+\[(\d{3})\](?:\s*[-–—]\s*\[(\d{3})\])?\*\*")
_DIAGRAM_LINE_RE = re.compile(r"^@diagram\s+(diagrams/[\w.-]+\.puml)\s*$")
_SEQUENCE_STEM_RE = re.compile(r"-sequence(?:-\d+)?$")


def _ranges(numbers: list[int]) -> str:
    parts: list[str] = []
    for n in numbers:
        if parts and parts[-1][1] == n - 1:
            parts[-1][1] = n
        else:
            parts.append([n, n])
    return ", ".join(f"[{a:03d}]" if a == b else f"[{a:03d}]-[{b:03d}]" for a, b in parts)


def step_ref_errors(text: str, draft_dir: Path) -> list[str]:
    """Отсылки «Шаг(и) [x]-[y]» под sequence-диаграммой против её шагов: нет лишних и нет неописанных.

    Описание диаграммы — строки после `@diagram …-sequence.puml` до следующего `@diagram` или закрытия `:::`.
    """
    errors: list[str] = []
    current: str | None = None
    refs: list[tuple[int, int]] = []

    def finish() -> None:
        path = draft_dir / current
        if not path.exists():
            return
        total = len(sequence_steps(path.read_text(encoding="utf-8")))
        name = Path(current).name
        if not refs:
            errors.append(f"{name}: под диаграммой нет отсылок «**Шаги [00X]-[00Y]**» — опиши шаги [001]-[{total:03d}]")
            return
        covered: set[int] = set()
        for start, end in refs:
            if end < start:
                errors.append(f"{name}: «Шаги [{start:03d}]-[{end:03d}]» — конец диапазона раньше начала")
                continue
            if end > total:
                errors.append(f"{name}: «[{end:03d}]» — на диаграмме шагов {total}; номера — из sa_puml.py steps")
            covered.update(range(start, min(end, total) + 1))
        missing = [n for n in range(1, total + 1) if n not in covered]
        if missing:
            errors.append(f"{name}: шаги {_ranges(missing)} не описаны ни одним пунктом «Описания шагов»")

    for line in text.splitlines():
        stripped = line.strip()
        diagram = _DIAGRAM_LINE_RE.match(stripped)
        if diagram or stripped == ":::":
            if current:
                finish()
            current, refs = None, []
            if diagram and _SEQUENCE_STEM_RE.search(Path(diagram.group(1)).stem):
                current = diagram.group(1)
            continue
        if current:
            refs += [(int(a), int(b or a)) for a, b in STEP_REF_RE.findall(line)]
    if current:
        finish()
    return errors


def render_steps(path: Path) -> str:
    steps = sequence_steps(path.read_text(encoding="utf-8"))
    if not steps:
        return f"{path.name}: сообщений нет"
    lines = [f"{path.name}: шагов {len(steps)}"]
    lines += [f"[{step:03d}] строка {line}: {text}" for step, line, text in steps]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "steps":
        path = Path(argv[1])
        if not path.exists():
            print(f"ошибка: нет файла {path}", file=sys.stderr)
            return 1
        print(render_steps(path))
        return 0
    if len(argv) < 2 or argv[0] != "check":
        print("использование:\n  sa_puml.py check <файл.puml>...\n  sa_puml.py steps <файл-sequence.puml>", file=sys.stderr)
        return 2
    paths = [Path(p) for p in argv[1:]]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print(f"ошибка: нет файлов: {', '.join(missing)}", file=sys.stderr)
        return 1
    errors, mode = check_files(paths)
    if errors:
        print("\n".join(errors))
        print(f"проверка: {mode}")
        return 1
    print(f"OK: диаграмм {len(paths)}")
    print(f"проверка: {mode}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
