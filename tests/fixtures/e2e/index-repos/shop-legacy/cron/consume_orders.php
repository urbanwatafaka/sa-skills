<?php
// cron: */5 * * * * php cron/consume_orders.php
require dirname(__FILE__) . '/../db.php';
$consumer = new RdKafka\KafkaConsumer($conf);
$consumer->subscribe(array('orders.created'));
while ($message = $consumer->consume(1000)) {
    mysql_query("UPDATE legacy_invoices SET status = 'new' WHERE order_id = " . (int) $message->payload);
}
