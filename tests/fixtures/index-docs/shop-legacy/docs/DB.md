# shop-legacy

## Таблицы

| Таблица | Назначение | Ключевые поля | Код |
|---|---|---|---|
| legacy_invoices | Счета | order_id, status | invoices.php:4, cron/consume_orders.php:7 |

## Связи

| Из | В | Тип | Код |
|---|---|---|---|
| legacy_invoices.order_id | ? orders.id (shop-api) | ? логическая, без FK | invoices.php:4 |
