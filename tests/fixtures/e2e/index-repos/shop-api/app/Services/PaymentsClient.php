<?php

namespace App\Services;

class PaymentsClient
{
    public function createInvoice($order)
    {
        return Http::post(config('services.payments.url') . '/invoices.php', ['order' => $order->id]);
    }
}
