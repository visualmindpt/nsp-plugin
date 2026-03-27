<?php
/**
 * Stripe Checkout Integration for NSP Plugin
 *
 * Place this file in your cPanel public_html directory.
 *
 * Installation:
 * 1. Install Stripe PHP SDK: composer require stripe/stripe-php
 * 2. Set STRIPE_SECRET_KEY in .env or hosting environment
 * 3. Create pricing page with links: checkout.php?plan=professional&email=user@example.com
 */

require_once __DIR__ . '/vendor/autoload.php';

// Load Stripe SDK
\Stripe\Stripe::setApiKey(getenv('STRIPE_SECRET_KEY'));

// Get plan and email from URL parameters
$plan = $_GET['plan'] ?? 'personal';
$customer_email = $_GET['email'] ?? null;

// Pricing configuration
$prices = [
    'personal' => [
        'amount' => 7900,  // €79.00 in cents
        'name' => 'Personal',
        'description' => 'Perfect for individual photographers',
        'activations' => 2
    ],
    'professional' => [
        'amount' => 14900,  // €149.00
        'name' => 'Professional',
        'description' => 'For professional photographers and studios',
        'activations' => 3
    ],
    'studio' => [
        'amount' => 49900,  // €499.00
        'name' => 'Studio',
        'description' => 'Unlimited activations for teams',
        'activations' => 10
    ],
];

// Validate plan
if (!isset($prices[$plan])) {
    http_response_code(400);
    die('Invalid plan. Choose: personal, professional, or studio');
}

$price_info = $prices[$plan];

try {
    // Create Stripe Checkout Session
    $session = \Stripe\Checkout\Session::create([
        'payment_method_types' => ['card'],
        'line_items' => [[
            'price_data' => [
                'currency' => 'eur',
                'product_data' => [
                    'name' => "NSP Plugin - {$price_info['name']} License",
                    'description' => "{$price_info['description']}. Activate on {$price_info['activations']} computers. Perpetual license.",
                    'images' => ['https://vilearn.ai/images/nsp-plugin-logo.png'],  // Optional
                ],
                'unit_amount' => $price_info['amount'],
            ],
            'quantity' => 1,
        ]],
        'mode' => 'payment',
        'success_url' => 'https://vilearn.ai/success?session_id={CHECKOUT_SESSION_ID}',
        'cancel_url' => 'https://vilearn.ai/pricing',
        'customer_email' => $customer_email,
        'metadata' => [
            'plan' => $plan,
        ],
        'billing_address_collection' => 'required',  // For VAT compliance
    ]);

    // Redirect to Stripe Checkout
    header("HTTP/1.1 303 See Other");
    header("Location: " . $session->url);
    exit;

} catch (\Stripe\Exception\ApiErrorException $e) {
    // Handle Stripe errors
    http_response_code(500);
    error_log("Stripe error: " . $e->getMessage());
    die('Payment error. Please contact support.');
}
