<?php

namespace App\Http\Controllers;

class PromocodeController
{
    public function checkAvailability(array $request): array
    {
        $code = strtoupper(trim($request['promocode'] ?? $request['promo_code'] ?? ''));
        $exists = \DB::table('partner_promocodes')->where('promocode', $code)->exists();
        return ['status' => $exists ? 'exists' : 'not_found'];
    }
}
