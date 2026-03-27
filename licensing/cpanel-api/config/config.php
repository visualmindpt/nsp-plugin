<?php
/**
 * NSP Plugin - License Server Configuration
 * Production-ready configuration for cPanel
 *
 * SECURITY: Este ficheiro contém informação sensível
 * Mover para fora de public_html e configurar .htaccess
 */

// Prevent direct access
defined('NSP_LICENSE_SERVER') or die('Access denied');

// Database Configuration
// Criar database via cPanel: nsp_licensing
// Criar user via cPanel com all privileges
define('DB_HOST', 'localhost');
define('DB_NAME', 'nelsonsi_nsp_licenses');  // Ajustar para teu cPanel prefix
define('DB_USER', 'nelsonsi_nsp_user');      // Ajustar
define('DB_PASS', 'CHANGE_ME_STRONG_PASSWORD_HERE_123!@#');  // MUDAR!
define('DB_CHARSET', 'utf8mb4');

// JWT Secret Key (CRITICAL - MUDAR!)
// Gerar: openssl rand -base64 64
define('JWT_SECRET_KEY', 'CHANGE_ME_SUPER_SECRET_JWT_KEY_BASE64_ENCODED_HERE_MIN_64_CHARS');
define('JWT_ALGORITHM', 'HS256');
define('JWT_EXPIRATION', 86400);  // 24 horas

// Admin API Key (CRITICAL - MUDAR!)
// Gerar: openssl rand -hex 32
define('ADMIN_API_KEY', 'CHANGE_ME_ADMIN_KEY_HEX_64_CHARS_HERE');

// Server Configuration
define('SERVER_URL', 'https://plugin.nelsonsilvaphotography.com');
define('API_VERSION', 'v1');

// Security Settings
define('ENABLE_RATE_LIMITING', true);
define('RATE_LIMIT_REQUESTS', 100);  // Max requests por hora por IP
define('RATE_LIMIT_WINDOW', 3600);   // 1 hora

define('ENABLE_IP_WHITELIST', false);  // Se true, apenas IPs da whitelist
define('IP_WHITELIST', [
    // '203.0.113.1',  // Exemplo
]);

define('ENABLE_ANTI_FRAUD', true);
define('MAX_ACTIVATIONS_PER_DAY', 5);  // Por license key
define('MAX_ACTIVATIONS_PER_IP_DAY', 10);  // Por IP

// VM Detection (bloquear VMs suspeitas)
define('DETECT_VMS', true);
define('BLOCK_KNOWN_VMS', false);  // Se true, rejeita VMs conhecidas

// Logging
define('ENABLE_LOGGING', true);
define('LOG_FILE', __DIR__ . '/../logs/license_server.log');
define('LOG_LEVEL', 'INFO');  // DEBUG, INFO, WARNING, ERROR

// Email Notifications (opcional)
define('ENABLE_EMAIL_ALERTS', false);
define('ALERT_EMAIL', 'nelson@nelsonsilvaphotography.com');
define('SMTP_HOST', 'mail.nelsonsilvaphotography.com');
define('SMTP_PORT', 587);
define('SMTP_USER', 'alerts@nelsonsilvaphotography.com');
define('SMTP_PASS', '');
define('SMTP_FROM', 'NSP License Server <alerts@nelsonsilvaphotography.com>');

// Feature Plans Configuration
define('PLANS', [
    'trial' => [
        'name' => 'Trial',
        'price' => 0,
        'max_activations' => 1,
        'duration_days' => 30,
        'features' => [
            'basic_adjustments' => true,
            'lightgbm_model' => true,
            'neural_network' => false,
            'smart_culling' => false,
            'auto_profiling' => false,
            'batch_processing' => true,
            'max_photos_per_batch' => 50,
            'priority_support' => false,
        ]
    ],
    'personal' => [
        'name' => 'Personal',
        'price' => 79,
        'max_activations' => 2,
        'duration_days' => 365,
        'features' => [
            'basic_adjustments' => true,
            'lightgbm_model' => true,
            'neural_network' => true,
            'smart_culling' => true,
            'auto_profiling' => false,
            'batch_processing' => true,
            'max_photos_per_batch' => 500,
            'priority_support' => false,
        ]
    ],
    'professional' => [
        'name' => 'Professional',
        'price' => 149,
        'max_activations' => 3,
        'duration_days' => 365,
        'features' => [
            'basic_adjustments' => true,
            'lightgbm_model' => true,
            'neural_network' => true,
            'smart_culling' => true,
            'auto_profiling' => true,
            'batch_processing' => true,
            'max_photos_per_batch' => 5000,
            'priority_support' => true,
        ]
    ],
    'studio' => [
        'name' => 'Studio',
        'price' => 499,
        'max_activations' => 10,
        'duration_days' => 365,
        'features' => [
            'basic_adjustments' => true,
            'lightgbm_model' => true,
            'neural_network' => true,
            'smart_culling' => true,
            'auto_profiling' => true,
            'batch_processing' => true,
            'max_photos_per_batch' => PHP_INT_MAX,
            'priority_support' => true,
            'team_collaboration' => true,
        ]
    ],
]);

// Development Mode (DESLIGAR EM PRODUÇÃO!)
define('DEV_MODE', false);

if (DEV_MODE) {
    ini_set('display_errors', 1);
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', 0);
    error_reporting(0);
}

// Timezone
date_default_timezone_set('Europe/Lisbon');

// CORS Settings (ajustar para teu domínio)
define('ALLOW_CORS', true);
define('CORS_ORIGINS', [
    'https://nelsonsilvaphotography.com',
    'https://www.nelsonsilvaphotography.com',
]);

if (DEV_MODE) {
    // Allow localhost em dev
    define('CORS_ORIGINS_DEV', [
        'http://localhost',
        'http://127.0.0.1',
    ]);
}
