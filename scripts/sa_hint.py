"""Подсказка к сообщению аналитика (хук UserPromptSubmit): статус задач, ключи которых есть в сообщении.

Читает JSON хука из stdin (prompt, cwd), печатает строки статуса — их видит Claude как контекст. Никогда не падает:
любая ошибка — тишина и код 0, чтобы не мешать сообщению.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ANSWER_RE = re.compile(r"\bQ-(?:PO|SA)-\d{2,}\s*[:—-]")
MAX_TASKS = 3
PREFIX = "[sa-skills]"


def _summary(task_dir: Path) -> str:
    from sa_status import build_status

    lines = build_status(task_dir).splitlines()
    pick = lambda start: next((l.split(":", 1)[1].strip() for l in lines if l.startswith(start)), "")
    head = lines[0].removeprefix("Задача: ")
    parts = [head, f"вопросы PO {pick('Вопросы PO')}", f"аналитику {pick('Вопросы аналитику')}"]
    review = pick("Ревью")
    if review:
        parts.append(f"ревью {review}")
    return f"{PREFIX} {' · '.join(parts)} · следующий шаг: {pick('Следующий шаг')}"


def hints(prompt: str, cwd: Path) -> list[str]:
    tasks = cwd / "tasks"
    if not tasks.is_dir():
        return []
    known = {p.name for p in tasks.iterdir() if (p / "state.json").exists()}
    # Ключ — имя папки задачи в tasks/, целым словом: PF2-3964, но не PF2-39640.
    positions = {k: m.start() for k in known if (m := re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", prompt))}
    keys = sorted(positions, key=positions.get)[:MAX_TASKS]
    if not keys and ANSWER_RE.search(prompt):
        if len(known) == 1:
            keys = sorted(known)
        elif known:
            return [f"{PREFIX} в сообщении ответы на вопросы без ключа задачи; задач несколько ({', '.join(sorted(known))}) — уточни у аналитика"]
    out = []
    for key in keys:
        try:
            out.append(_summary(tasks / key))
        except Exception:  # noqa: BLE001 — подсказка не должна ломать сообщение
            continue
    if out:
        out.append(f"{PREFIX} как продолжать — скил sa-skills:sa-flow (явную команду /tdd-… аналитика выполняй как есть)")
    return out


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
        lines = hints(str(data.get("prompt") or ""), Path(data.get("cwd") or Path.cwd()))
        if lines:
            print("\n".join(lines))
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n", encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
