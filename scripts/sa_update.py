"""Точечное обновление черновика: что изменилось с последней сборки и какие секции это затрагивает."""
from __future__ import annotations

import difflib
import sys
from dataclasses import dataclass
from pathlib import Path

from sa_artifacts import ArtifactError, find_refs
from sa_draft import (
    block_section, is_human, mark, placeholders, release, row_hashes, scope_of, section_path, section_texts,
    task_data, task_manifest, trace_refs,
)
from sa_review import review_rows
from sa_state import ARTIFACTS, PUBLISH_FILE, file_sha1, load_state, write_atomic

PROPOSALS_DIR = "proposals"
HUMAN = "правка человека — только предложение"
REGENERATE = "перегенерировать"
CREATE = "создать"


@dataclass
class SectionUpdate:
    id: str
    reasons: list[str]
    human: bool
    missing: bool = False


@dataclass
class UpdatePlan:
    snapshot: bool
    new: list[str]
    changed: list[str]
    removed: list[str]
    accepted: list[str]
    sections: list[SectionUpdate]
    unbound: list[str]
    proposals: list[str]
    published: str | None


def _published(task_dir: Path, state: dict) -> str | None:
    published = state.get("published")
    if not isinstance(published, dict):
        return None
    publish = task_dir / PUBLISH_FILE
    changed = not publish.exists() or file_sha1(publish) != published.get("hash")
    return (
        f"Опубликовано: {published.get('url')}"
        + (" — черновик изменился после публикации" if changed else "")
        + ". Перед повторной публикацией сверь страницу с прошлой публикацией и перенеси ручные правки "
        "(shared/access/adapters.md, «Публикация ТЗ», шаг 6)."
    )


def build_plan(task_dir: Path) -> UpdatePlan:
    if not (task_dir / ARTIFACTS["draft"]).exists():
        raise ArtifactError("нет draft.md — сначала /tdd-draft")
    state = load_state(task_dir)
    manifest = task_manifest(state)
    data = task_data(task_dir)
    texts = section_texts(task_dir, manifest)
    current = row_hashes(task_dir)
    old = state.get("rows") if isinstance(state.get("rows"), dict) else None
    snapshot = old is not None
    old = old if snapshot else current
    new = [i for i in current if i not in old]
    changed = [i for i in current if i in old and old[i] != current[i]]
    removed = [i for i in old if i not in current]

    reasons: dict[str, list[str]] = {s.id: [] for s in manifest.sections}

    def add(sid: str | None, reason: str) -> bool:
        if sid not in reasons:
            return False
        if reason not in reasons[sid]:
            reasons[sid].append(reason)
        return True

    traces = {sid: set(trace_refs(text)) for sid, text in texts.items()}
    holders = {sid: {q for q in placeholders(text) if q} for sid, text in texts.items()}
    questions = {q.id: q for q in data["questions"]}
    decisions = {row["ID"]: row for row in data["decisions"]}
    impact = {row["ID"]: row for row in data["impact"]}
    unbound: list[str] = []

    for ref in changed + removed:
        hit = False
        for sid, refs in traces.items():
            if ref in refs:
                hit = add(sid, ref) or hit
        if not hit:
            unbound.append(ref)
    for ref in new:
        hit = False
        if ref.startswith("D-"):
            row = decisions[ref]
            q_ids = [r for r in find_refs(row["← Q"]) if r.startswith("Q-")]
            for sid in texts:
                held = [q for q in q_ids if q in holders[sid]]
                if held:
                    hit = add(sid, f"{ref} (⚠ {', '.join(held)})") or hit
            if not hit:
                links = {r for q in q_ids if q in questions for r in questions[q].refs}
                links |= {r for r in find_refs(row["Решение"]) if not r.startswith("Q-")}
                for sid, refs in traces.items():
                    if links & refs:
                        hit = add(sid, ref) or hit
        elif ref.startswith("IM-"):
            if scope_of(data, ref) == "вне скоупа":
                continue
            for s in manifest.sections:
                if impact[ref]["Вид"] in s.im_kinds:
                    hit = add(s.id, ref) or hit
            hit = add(block_section(manifest, "changes"), ref) or hit
        else:
            hit = add(block_section(manifest, "brd"), ref)
        if not hit:
            unbound.append(ref)

    for sid, held in holders.items():
        for q in sorted(held):
            if q in questions and questions[q].status != "open" and not any(q in r for r in reasons[sid]):
                add(sid, f"⚠ {q} закрыт")

    accepted: list[str] = []
    if (task_dir / ARTIFACTS["review"]).exists():
        for row in review_rows(task_dir):
            if row["Статус"] == "принято":
                accepted.append(row["ID"])
                if not add(row["Где"], row["ID"]):
                    unbound.append(row["ID"])

    entries = state.get("sections") if isinstance(state.get("sections"), dict) else {}
    sections = [
        SectionUpdate(
            s.id,
            reasons[s.id],
            s.id in texts and is_human(entries.get(s.id), section_path(task_dir, s.id)),
            s.id not in texts,
        )
        for s in manifest.sections if reasons[s.id]
    ]
    proposals_dir = task_dir / PROPOSALS_DIR
    proposals = sorted(p.stem for p in proposals_dir.glob("*.md")) if proposals_dir.is_dir() else []
    return UpdatePlan(snapshot, new, changed, removed, accepted, sections, unbound, proposals, _published(task_dir, state))


