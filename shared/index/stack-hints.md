# Где искать: подсказки по стекам

Стек и папки-подсказки печатает `sa_index.py survey`. Начинай с подсказок, ищи Grep с `-n`, читай фрагментами.

## Общее

- Конфиги окружения (`.env.example`, `appsettings*.json`, `config/*.php`, `docker-compose*.yml`) — адреса других сервисов и брокеров: по ним понятно, куда идут исходящие вызовы (`Куда`).
- Брокеры: grep `kafka`, `rdkafka`, `KafkaProducer`, `subscribe`, `RabbitMQ`, `amqp`, `basic_publish`, `basic_consume`, `Confluent.Kafka`, `MassTransit`.
- HTTP-клиенты: grep `Http::`, `Guzzle`, `curl_init`, `file_get_contents('http`, `HttpClient`, `fetch(`, `axios`.
- Расписание: `crontab`, `cron`, `schedule(`, `Schedule::`, `IHostedService`, `BackgroundService`, `Hangfire`, `Quartz`.

## .NET

- API: атрибуты `[Http(Get|Post|Put|Delete)]`, `[Route]` в `Controllers/`; minimal API — `app.Map(Get|Post)` в `Program.cs`.
- БД: `DbContext` и `DbSet<>`, папка `Migrations/` (`migrationBuilder.CreateTable`), `[Table]`; Dapper — SQL-строки.
- Фон: `BackgroundService`, `IHostedService`, Hangfire/Quartz-джобы; консьюмеры MassTransit/Confluent.

## Laravel

- API: `routes/api.php`, `routes/web.php`; контроллеры `app/Http/Controllers`.
- БД: `database/migrations` (`Schema::create`, `Schema::table`), модели `app/Models` (`$table`, связи `belongsTo`/`hasMany` → раздел `Связи`).
- Фон: `app/Jobs` (`ShouldQueue`), `app/Console/Kernel.php` (`schedule`), `app/Listeners`, консьюмеры в `app/Console/Commands`.
- Фронт внутри проекта: `resources/js` (Vue/React), `resources/views` (Blade) — экраны и вызовы API для `bctc.md` и `Исходящих вызовов`.

## PHP без фреймворка

- Точки входа — PHP-файлы в корне и папках, открываемые по URL: путь = путь файла (`/invoices.php`); метод — по суперглобальным `_POST`/`_GET`. Ищи `.htaccess` с `RewriteRule` — он меняет пути.
- БД: `mysql_query`, `mysqli_`, `PDO`, `->query(` — таблицы по SQL (`FROM`, `INTO`, `UPDATE`); `Код` — строка SQL.
- Шаблоны (`templates/`, `*.tpl`, `*.phtml`, Smarty) — экраны для `bctc.md`, но не API.
- Фон — скрипты в `cron/`, `scripts/`, строки crontab в комментариях или в `crontab`-файлах.

## React и другие фронты

- Своих API и БД нет: `API`, `Таблицы`, `Связи` — строка `нет`.
- `Исходящие вызовы` — `fetch`, `axios`, клиенты в `src/api`, `services/`: `Куда` — бэкенд по базовому URL из конфига; если бэкенд неясен — `? <имя из конфига>`.
- `bctc.md` — экраны и роуты (`react-router`, `pages/`, `routes`): сценарий, роль экрана, точка входа — путь экрана.
