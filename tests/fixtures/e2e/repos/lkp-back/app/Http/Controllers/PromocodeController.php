<?php

namespace App\Http\Controllers;

use App\Services\PartnersClient;

class PromocodeController
{
    public function check(PartnersClient $partners, array $request): array
    {
        $result = $partners->checkAvailability($request['promo_code']);
        return ['status' => $result['status'] ?? 'not_found'];
    }
}
