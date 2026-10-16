<?php

namespace App\Services;

class PartnersClient
{
    public function checkAvailability(string $promocode): array
    {
        return $this->post('/api/promocode/check-availability', ['promo_code' => $promocode]);
    }

    private function post(string $path, array $payload): array
    {
        // HTTP-вызов partners-dashboard с сервисным токеном
        return [];
    }
}
