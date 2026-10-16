<?php

namespace App\Rules;

use App\Services\PartnersClient;

class PromocodeRule
{
    public function __construct(private PartnersClient $partners) {}

    public function passes(string $attribute, ?string $value): bool
    {
        if ($value === null || $value === '') {
            return true;
        }
        if (!preg_match('/^[A-Za-z0-9_]{1,25}$/', $value)) {
            return false;
        }
        // Проверяется только существование промокода
        return $this->partners->checkAvailability($value)['status'] === 'exists';
    }
}
