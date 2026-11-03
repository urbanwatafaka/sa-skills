---
name: puml-c2
description: C2-диаграмма (контейнеры) на C4-PlantUML для ТЗ — сервисы ПФ2 контейнерами Container/ContainerDb в рамке System_Boundary «Prodamus PF2», внешние системы System_Ext, новые и изменённые — тегами с легендой, ortho-связи Rel_D/U/L/R с нумерацией 1) 2) по ходу процесса, Kafka — пунктир от продюсера к консьюмеру без узла Kafka. Используй для «C2 — Архитектура» в /tdd-draft или когда просят C2/C4-диаграмму.
allowed-tools: Bash(python3:*)
---

# puml-c2

`<база>` — базовая директория этого скила, `<плагин>` = `<база>/../..`. Перед работой прочитай `<плагин>/shared/blocks/diagrams.md`.

## Когда применять

- Нужно показать, какие системы и БД участвуют в доработке и как связаны. Одна C2 на документ, открыто, не под «Раскрыть».

Не применять: порядок вызовов — `puml-sequence`; структура таблиц — `puml-er`.

## Каркас

```plantuml
@startuml
!$TECHN_FONT_SIZE = 11
!includeurl https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml
skinparam linetype ortho
skinparam nodesep 320
skinparam ranksep 220
skinparam padding 20
skinparam defaultFontSize 11
skinparam ArrowFontSize 11
skinparam rectangle {
  FontSize 11
  StereotypeFontSize 11
}
skinparam person {
  FontSize 11
  StereotypeFontSize 11
}
skinparam ArrowColor #333333
skinparam ArrowThickness 3
AddRelTag("kafka", $lineStyle = DashedLine(), $legendText = "Kafka: продюсер → консьюмер")
AddElementTag("new", $bgColor = "#D5F5E3", $fontColor = "#000000", $borderColor = "#0B8043", $legendText = "новый сервис")
AddElementTag("changed", $borderColor = "#0B8043", $legendText = "сервис с доработками")
LAYOUT_TOP_DOWN()

Person(merchant, "Мерчант")
System_Ext(dadata, "DaData", "Проверка ИНН")

System_Boundary(pf2, "Prodamus PF2") {
  Container(front, "lkp-front", "Vue", "ЛК мерчанта", $tags = "changed")
  Container(back, "lkp-back", ".NET", "Бэкенд ЛК", $tags = "changed")
  ContainerDb(db, "БД lkp", "PostgreSQL", "Анкеты")
  Container(pd, "partners-dashboard", ".NET", "Промокоды партнёров", $tags = "new")
  Container(notify, "notification-service", ".NET", "Уведомления")
}

Rel_D(merchant, front, "1) Сохраняет анкету")
Rel_D(front, back, "2) POST /api/questionnaires")
Rel_R(back, pd, "3) GET /internal/promocodes/{code}/owner")
Rel_D(back, notify, "4) Kafka: lkp.questionnaire —\nQuestionnaireSavedEvent", $tags="kafka")
Rel_R(back, pd, "4) Kafka: lkp.questionnaire —\nQuestionnaireSavedEvent", $tags="kafka")
Rel_R(back, db, "5) Сохранить анкету")
Rel_L(back, dadata, "6) Проверка ИНН")

SHOW_LEGEND()
@enduml
```

## Соглашения

