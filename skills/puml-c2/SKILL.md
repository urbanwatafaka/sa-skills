---
name: puml-c2
description: C2-диаграмма (контейнеры) на C4-PlantUML для ТЗ — затронутые системы, БД и Kafka, ortho-связи Rel_D/U/L/R с нумерацией 1) 2) по ходу процесса, без цветовой маркировки нового. Используй для «C2 — Архитектура» в /tdd-draft или когда просят C2/C4-диаграмму.
allowed-tools: Bash(python3:*)
---

# puml-c2

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Перед работой прочитай `<плагин>/shared/blocks/diagrams.md`.

## Когда применять

- Нужно показать, какие системы, БД и Kafka участвуют в доработке и как связаны. Одна C2 на документ, открыто, не под «Раскрыть».

Не применять: порядок вызовов — `puml-sequence`; структура таблиц — `puml-er`.

## Каркас

```plantuml
@startuml
!includeurl https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml
skinparam linetype ortho
skinparam nodesep 120
skinparam ranksep 100
skinparam padding 20
skinparam ArrowFontSize 16
skinparam ArrowColor #333333
skinparam ArrowThickness 4
AddRelTag("read", $lineStyle = DashedLine())

Person(merchant, "Мерчант")
System(front, "lkp-front", "ЛК мерчанта")
System(back, "lkp-back", "Бэкенд ЛК")
System(pd, "partners-dashboard", "Промокоды партнёров")
SystemQueue(kafka, "Kafka")

Rel_D(merchant, front, "1) Сохраняет анкету")
Rel_D(front, back, "2) POST /api/questionnaires")
Rel_R(back, pd, "3) GET /internal/promocodes/{code}/owner")
Rel_D(back, kafka, "4) QuestionnaireSavedEvent")
Rel_D(pd, kafka, "5) QuestionnaireSavedEvent", $tags="read")
@enduml
```

## Соглашения

- `!includeurl` — всегда полный `https://` URL, не `<C4/...>` и не локальный путь.
- `skinparam linetype ortho`, связи только `Rel_D`/`Rel_U`/`Rel_L`/`Rel_R`, без пересечений.
- Компоновка сверху вниз: инициатор наверху, системы и БД ниже по уровням вызовов; по возможности ближе к квадрату. Перед связями выпиши граф смежности: связанные элементы — соседи, элемент с многими связями (общая БД) — с края цепочки, связи разводи в разные стороны.
- Каждая связь начинается с номера `1)`, `2)` … в порядке старта процесса.
- Одиночный внутренний сервис — `System()`, внешняя система — `System_Ext()`. `System_Boundary` — только рамка вокруг нескольких вложенных `Container`/`ContainerDb` (например, `System_Boundary(pf1, "ПФ1 (монолит)")` с кодом PHP 5.6 и БД `ishop_4 + prodamus`).
- Kafka — `SystemQueue(kafka, "Kafka")`, не подпись на связи сервис→сервис. Стрелки от сервиса к Kafka: запись — сплошная, чтение — `$tags="read"`. Несколько событий одного сервиса в одну сторону — одной связью с перечислением.
- Без цветовой маркировки нового, если аналитик не попросил.
- Элементы — только системы из карты влияния в скоупе и роли BRD.

## Чек-лист

- [ ] Каждый элемент есть в карте влияния или ролях BRD.
- [ ] У каждой связи есть номер `N)`, связи только `Rel_D/U/L/R`.
- [ ] Kafka — отдельный `SystemQueue`, чтение пунктиром.
- [ ] `!includeurl` с полным `https://` URL.

## Проверка

`python3 <плагин>/scripts/sa_puml.py check <путь к .puml>` — исправляй, пока не `OK`. Если `проверка: только структура`, скажи в итоге, что синтаксис PlantUML не проверен.
