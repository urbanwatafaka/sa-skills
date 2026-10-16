<?php
require 'db.php';
$orderId = (int) $_POST['order'];
mysql_query("INSERT INTO legacy_invoices (order_id) VALUES ($orderId)");
echo json_encode(array('ok' => true));
