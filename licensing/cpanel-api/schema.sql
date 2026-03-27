-- NSP Plugin - License Server Database Schema
-- MySQL 5.7+ / MariaDB 10.2+
-- 
-- USAGE: Import via phpMyAdmin or mysql CLI:
--   mysql -u USER -p DATABASE_NAME < schema.sql

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

-- ============================================================================
-- TABLE: licenses
-- Stores license keys and associated metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS `licenses` (
  `id` char(36) NOT NULL PRIMARY KEY,
  `license_key` varchar(64) NOT NULL UNIQUE,
  `email` varchar(255) NOT NULL,
  `plan` enum('trial','personal','professional','studio') NOT NULL DEFAULT 'trial',
  `status` enum('active','expired','suspended','revoked','archived') NOT NULL DEFAULT 'active',
  `max_activations` int(11) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expires_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `revoke_reason` text DEFAULT NULL,
  `notes` text DEFAULT NULL,
  INDEX `idx_email` (`email`),
  INDEX `idx_status` (`status`),
  INDEX `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: activations
-- Stores machine activations for each license
-- ============================================================================

CREATE TABLE IF NOT EXISTS `activations` (
  `id` char(36) NOT NULL PRIMARY KEY,
  `license_id` char(36) NOT NULL,
  `machine_id` varchar(128) NOT NULL,
  `machine_name` varchar(255) DEFAULT NULL,
  `machine_os` varchar(50) DEFAULT NULL,
  `machine_os_version` varchar(50) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `activated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_heartbeat` datetime DEFAULT NULL,
  `deactivated_at` datetime DEFAULT NULL,
  `plugin_version` varchar(20) DEFAULT NULL,
  FOREIGN KEY (`license_id`) REFERENCES `licenses`(`id`) ON DELETE CASCADE,
  INDEX `idx_license_id` (`license_id`),
  INDEX `idx_machine_id` (`machine_id`),
  INDEX `idx_last_heartbeat` (`last_heartbeat`),
  UNIQUE KEY `unique_active_machine` (`license_id`, `machine_id`, `deactivated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: heartbeats
-- Stores heartbeat pings for analytics and activity monitoring
-- ============================================================================

CREATE TABLE IF NOT EXISTS `heartbeats` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `activation_id` char(36) NOT NULL,
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `plugin_version` varchar(20) DEFAULT NULL,
  `photos_processed` int(11) DEFAULT 0,
  `uptime_hours` decimal(10,2) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  FOREIGN KEY (`activation_id`) REFERENCES `activations`(`id`) ON DELETE CASCADE,
  INDEX `idx_activation_id` (`activation_id`),
  INDEX `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: rate_limits
-- Stores rate limiting counters per IP and endpoint
-- ============================================================================

CREATE TABLE IF NOT EXISTS `rate_limits` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `ip_address` varchar(45) NOT NULL,
  `endpoint` varchar(100) NOT NULL,
  `request_count` int(11) NOT NULL DEFAULT 1,
  `window_start` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `blocked_until` datetime DEFAULT NULL,
  UNIQUE KEY `unique_ip_endpoint_window` (`ip_address`, `endpoint`, `window_start`),
  INDEX `idx_ip_address` (`ip_address`),
  INDEX `idx_window_start` (`window_start`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: audit_log
-- Logs all admin actions for security audit
-- ============================================================================

CREATE TABLE IF NOT EXISTS `audit_log` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `action` varchar(100) NOT NULL,
  `admin_ip` varchar(45) DEFAULT NULL,
  `license_id` char(36) DEFAULT NULL,
  `details` text DEFAULT NULL,
  INDEX `idx_timestamp` (`timestamp`),
  INDEX `idx_action` (`action`),
  INDEX `idx_license_id` (`license_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SAMPLE DATA (Optional - Remove in production)
-- ============================================================================

-- Criar uma licença de teste
INSERT INTO `licenses` (`id`, `license_key`, `email`, `plan`, `status`, `max_activations`, `expires_at`)
VALUES (
  UUID(),
  'NSP-TEST-1234-5678-ABCD',
  'test@nelsonsilvaphotography.com',
  'professional',
  'active',
  3,
  DATE_ADD(NOW(), INTERVAL 365 DAY)
);

-- ============================================================================
-- VIEWS (úteis para analytics)
-- ============================================================================

-- View: Licenças ativas com contagem de ativações
CREATE OR REPLACE VIEW `v_licenses_summary` AS
SELECT 
    l.id,
    l.license_key,
    l.email,
    l.plan,
    l.status,
    l.max_activations,
    l.created_at,
    l.expires_at,
    COUNT(a.id) as active_activations,
    MAX(a.last_heartbeat) as last_activity
FROM licenses l
LEFT JOIN activations a ON l.id = a.license_id AND a.deactivated_at IS NULL
GROUP BY l.id;

-- View: Ativações ativas com informação de licença
CREATE OR REPLACE VIEW `v_active_activations` AS
SELECT 
    a.id,
    a.machine_id,
    a.machine_name,
    a.activated_at,
    a.last_heartbeat,
    a.plugin_version,
    l.license_key,
    l.email,
    l.plan,
    TIMESTAMPDIFF(HOUR, a.last_heartbeat, NOW()) as hours_since_heartbeat
FROM activations a
JOIN licenses l ON a.license_id = l.id
WHERE a.deactivated_at IS NULL
ORDER BY a.last_heartbeat DESC;

-- ============================================================================
-- STORED PROCEDURES (opcional mas útil)
-- ============================================================================

DELIMITER $$

-- Procedure: Cleanup de dados antigos
CREATE PROCEDURE `sp_cleanup_old_data`()
BEGIN
    -- Apagar heartbeats >90 dias
    DELETE FROM heartbeats 
    WHERE timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY);
    
    -- Apagar rate_limits >7 dias
    DELETE FROM rate_limits 
    WHERE window_start < DATE_SUB(NOW(), INTERVAL 7 DAY);
    
    -- Arquivar licenças expiradas >1 ano
    UPDATE licenses 
    SET status = 'archived'
    WHERE status = 'expired' 
      AND expires_at < DATE_SUB(NOW(), INTERVAL 365 DAY);
      
    SELECT 
        'Cleanup completed' as status,
        ROW_COUNT() as rows_affected;
