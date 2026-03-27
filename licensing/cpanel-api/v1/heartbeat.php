<?php
/**
 * NSP Plugin - Heartbeat Endpoint
 * POST /v1/heartbeat
 *
 * Records activity and refreshes token
 *
 * Request:
 * {
 *   "token": "jwt_token",
 *   "plugin_version": "2.0.0",
 *   "photos_processed": 150,
 *   "uptime_hours": 3.5
 * }
 *
 * Response:
 * {
 *   "success": true,
 *   "token": "new_jwt_token"
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

// Rate limiting (more lenient for heartbeats)
if (!$security->checkRateLimit($ipAddress, 'heartbeat')) {
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
$pluginVersion = $input['plugin_version'] ?? null;
$photosProcessed = $input['photos_processed'] ?? 0;
$uptimeHours = $input['uptime_hours'] ?? null;

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
        http_response_code(401);
        die(json_encode(['error' => 'Activation has been deactivated']));
    }

    // Update last heartbeat timestamp
    $db->execute(
        "UPDATE activations SET last_heartbeat = NOW() WHERE id = ?",
        [$activationId]
    );

    // Record heartbeat
    $heartbeatId = Database::generateUuid();
    $db->execute(
        "INSERT INTO heartbeats (
            id, activation_id, timestamp, plugin_version,
            photos_processed, uptime_hours, ip_address
        ) VALUES (?, ?, NOW(), ?, ?, ?, ?)",
        [
            $heartbeatId,
            $activationId,
            $pluginVersion,
            $photosProcessed,
            $uptimeHours,
            $ipAddress
        ]
    );

    // Generate new token (refresh)
    $newToken = JWT::encode([
        'activation_id' => $activation['id'],
        'license_id' => $activation['license_id'],
        'machine_id' => $activation['machine_id'],
        'plan' => $payload['plan'] ?? 'trial',
    ]);

    // Success response
    http_response_code(200);
    echo json_encode([
        'success' => true,
        'token' => $newToken
    ]);

} catch (Exception $e) {
    $logger->error("Heartbeat error: " . $e->getMessage());

    http_response_code(500);
    echo json_encode([
        'error' => DEV_MODE ? $e->getMessage() : 'Internal server error'
    ]);
}
