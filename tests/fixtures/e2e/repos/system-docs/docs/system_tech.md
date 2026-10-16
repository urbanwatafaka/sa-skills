# API и Kafka

| Поставщик | Метод или топик | Потребители | Назначение |
|---|---|---|---|
| partners-dashboard | POST /api/promocode/check-availability | lkp-back | Проверка существования промокода |
| lkp-back | POST /api/questionnaire/promocode/check | lkp-front | Живая проверка промокода в анкете |
| lkp-back | Kafka: questionnaire.saved | lk-payform | Анкета сохранена |