def _none(items: list[str]) -> str:
    return ", ".join(items) if items else "нет"


def render_plan(plan: UpdatePlan) -> str:
    if plan.snapshot:
        lines = [f"Изменения с последней сборки: новые {_none(plan.new)}; изменены {_none(plan.changed)}; удалены {_none(plan.removed)}"]
    else:
        lines = ["Снимка строк нет (черновик собран до /tdd-update) — изменения BRD, карты и решений не отслежены"]
    lines.append(f"Принятые замечания: {_none(plan.accepted)}")
    if plan.sections:
        lines.append("Секции к обновлению:")
        lines += [
            f"{s.id} | {CREATE if s.missing else HUMAN if s.human else REGENERATE} | {', '.join(s.reasons)}"
            for s in plan.sections
        ]
    else:
        lines.append("Секции к обновлению: нет")
    if plan.unbound:
        lines.append(f"Без привязки: {', '.join(plan.unbound)} — реши по тексту, какие секции они меняют, или спроси аналитика")
    if plan.proposals:
        lines.append(f"Предложения ждут решения: {', '.join(plan.proposals)}")
    if plan.published:
        lines.append(plan.published)
    return "\n".join(lines)


def _proposal(task_dir: Path, sid: str) -> Path:
    path = task_dir / PROPOSALS_DIR / f"{sid}.md"
    if not path.exists():
        raise ArtifactError(f"нет предложения {PROPOSALS_DIR}/{sid}.md")
    return path


def proposal_diff(task_dir: Path, sid: str) -> str:
    proposal = _proposal(task_dir, sid)
    current = section_path(task_dir, sid)
    old = current.read_text(encoding="utf-8").splitlines(keepends=True) if current.exists() else []
    lines = difflib.unified_diff(old, proposal.read_text(encoding="utf-8").splitlines(keepends=True),
                                 f"draft/{sid}.md", f"{PROPOSALS_DIR}/{sid}.md")
    return "".join(lines) or "отличий нет"


def apply_proposal(task_dir: Path, sid: str) -> None:
    proposal = _proposal(task_dir, sid)
    text = proposal.read_text(encoding="utf-8")
    write_atomic(section_path(task_dir, sid), text)
    release(task_dir, [sid])
    mark(task_dir, [sid])
    proposal.unlink()


def drop_proposal(task_dir: Path, sid: str) -> None:
    _proposal(task_dir, sid).unlink()


USAGE = (
    "использование:\n"
    "  sa_update.py plan <папка задачи>\n"
    "  sa_update.py diff <папка задачи> <секция>\n"
    "  sa_update.py apply <папка задачи> <секция>\n"
    "  sa_update.py drop <папка задачи> <секция>"
)


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if not ((command == "plan" and len(argv) == 2) or (command in ("diff", "apply", "drop") and len(argv) == 3)):
        print(USAGE, file=sys.stderr)
        return 2
    task_dir = Path(argv[1])
    try:
        if command == "plan":
            print(render_plan(build_plan(task_dir)))
        elif command == "diff":
            print(proposal_diff(task_dir, argv[2]))
        elif command == "apply":
            apply_proposal(task_dir, argv[2])
            print(f"предложение принято: draft/{argv[2]}.md")
        else:
            drop_proposal(task_dir, argv[2])
            print(f"предложение отклонено: {argv[2]}")
    except ArtifactError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
