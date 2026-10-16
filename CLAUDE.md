# sa-skills — правила работы с репозиторием

Плагин Claude Code для пайплайна системного аналитика (`/tdd-impact` → `/tdd-start` → `/tdd-clarify` → `/tdd-draft`). Обзор — `README.md`, дизайн — `docs/superpowers/specs/`.

## Куда коммитить

- Единственный remote — `origin` = https://github.com/urbanwatafaka/sa-skills, ветка `main`.
- Каждую законченную правку плагина: тесты → коммит → `git push origin main`. Не копить локальные коммиты.
- Исходный репозиторий команды (gibus.prodamus.ru/v.varaksin/sa-skills) не трогать: не добавлять его remote и ничего туда не пушить.

## Перед коммитом

- `python -m pytest -q` — всё зелёное. Известное исключение на Windows: `tests/test_sa_paths.py::test_format` (сравнивает пути с `/`, на Windows печатаются `\`).
- Поменял скил, блок, шаблон или скрипт — поправь тесты-контракты (`tests/test_skills_contract.py`, `tests/test_shared_docs.py`) и фикстуру `tests/fixtures/LKP-DEMO/`, если она зависит от изменения.
- Меняется структура шаблона ТЗ — подними `version` в `shared/templates/<тип>.yaml`. Заметная правка плагина — подними `version` в `.claude-plugin/plugin.json` и в тестах, которые её проверяют.

## Откуда правила оформления

Шаблон `feature` (тип 1 — ТЗ на доработку), блоки `shared/blocks/`, `shared/rules/writing-style.md`, скилы `puml-*` и раздел публикации в `shared/access/adapters.md` перенесены из личного скила аналитика `~/.claude/skills/zuyza-write-confluence/SKILL.md` (эталоны Confluence pageId 110167390, 110167415, 110166633). При расхождении источник истины — этот скил и эталонные страницы. Плагин собирает только тип 1; типы 2–5 не переносятся.

Сверил блоки с эталоном — запиши его версию в `shared/etalons.md`: по ней `/tdd-draft` проверяет, не устарели ли блоки.

## Окружение (Windows)

- Скилы вызывают `python3`; на этой машине `python3.exe` — копия `python.exe` в папке Python 3.13. Вывод скриптов требует UTF-8: в `~/.claude/settings.json` задан `PYTHONUTF8=1`.
- Скрипты — только стандартная библиотека Python ≥ 3.10.
- Держи клон по ASCII-пути без кириллицы: длинные кириллические пути ломают git.
