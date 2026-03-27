<?php
/**
 * NSP Plugin - Validate License Token Endpoint
 * POST /v1/validate
 *
 * Request:
 * {
 *   "token": "jwt_token"
 * }
 *
 * Response:
 * {
 *   "valid": true,
 *   "plan": "professional",
 *   "expires_at": "2025-11-24T10:00:00Z",
 *   "days_remaining": 365,
 *   "features": {...}
 * }
 */

define('NSP_LICENSE_SERVER', true);
require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../lib/Database.php';
require_once __DIR__ . '/../lib/Logger.php';
require_once __DIR__ . '/../lib/JWT.php';
require_once __DIR__ . '/../lib/Security.php';

// Initialize
$db = Database::getInstance();
$logger = Logger::getInstance();
$security = new Security();

// Force HTTPS in production
if (!DEV_MODE && (!isset($_SERVER['HTTPS']) || $_SERVER['HTTPS'] !== 'on')) {
    http_response_code(403);
    die(json_encode(['error' => 'HTTPS required']));
}

// Only POST allowed
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die(json_encode(['error' => 'Method not allowed']));
}

// Get client IP
$ipAddress = $security->getClientIp();

// Rate limiting
if (!$security->checkRateLimit($ipAddress, 'validate')) {
    http_response_code(429);
    die(json_encode(['error' => 'Rate limit exceeded']));
}

// Parse JSON body
$input = json_decode(file_get_contents('php://input'), true);

if (!$input || empty($input['token'])) {
    http_response_code(400);
    die(json_encode(['error' => 'Missing token']));
}

$token = $input['token'];

try {
    // Decode token
    try {
        $payload = JWT::decode($token);
    } catch (Exception $e) {
        http_response_code(401);
        die(json_encode([
            'valid' => false,
            'error' => 'Invalid or expired token'
        ]));
    }

    $activationId = $payload['activation_id'] ?? null;
    $licenseId = $payload['license_id'] ?? null;

    if (!$activationId || !$licenseId) {
        http_response_code(401);
        die(json_encode([
            'valid' => false,
            'error' => 'Invalid token payload'
        ]));
    }

    // Check activation exists and is active
    $activation = $db->queryOne(
        "SELECT * FROM activations WHERE id = ?",
        [$activationId]
    );

    if (!$activation || $activation['deactivated_at']) {
        http_response_code(401);
        die(json_encode([
            'valid' => false,
            'error' => 'Activation not found or deactivated'
        ]));
    }

    // Check license exists and is active
    $license = $db->queryOne(
        "SELECT * FROM licenses WHERE id = ?",
        [$licenseId]
    );

    if (!$license) {
        http_response_code(401);
        die(json_encode([
            'valid' => false,
            'error' => 'License not found'
        ]));
    }

    if ($license['status'] !== 'active') {
        http_response_code(403);
        die(json_encode([
            'valid' => false,
            'error' => "License is {$license['status']}"
        ]));
    }

    // Check expiration
    $daysRemaining = null;
    if ($license['expires_at']) {
        $expiresTimestamp = strtotime($license['expires_at']);

        if ($expiresTimestamp < time()) {
            // Mark as expired
            $db->execute("UPDATE licenses SET status = 'expired' WHERE id = ?", [$licenseId]);

            http_response_code(403);
            die(json_encode([
                'valid' => false,
                'error' => 'License has expired'
            ]));
        }

        $daysRemaining = floor(($expiresTimestamp - time()) / 86400);
    }

    // Success response
    http_response_code(200);
    echo json_encode([
        'valid' => true,
        'plan' => $license['plan'],
        'expires_at' => $license['expires_at'],
        'days_remaining' => $daysRemaining,
        'features' => PLANS[$license['plan']]['features'],
    ]);

} catch (Exception $e) {
    $logger->error("Validation error: " . $e->getMessage());

    http_response_code(500);
    echo json_encode([
        'valid' => false,
        'error' => DEV_MODE ? $e->getMessage() : 'Internal server error'
    ]);
}
