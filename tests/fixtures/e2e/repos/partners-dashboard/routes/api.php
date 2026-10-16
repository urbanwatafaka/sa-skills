<?php

use App\Http\Controllers\PromocodeController;

Route::middleware('check-intermediate-access-token')->group(function () {
    Route::post('/promocode/check-availability', [PromocodeController::class, 'checkAvailability']);
});
