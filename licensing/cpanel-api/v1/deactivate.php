<?php
/**
 * NSP Plugin - Deactivate License Endpoint
 * POST /v1/deactivate
 *
 * Deactivates license on current machine
 *
 * Request:
 * {
 *   "token": "jwt_token"
 * }
 *
 * Response:
 * {
 *   "success": true,
 *   "message": "License deactivated successfully"
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
if (!$security->checkRateLimit($ipAddress, 'deactivate')) {
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
        die(json_encode(['error' => 'Invalid or expired token']));
    }

    $activationId = $payload['activation_id'] ?? null;

    if (!$activationId) {
        http_response_code(401);
        die(json_encode(['error' => 'Invalid token payload']));
    }

    // Check activation exists
    $activation = $db->queryOne(
        "SELECT * FROM activations WHERE id = ?",
        [$activationId]
    );

    if (!$activation) {
        http_response_code(404);
        die(json_encode(['error' => 'Activation not found']));
    }

    if ($activation['deactivated_at']) {
        http_response_code(400);
        die(json_encode(['error' => 'Already deactivated']));
    }

    // Deactivate
    $db->execute(
        "UPDATE activations SET deactivated_at = NOW() WHERE id = ?",
        [$activationId]
    );

    // Log success
    $logger->info("License deactivated", [
        'activation_id' => $activationId,
        'machine' => $activation['machine_id']
    ]);

    // Audit log
    $security->auditLog(
        'license_deactivated',
        $activation['license_id'],
        "Machine: {$activation['machine_name']} ({$activation['machine_id']})"
    );

    // Success response
    http_response_code(200);
    echo json_encode([
        'success' => true,
        'message' => 'License deactivated successfully'
    ]);

} catch (Exception $e) {
    $logger->error("Deactivation error: " . $e->getMessage());

    http_response_code(500);
    echo json_encode([
        'error' => DEV_MODE ? $e->getMessage() : 'Internal server error'
    ]);
}
