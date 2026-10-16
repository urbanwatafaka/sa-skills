---
index_used: true
confidence_cap: высокая
---
# Карта влияния

| ID    | Объект                                      | Вид    | Влияние | ← R        | Источник                                  | Статус    | Уверенность |
|-------|---------------------------------------------|--------|---------|------------|-------------------------------------------|-----------|-------------|
| IM-01 | partners-dashboard: promocode/check-usage   | API    | новый   | R-01       | BRD R-01                                  | факт      | высокая     |
| IM-02 | lkp-back: правило валидации промокода       | модуль | изм.    | R-01, R-03 | code: lkp-back/app/Rules/Promocode.php:40 | факт      | высокая     |
| IM-03 | lkp-front: поле «Промокод партнёра»         | UI     | изм.    | R-02       | docs: lkp-front/docs/tech.md#promocode    | факт      | средняя     |
| IM-04 | Kafka: questionnaire.saved                  | Kafka  | ?       | R-03       | —                                         | допущение | низкая      |