END$$

-- Procedure: Estatísticas do sistema
CREATE PROCEDURE `sp_get_stats`()
BEGIN
    SELECT 
        (SELECT COUNT(*) FROM licenses WHERE status = 'active') as total_licenses,
        (SELECT COUNT(*) FROM activations WHERE deactivated_at IS NULL) as total_activations,
        (SELECT COUNT(*) FROM heartbeats WHERE timestamp > DATE_SUB(NOW(), INTERVAL 24 HOUR)) as heartbeats_24h,
        (SELECT COUNT(DISTINCT license_id) FROM activations 
         WHERE last_heartbeat > DATE_SUB(NOW(), INTERVAL 7 DAY)) as active_users_7d;
END$$

DELIMITER ;

-- ============================================================================
-- TRIGGERS (opcional - validações adicionais)
-- ============================================================================

DELIMITER $$

-- Trigger: Validar max_activations antes de insert
CREATE TRIGGER `trg_check_max_activations`
BEFORE INSERT ON `activations`
FOR EACH ROW
BEGIN
    DECLARE current_count INT;
    DECLARE max_allowed INT;
    
    SELECT COUNT(*) INTO current_count
    FROM activations
    WHERE license_id = NEW.license_id 
      AND deactivated_at IS NULL;
    
    SELECT max_activations INTO max_allowed
    FROM licenses
    WHERE id = NEW.license_id;
    
    IF current_count >= max_allowed THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Maximum activations reached for this license';
    END IF;
END$$

DELIMITER ;

-- ============================================================================
-- INITIAL GRANTS (ajustar conforme necessário)
-- ============================================================================

-- Criar user se não existir (executar manualmente com root)
-- CREATE USER IF NOT EXISTS 'nsp_user'@'localhost' IDENTIFIED BY 'STRONG_PASSWORD_HERE';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON nsp_licenses.* TO 'nsp_user'@'localhost';
-- FLUSH PRIVILEGES;

-- ============================================================================
-- INDEXES ADICIONAIS (para performance em queries comuns)
-- ============================================================================

-- Composite index para queries de validação
CREATE INDEX `idx_license_validation` ON `licenses` (`license_key`, `status`, `expires_at`);

-- Composite index para queries de ativações
CREATE INDEX `idx_activation_lookup` ON `activations` (`license_id`, `machine_id`, `deactivated_at`);

-- Index para queries de analytics
CREATE INDEX `idx_heartbeat_analytics` ON `heartbeats` (`timestamp`, `activation_id`);

-- ============================================================================
-- DONE
-- ============================================================================

SELECT 
    'Database schema created successfully!' as status,
    DATABASE() as database_name,
    NOW() as timestamp;
