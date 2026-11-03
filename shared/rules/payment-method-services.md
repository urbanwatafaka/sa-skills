# Сервисы-кандидаты интеграции платёжного метода (ПФ2)

Справка для `/tdd-impact`, когда BRD — подключение нового платёжного метода или провайдера. Это список, что проверить, а не готовая карта: каждый сервис идёт в `source-reader` вместе с требованиями, в карту попадает только подтверждённое кодом или BRD. Сервис без затронутых требований отбрасывается.

| Сервис | Что обычно затрагивает |
|---|---|
| `payform.payment.paymentmethods` | Провайдер, метод, локализация, группы отображения, `AdditionalSettings`, выдача методов канала |
| Новый адаптер провайдера (`payment.apm.adapter.<провайдер>`, `payment.card.adapter.<провайдер>`, `payment.installment.adapter.<провайдер>`) | Создание платежа, статус, callback, возврат |
| Общий адаптер (`payform.payment.apm.adapter`, `payform.payment.card.adapter`, `payform.payment.installment.adapter`) | `…Implementations:<код>:BaseUrl`, контракт заявки, категории ошибок |
| `payment.apm.callbackhandler`, `card.callbackhandler`, `installment.callbackhandler`, `Payform.Payment.CallbackHandler.Proxy` | Источник callback (`SourceCodes`), публичный URL |
| `payform.payments.transactions` | Сага оплаты и возврата, курс и маркап, данные плательщика |
| `payform.payment.apigateway` | Публичные методы оплаты, валидация данных плательщика |
| `payform.payment.orders` | Возвраты, в том числе ручные |
| `payform.payment.markups`, `payform.payment.currency` | Конвертация и маркап, если валюта оплаты не валюта заказа |
| `payform.payment.page`, `payform.payment.domainpage`, `payform.payment.widget` | Кнопка метода, форма плательщика, лимиты, переводы |
| `payform.backoffice.client`, `payform.cabinet.client` | Включение метода на канале, раздел группы, возвраты |
| `payform.payment.receipt` | Чеки, если метод их пробивает |
| `Platform.Pf2xPf1.Adapter` | Маппинг метода и выгрузка в ПФ1 |
| `Platform.Partner.Adapter` | Передача метода при создании мерчанта из анкеты (`UserFlowPaymentMethod`) |
| `report` | Отчёты по комиссиям |
