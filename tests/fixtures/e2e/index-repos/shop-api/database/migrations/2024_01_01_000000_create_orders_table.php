<?php

return new class extends Migration
{
    public function up()
    {
        Schema::create('orders', function (Blueprint $table) {
            $table->id();
            $table->string('email');
            $table->integer('amount');
            $table->timestamps();
        });
    }
};
