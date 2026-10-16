<?php
require 'db.php';
$orders = mysql_query("SELECT * FROM legacy_invoices ORDER BY id DESC");
include 'templates/invoices.tpl.php';
