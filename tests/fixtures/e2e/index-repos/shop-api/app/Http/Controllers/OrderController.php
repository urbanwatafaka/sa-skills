<?php

namespace App\Http\Controllers;

use App\Jobs\SendOrderToCrm;
use App\Services\PaymentsClient;

class OrderController
{
    public function store(PaymentsClient $payments)
    {
        $order = Order::create(request()->all());
        $payments->createInvoice($order);
        SendOrderToCrm::dispatch($order);
        return $order;
    }

    public function show(int $id)
    {
        return Order::findOrFail($id);
    }
}
