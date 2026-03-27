<?php
/**
 * NSP Plugin - Create License Endpoint (Admin Only)
 * POST /v1/create
 *
 * Creates new license. Requires admin authentication.
 *
 * Request Headers:
 *   X-Admin-Key: admin_api_key
 *
 * Request Body:
 * {
 *   "email": "customer@example.com",
 *   "plan": "professional",
 *   "max_activations": 3,
 *   "duration_days": 365
 * }
 *
 * Response:
 * {
 *   "success": true,
 *   "license_key": "NSP-XXXX-XXXX-XXXX-XXXX",
 *   "email": "customer@example.com",
 *   "plan": "professional",
 *   "expires_at": "2025-11-24T10:00:00Z"
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

// Check admin authentication
$adminKey = $_SERVER['HTTP_X_ADMIN_KEY'] ?? '';

if (!$security->validateAdminKey($adminKey)) {
    $logger->warning("Unauthorized admin access attempt", [
        'ip' => $security->getClientIp()
    ]);

    http_response_code(403);
    die(json_encode(['error' => 'Unauthorized. Admin key required.']));
}

// Parse JSON body
$input = json_decode(file_get_contents('php://input'), true);

if (!$input) {
    http_response_code(400);
    die(json_encode(['error' => 'Invalid JSON']));
}

// Validate required fields
$email = $input['email'] ?? '';
$plan = $input['plan'] ?? 'personal';
$maxActivations = $input['max_activations'] ?? null;
$durationDays = $input['duration_days'] ?? null;

if (empty($email)) {
    http_response_code(400);
    die(json_encode(['error' => 'Missing required field: email']));
}

if (!$security->validateEmail($email)) {
    http_response_code(400);
    die(json_encode(['error' => 'Invalid email format']));
}

// Validate plan
$validPlans = ['trial', 'personal', 'professional', 'studio'];
if (!in_array($plan, $validPlans)) {
    http_response_code(400);
    die(json_encode([
        'error' => 'Invalid plan',
        'valid_plans' => $validPlans
    ]));
}

// Get max_activations from plan if not specified
if ($maxActivations === null) {
    $maxActivations = PLANS[$plan]['max_activations'];
}

// Validate max_activations
if ($maxActivations < 1 || $maxActivations > 100) {
    http_response_code(400);
    die(json_encode(['error' => 'max_activations must be between 1 and 100']));
}

try {
    // Generate unique license key
    $licenseKey = JWT::generateLicenseKey();

    // Check if key already exists (very unlikely)
    $existing = $db->queryOne(
        "SELECT id FROM licenses WHERE license_key = ?",
        [$licenseKey]
    );

    // If exists, generate new one
    while ($existing) {
        $licenseKey = JWT::generateLicenseKey();
        $existing = $db->queryOne(
            "SELECT id FROM licenses WHERE license_key = ?",
            [$licenseKey]
        );
    }

    // Calculate expiration
    $expiresAt = null;
    if ($durationDays !== null) {
        if ($durationDays < 1 || $durationDays > 3650) { // Max 10 years
            http_response_code(400);
            die(json_encode(['error' => 'duration_days must be between 1 and 3650']));
        }

        $expiresAt = date('Y-m-d H:i:s', time() + ($durationDays * 86400));
    }

    // Create license
    $licenseId = Database::generateUuid();

    $db->execute(
        "INSERT INTO licenses (
            id, license_key, email, plan, status,
            max_activations, created_at, expires_at
        ) VALUES (?, ?, ?, ?, 'active', ?, NOW(), ?)",
        [
            $licenseId,
            $licenseKey,
            $email,
            $plan,
            $maxActivations,
            $expiresAt
        ]
    );

    // Log success
    $logger->info("License created", [
        'license' => $licenseKey,
        'email' => $email,
        'plan' => $plan,
        'max_activations' => $maxActivations
    ]);

    // Audit log
    $security->auditLog(
        'license_created',
        $licenseId,
        "Email: $email, Plan: $plan, Max Activations: $maxActivations"
    );

    // Success response
    http_response_code(201);
    echo json_encode([
        'success' => true,
        'license_key' => $licenseKey,
        'email' => $email,
        'plan' => $plan,
        'max_activations' => $maxActivations,
        'expires_at' => $expiresAt,
        'features' => PLANS[$plan]['features'],
    ]);

} catch (Exception $e) {
    $logger->error("Create license error: " . $e->getMessage());

    http_response_code(500);
    echo json_encode([
        'error' => DEV_MODE ? $e->getMessage() : 'Internal server error'
    ]);
}
