<?php
/**
 * NSP Plugin - Activate License Endpoint
 * POST /v1/activate
 *
 * Request:
 * {
 *   "license_key": "NSP-XXXX-XXXX-XXXX-XXXX",
 *   "machine_id": "sha256_hash",
 *   "machine_name": "MacBook Pro",
 *   "machine_os": "macOS",
 *   "machine_os_version": "14.2"
 * }
 *
 * Response:
 * {
 *   "success": true,
 *   "token": "jwt_token",
 *   "plan": "professional",
 *   "expires_at": "2025-11-24T10:00:00Z",
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
if (!$security->checkRateLimit($ipAddress, 'activate')) {
    http_response_code(429);
    die(json_encode(['error' => 'Rate limit exceeded. Try again in 1 hour.']));
}

// Parse JSON body
$input = json_decode(file_get_contents('php://input'), true);

if (!$input) {
    http_response_code(400);
    die(json_encode(['error' => 'Invalid JSON']));
}

// Validate required fields
$licenseKey = $input['license_key'] ?? '';
$machineId = $input['machine_id'] ?? '';
$machineName = $input['machine_name'] ?? 'Unknown';
$machineOs = $input['machine_os'] ?? null;
$machineOsVersion = $input['machine_os_version'] ?? null;

if (empty($licenseKey) || empty($machineId)) {
    http_response_code(400);
    die(json_encode(['error' => 'Missing required fields: license_key, machine_id']));
}

// Validate formats
if (!$security->validateLicenseKey($licenseKey)) {
    http_response_code(400);
    die(json_encode(['error' => 'Invalid license key format']));
}

if (!$security->validateMachineId($machineId)) {
    http_response_code(400);
    die(json_encode(['error' => 'Invalid machine_id format (must be SHA-256 hash)']));
}

try {
    // Find license
    $license = $db->queryOne(
        "SELECT * FROM licenses WHERE license_key = ?",
        [$licenseKey]
    );

    if (!$license) {
        $logger->warning("Activation failed: License not found", ['key' => $licenseKey]);
        http_response_code(404);
        die(json_encode(['error' => 'License key not found']));
    }

    // Check license status
    if ($license['status'] === 'revoked') {
        $logger->warning("Activation failed: License revoked", ['key' => $licenseKey]);
        http_response_code(403);
        die(json_encode([
            'error' => 'License has been revoked',
            'reason' => $license['revoke_reason'] ?? 'No reason provided'
        ]));
    }

    if ($license['status'] === 'expired') {
        http_response_code(403);
        die(json_encode(['error' => 'License has expired']));
    }

    // Check expiration date
    if ($license['expires_at'] && strtotime($license['expires_at']) < time()) {
        // Mark as expired
        $db->execute("UPDATE licenses SET status = 'expired' WHERE id = ?", [$license['id']]);

        $logger->info("License expired", ['key' => $licenseKey]);
        http_response_code(403);
        die(json_encode(['error' => 'License has expired']));
    }

    // Check if machine already activated
    $existingActivation = $db->queryOne(
        "SELECT * FROM activations
         WHERE license_id = ? AND machine_id = ? AND deactivated_at IS NULL",
        [$license['id'], $machineId]
    );

    if ($existingActivation) {
        // Already activated - return new token
        $tokenPayload = [
            'activation_id' => $existingActivation['id'],
            'license_id' => $license['id'],
            'machine_id' => $machineId,
            'plan' => $license['plan'],
        ];

        $token = JWT::encode($tokenPayload);

        $logger->info("Re-activated existing machine", [
            'license' => $licenseKey,
            'machine' => $machineId
        ]);

        http_response_code(200);
        echo json_encode([
            'success' => true,
            'token' => $token,
            'plan' => $license['plan'],
            'expires_at' => $license['expires_at'],
            'features' => PLANS[$license['plan']]['features'],
        ]);
        exit;
    }

    // Check activation limit
    $activeCount = $db->queryOne(
        "SELECT COUNT(*) as count FROM activations
         WHERE license_id = ? AND deactivated_at IS NULL",
        [$license['id']]
    );

    if ($activeCount['count'] >= $license['max_activations']) {
        $logger->warning("Activation failed: Max activations reached", [
            'license' => $licenseKey,
            'max' => $license['max_activations']
        ]);

        http_response_code(403);
        die(json_encode([
            'error' => "Maximum activations ({$license['max_activations']}) reached",
            'message' => 'Please deactivate another machine first or upgrade your plan.'
        ]));
    }

    // Fraud detection
    $fraudCheck = $security->detectFraud($license['id'], $ipAddress);
    if ($fraudCheck['is_fraud']) {
        $logger->error("FRAUD DETECTED during activation", [
            'license' => $licenseKey,
            'ip' => $ipAddress,
            'reasons' => $fraudCheck['reasons']
        ]);

        // Don't block completely, but flag for review
        // In production, you might want to block or require manual approval
    }

    // Create new activation
    $activationId = Database::generateUuid();
    $pluginVersion = $input['plugin_version'] ?? null;

    $db->execute(
        "INSERT INTO activations (
            id, license_id, machine_id, machine_name, machine_os,
            machine_os_version, ip_address, plugin_version, activated_at, last_heartbeat
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())",
        [
            $activationId,
            $license['id'],
            $machineId,
            $machineName,
            $machineOs,
            $machineOsVersion,
            $ipAddress,
            $pluginVersion
        ]
    );

    // Create access token
    $tokenPayload = [
        'activation_id' => $activationId,
        'license_id' => $license['id'],
        'machine_id' => $machineId,
        'plan' => $license['plan'],
    ];

    $token = JWT::encode($tokenPayload);

    // Log success
    $logger->info("License activated successfully", [
        'license' => $licenseKey,
        'machine' => $machineId,
        'plan' => $license['plan']
    ]);

    // Audit log
    $security->auditLog(
        'license_activated',
        $license['id'],
        "Machine: $machineName ($machineId)"
    );

    // Success response
    http_response_code(200);
    echo json_encode([
        'success' => true,
        'token' => $token,
        'plan' => $license['plan'],
        'expires_at' => $license['expires_at'],
        'features' => PLANS[$license['plan']]['features'],
    ]);

} catch (Exception $e) {
    $logger->error("Activation error: " . $e->getMessage());

    http_response_code(500);
    echo json_encode([
        'error' => DEV_MODE ? $e->getMessage() : 'Internal server error'
    ]);
}
