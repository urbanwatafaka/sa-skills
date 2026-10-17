# Доработки

## **[payform.cabinet.client](https://gibus.prodamus.ru/payform-2.0/payform.cabinet.client)**

Задача: &lt;Не заведена&gt;

### Front

### Экран: Канал продаж — «Данные о канале»

**URL:** `/saleChannels/:id/:tab?`

**Доступен для ролей:** Мерчант

**Что изменить:**

1. Поля «Логотип» и «Оферта» — загрузка одним запросом `POST /api/files` в `payform.payment.saleschannels`. ‹IM-01, D-01›
   1. Во время запроса показывать индикатор загрузки. ‹R-03›
   2. Ответ с ошибкой — уведомление «При загрузке файла произошла ошибка», поле сбросить. ‹D-01›

## **[payform.payment.saleschannels](https://gibus.prodamus.ru/payform-2.0/payform.payment.saleschannels)**

Задача: &lt;Не заведена&gt;

### Back

**1. Описание изменений:**

1. Новый метод `POST /api/files` — загрузка логотипа или оферты канала из ЛК. ‹IM-02, D-01›
   1. Доступ — право `saleschannels:edit`; мерчант — из токена.
   2. Тело — `multipart/form-data`:
      - `file` — файл, обязательное.
   3. Файл пустой или больше 5 МБ — ответ `400`, файл не сохраняется. ‹IM-02, D-01›
   4. Ответ `200`: `documentId`, `fileName`, `size`. ‹R-03›
2. Передача файла в сервис документов — `POST /internal/documents`. ‹IM-03›
   1. Сбой сервиса документов — повторить вызов до 3 раз с паузой 1, 2 и 4 секунды.
      Повтор отправляет файл заново. ‹R-01›

**2. API:**

@openapi api/payform.payment.saleschannels.yaml

**3. БД:**

Изменений схемы БД не требуется. ‹IM-02›