- `!includeurl` — всегда полный `https://` URL, не `<C4/...>` и не локальный путь.
- `skinparam linetype ortho`, связи только `Rel_D`/`Rel_U`/`Rel_L`/`Rel_R`, без пересечений.
- Один размер шрифта на всей схеме — 11: `!$TECHN_FONT_SIZE = 11` до `!includeurl`, затем `defaultFontSize`, `ArrowFontSize` и `FontSize`/`StereotypeFontSize` у `rectangle` и `person` — по 11, как в каркасе. Подписи стрелок крупнее текста блоков налезают на блоки.
- Отступы `nodesep 320`, `ranksep 220`: при прямоугольных линиях подпись стоит посередине стрелки, и на короткой стрелке между близкими блоками её перекрывает блок. `ArrowThickness 3`, `LAYOUT_TOP_DOWN()`.
- Длинную подпись переноси `\n`: у Kafka топик на первой строке, событие на второй — `"N) Kafka: <топик> —\n<Событие>"`; у HTTP с двумя методами второй метод — с новой строки.
- Подписи всё равно налезают на блоки — на стрелке оставь номер и короткую суть, детали вынеси в таблицу под схемой.
- Компоновка сверху вниз: инициатор наверху, системы и БД ниже по уровням вызовов; по возможности ближе к квадрату. Перед связями выпиши граф смежности: связанные элементы — соседи, элемент с многими связями (общая БД) — с края цепочки, связи разводи в разные стороны.
- Каждая связь начинается с номера `1)`, `2)` … в порядке старта процесса.
- Нотация C4 Container: сервисы ПФ2 — `Container(id, "имя сервиса", "стек", "назначение")` внутри одной рамки `System_Boundary(pf2, "Prodamus PF2") { … }`; хранилища (БД, Redis) — `ContainerDb`; внешние системы (провайдер, банк, ПФ1) и роли — вне рамки, `System_Ext` и `Person`. Внутренние сервисы блоком `System()` не рисуй: это уровень C1, на C2 он читается непривычно.
- Хранилище рисуй, только если доработка меняет его данные: новая таблица, новые поля, новая запись в кэш.
- Узла Kafka на C2 нет: центральный блок, через который идут все стрелки, делает схему нечитаемой. Взаимодействие через Kafka — пунктирная стрелка прямо от продюсера к консьюмеру: `AddRelTag("kafka", $lineStyle = DashedLine())` и `Rel_X(producer, consumer, "N) Kafka: <топик> — <Событие>", $tags="kafka")`. HTTP-вызовы — сплошные, без тега.
- Топик — как в коде или конфиге и в «Топиках Кафка»; не согласован — `ХХХХХ` и `⚠ Q-SA-xx`.
- Событие читают несколько сервисов — по стрелке от продюсера к каждому консьюмеру с одним номером. Несколько событий от одного продюсера одному консьюмеру — одной стрелкой: события одного топика через запятую, разные топики — пары `топик — Событие` через «;».
- На sequence-диаграммах правило прежнее — стрелки к участнику Kafka, см. `puml-sequence`.
- Новый сервис — `$tags = "new"`, сервис с доработками — `$tags = "changed"`; теги заданы `AddElementTag`, как в каркасе, в конце схемы — `SHOW_LEGEND()`. Существующие сервисы без доработок — без тега.
- Элементы — только системы из карты влияния в скоупе и роли BRD.

## Чек-лист

- [ ] Каждый элемент есть в карте влияния или ролях BRD.
- [ ] Сервисы ПФ2 — `Container`/`ContainerDb` в рамке `System_Boundary(pf2, "Prodamus PF2")`, внешние — `System_Ext` вне рамки; новые и изменённые — с тегом, есть `SHOW_LEGEND()`.
- [ ] У каждой связи есть номер `N)`, связи только `Rel_D/U/L/R`.
- [ ] Узла Kafka нет; каждая связь через Kafka — пунктир `$tags="kafka"` от продюсера к консьюмеру с подписью `N) Kafka: <топик> — <Событие>`, HTTP — сплошные.
- [ ] Событие с несколькими консьюмерами — по стрелке на каждого с одним номером.
- [ ] `!includeurl` с полным `https://` URL.
- [ ] Шрифт 11 везде (`!$TECHN_FONT_SIZE = 11` до `!includeurl`), `nodesep 320`, `ranksep 220`; длинные подписи перенесены, ни одна не налезает на блок.

## Проверка

`python3 <плагин>/scripts/sa_puml.py check <путь к .puml>` — исправляй, пока не `OK`. Если `проверка: только структура`, скажи в итоге, что синтаксис PlantUML не проверен.
