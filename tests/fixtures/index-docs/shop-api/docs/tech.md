# shop-api

## API

| Метод | Путь | Назначение | Код |
|---|---|---|---|
| POST | /api/orders | Создание заказа | routes/api.php:6, app/Http/Controllers/OrderController.php:10 |
| GET | /api/orders/{id} | Заказ по id | routes/api.php:7, app/Http/Controllers/OrderController.php:18 |

## Исходящие вызовы

| Куда | Метод или топик | Назначение | Код |
|---|---|---|---|
| shop-legacy | POST /invoices.php | Создание счёта по заказу | app/Services/PaymentsClient.php:9 |

## Сообщения

| Брокер | Топик или очередь | Направление | Когда | Код |
|---|---|---|---|---|
| Kafka | orders.created | публикует | после создания заказа | app/Jobs/SendOrderToCrm.php:9 |

## Фоновые задачи

| Задача | Запуск | Что делает | Код |
|---|---|---|---|
| SendOrderToCrm | очередь | Публикует событие о новом заказе | app/Jobs/SendOrderToCrm.php:5 |
