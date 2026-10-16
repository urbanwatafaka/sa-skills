<?php

namespace App\Jobs;

class SendOrderToCrm implements ShouldQueue
{
    public function handle(KafkaProducer $kafka)
    {
        $kafka->send('orders.created', $this->order->toArray());
    }
}
