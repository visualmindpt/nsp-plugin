<?php
/**
 * NSP Plugin - Health Check Endpoint
 * GET /health
 */

define('NSP_LICENSE_SERVER', true);
require_once __DIR__ . '/config/config.php';

// Force HTTPS in production
if (!DEV_MODE && (!isset($_SERVER['HTTPS']) || $_SERVER['HTTPS'] !== 'on')) {
    header('HTTP/1.1 403 Forbidden');
    die(json_encode(['error' => 'HTTPS required']));
}

// CORS headers
if (ALLOW_CORS) {
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    $allowedOrigins = CORS_ORIGINS;

    if (DEV_MODE && defined('CORS_ORIGINS_DEV')) {
        $allowedOrigins = array_merge($allowedOrigins, CORS_ORIGINS_DEV);
    }

    if (in_array($origin, $allowedOrigins)) {
        header("Access-Control-Allow-Origin: $origin");
        header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type, Authorization');
    }
}

// Handle OPTIONS preflight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Health check response
header('Content-Type: application/json');
http_response_code(200);

echo json_encode([
    'status' => 'ok',
    'service' => 'nsp-license-server',
    'version' => '1.0.0',
    'timestamp' => date('c')
], JSON_PRETTY_PRINT);
