# partners-dashboard

## API

| Метод | Назначение | Код |
|---|---|---|
| POST /api/promocode/check-availability | Существует ли промокод | routes/api.php, app/Http/Controllers/PromocodeController.php |

## БД

| Таблица | Поля |
|---|---|
| partners | id, inn, owner_email, phone, id_in_platform, uuid_in_platform |
| partner_promocodes | promocode, partner_id |
