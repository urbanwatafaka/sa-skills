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
C2_REL_RE = re.compile(r'^Rel_(?:D|U|L|R|Down|Up|Left|Right)\(\s*[\w.]+\s*,\s*[\w.]+\s*,\s*"([^"]*)"')
C2_NUMBER_RE = re.compile(r"^\d+\)")
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
    elif kind == "c2":
        if "skinparam linetype ortho" not in lines:
            errors.append("нет skinparam linetype ortho")
        for number, line in enumerate(lines, start=1):
            if line.startswith(("Rel(", "BiRel(")):
                errors.append(f"строка {number}: связи только Rel_D/Rel_U/Rel_L/Rel_R")
            rel = C2_REL_RE.match(line)
            if rel and not C2_NUMBER_RE.match(rel.group(1).strip()):
                errors.append(f"строка {number}: подпись связи начинается с номера шага: «1) …»")
    elif kind == "er":
        if "hide circle" not in lines:
            errors.append("нет hide circle")
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


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] != "check":
        print("использование: sa_puml.py check <файл.puml>...", file=sys.stderr)
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
