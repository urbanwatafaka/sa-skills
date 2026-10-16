<?php

use App\Http\Controllers\OrderController;
use Illuminate\Support\Facades\Route;

Route::post('/api/orders', [OrderController::class, 'store']);
Route::get('/api/orders/{id}', [OrderController::class, 'show']);
