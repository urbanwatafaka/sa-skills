"""Манифесты шаблонов ТЗ: shared/templates/<тип>.yaml (плоское подмножество YAML)."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sa_artifacts import ArtifactError

PLUGIN_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PLUGIN_DIR / "shared" / "templates"
BLOCKS_DIR = PLUGIN_DIR / "shared" / "blocks"
DIAGRAM_KINDS = {"c2", "sequence", "activity", "er", "state"}
NAME_RE = re.compile(r"[a-z][a-z0-9-]*")
SECTION_ID_RE = re.compile(r"\d{2}-[a-z0-9-]+")
VERSION_RE = re.compile(r"\d+\.\d+")
SECTION_KEYS = ("id", "title", "block", "required", "diagrams", "im_kinds")
LEVELS = {"1": 1, "2": 2}


@dataclass
class Section:
    id: str
    title: str
    block: str | None
    required: bool
    diagrams: list[str]
    im_kinds: list[str]
    level: int = 1

    @property
    def heading(self) -> str:
        return "#" * self.level + " " + self.title


@dataclass
class Manifest:
    name: str
    version: str
    title: str
    sections: list[Section]


def _value(raw: str):
    value = raw.strip()
    if value in ("true", "false"):
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [item.strip() for item in inner.split(",")] if inner else []
    return value


def _pair(line: str, number: int) -> tuple[str, object]:
    if ":" not in line:
        raise ArtifactError(f"манифест, строка {number}: ожидается «ключ: значение»")
    key, raw = line.split(":", 1)
    return key.strip(), _value(raw)


def _section(item: dict) -> Section:
    sid = item.get("id", "?")
    missing = [key for key in SECTION_KEYS if key not in item]
    if missing:
        raise ArtifactError(f"секция {sid}: нет ключей {', '.join(missing)}")
    if not (isinstance(sid, str) and SECTION_ID_RE.fullmatch(sid)):
        raise ArtifactError(f"секция {sid}: id вида 05-api")
    if not isinstance(item["title"], str) or not item["title"]:
        raise ArtifactError(f"секция {sid}: пустой title")
    if not isinstance(item["required"], bool):
        raise ArtifactError(f"секция {sid}: required — true или false")
    for key in ("diagrams", "im_kinds"):
        if not isinstance(item[key], list):
            raise ArtifactError(f"секция {sid}: {key} — список вида [a, b]")
    unknown = sorted(set(item["diagrams"]) - DIAGRAM_KINDS)
    if unknown:
        raise ArtifactError(f"секция {sid}: неизвестные диаграммы {', '.join(unknown)}")
    block = None if item["block"] in ("—", "-", "") else str(item["block"])
    if block is not None and not (BLOCKS_DIR / f"{block}.md").exists():
        raise ArtifactError(f"секция {sid}: нет блока shared/blocks/{block}.md")
    level = LEVELS.get(str(item.get("level", "1")))
    if level is None:
        raise ArtifactError(f"секция {sid}: level — 1 или 2")
    return Section(sid, item["title"], block, item["required"], item["diagrams"], item["im_kinds"], level)


def parse_manifest(text: str, name: str) -> Manifest:
    top: dict = {}
    items: list[dict] = []
    in_sections = False
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            key, value = _pair(line, number)
            in_sections = key == "sections"
            if not in_sections:
                top[key] = value
        elif not in_sections:
            raise ArtifactError(f"манифест, строка {number}: отступ вне sections")
        elif line.lstrip().startswith("- "):
            key, value = _pair(line.lstrip()[2:], number)
            items.append({key: value})
        elif items:
            key, value = _pair(line, number)
            items[-1][key] = value
        else:
            raise ArtifactError(f"манифест, строка {number}: ожидается «- id: …»")
    for key in ("name", "version", "title"):
        if not isinstance(top.get(key), str) or not top[key]:
            raise ArtifactError(f"в манифесте нет {key}")
    if top["name"] != name:
        raise ArtifactError(f"name: {top['name']}, ожидается {name}")
    if not VERSION_RE.fullmatch(top["version"]):
        raise ArtifactError("version: формат мажор.минор, например 1.0")
    if not items:
        raise ArtifactError("в манифесте нет секций")
    sections = [_section(item) for item in items]
    ids = [s.id for s in sections]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ArtifactError(f"секция повторяется: {', '.join(duplicates)}")
    return Manifest(top["name"], top["version"], top["title"], sections)


def load_manifest(name: str) -> Manifest:
    if not NAME_RE.fullmatch(name):
        raise ArtifactError(f"имя шаблона «{name}»: латиница, цифры, дефис")
    path = TEMPLATES_DIR / f"{name}.yaml"
    if not path.exists():
        raise ArtifactError(f"шаблона {name} нет: {path} не найден")
    return parse_manifest(path.read_text(encoding="utf-8"), name)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "version":
        print("использование: sa_template.py version <тип>", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(argv[1])
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    print(f"{manifest.name}@{manifest.version}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main(sys.argv[1:]))
