# lkp-back

## API

| Метод | Назначение | Код |
|---|---|---|
| POST /api/questionnaire/promocode/check | Живая проверка промокода по расфокусу поля | app/Http/Controllers/PromocodeController.php |

## Правила валидации

- Поле client_promocode: правило PromocodeRule (app/Rules/PromocodeRule.php) — формат и существование через partners-dashboard.

## Kafka

| Топик | Направление | Когда |
|---|---|---|
| questionnaire.saved | публикует | после сохранения анкеты |
