/**
 * NSP Control Center V2 - Main Dashboard Logic
 * Orchestrates all dashboard functionality
 */

class NSPDashboard {
    constructor() {
        this.updateInterval = null;
        this.updateFrequency = 5000; // 5 seconds
        this.isServerOnline = false;
        this.logs = [];
        this.maxLogs = 100;
    }

    /**
     * Initialize dashboard on page load
     */
    async initialize() {
        console.log('🚀 Inicializando NSP Control Center V2...');

        // Initialize charts
        charts.initializeCharts();

        // Load initial data
        await this.loadInitialData();

        // Start auto-refresh
        this.startAutoRefresh();

        // Connect WebSocket for real-time logs
        this.connectWebSocket();

        // Setup event listeners
        this.setupEventListeners();

        console.log('✅ Dashboard inicializado com sucesso!');
    }

    /**
     * Load all initial data
     */
    async loadInitialData() {
        await Promise.all([
            this.updateServerStatus(),
            this.updateMetrics(),
            this.updateTrainingStatus(),
            this.updateFeedbackStats(),
            this.loadSettings(),
            this.loadRecentLogs()
        ]);
    }

    /**
     * Refresh all data
     */
    async refreshAll() {
        console.log('🔄 A atualizar dados...');
        await this.loadInitialData();
        this.addLog('info', 'Dashboard atualizado');
    }

    /**
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }

        this.updateInterval = setInterval(async () => {
            if (this.isServerOnline) {
                await Promise.all([
                    this.updateServerStatus(),
                    this.updateMetrics(),
                    this.updateTrainingStatus()
                ]);
            }
        }, this.updateFrequency);
    }

    /**
     * Stop auto-refresh interval
     */
    stopAutoRefresh() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    // ========================================================================
    // SERVER STATUS
    // ========================================================================

    /**
     * Update server status indicators
     */
    async updateServerStatus() {
        try {
            const status = await apiClient.getServerStatus();
            this.isServerOnline = true;

            // Update status indicator
            const statusEl = document.getElementById('serverStatus');
            const indicator = statusEl.querySelector('.status-indicator');
            const text = statusEl.querySelector('.status-text');

            indicator.classList.remove('offline');
            indicator.classList.add('online');
            text.textContent = 'Online';

            // Update metrics
            document.getElementById('memoryUsage').textContent =
                NSPApiClient.formatMemory(status.memory_mb);
            document.getElementById('cpuUsage').textContent =
                `${status.cpu_percent.toFixed(1)}%`;
            document.getElementById('uptime').textContent =
                NSPApiClient.formatUptime(status.uptime_seconds);

        } catch (error) {
            this.isServerOnline = false;

            const statusEl = document.getElementById('serverStatus');
            const indicator = statusEl.querySelector('.status-indicator');
            const text = statusEl.querySelector('.status-text');

            indicator.classList.remove('online');
            indicator.classList.add('offline');
            text.textContent = 'Offline';

            console.error('Erro ao obter status do servidor:', error);
        }
    }

    // ========================================================================
    // METRICS
    // ========================================================================

    /**
     * Update prediction metrics
     */
    async updateMetrics() {
        try {
            const metrics = await apiClient.getPredictionMetrics();

            // Update metric cards
            document.getElementById('metricsToday').textContent = metrics.total_today;
            document.getElementById('successRate').textContent =
                NSPApiClient.formatPercent(metrics.success_rate);
            document.getElementById('avgTime').textContent =
                NSPApiClient.formatMs(metrics.average_time_ms);
            document.getElementById('avgConfidence').textContent =
                NSPApiClient.formatPercent(metrics.confidence_average);

            // Update preset distribution chart
            if (metrics.preset_distribution && Object.keys(metrics.preset_distribution).length > 0) {
                charts.updatePresetDistribution(metrics.preset_distribution);
            }

        } catch (error) {
            console.error('Erro ao obter métricas:', error);
        }
    }

    // ========================================================================
    // TRAINING
    // ========================================================================

    /**
     * Update training status
     */
    async updateTrainingStatus() {
        try {
            const status = await apiClient.getTrainingStatus();

            const statusBadge = document.querySelector('.training-status .status-badge');
            const progressDiv = document.getElementById('trainingProgress');
            const formDiv = document.getElementById('trainingForm');
            const btnStart = document.getElementById('btnStartTraining');
            const btnStop = document.getElementById('btnStopTraining');

            if (status.is_training) {
                // Show training progress
                statusBadge.textContent = 'Ativo';
                statusBadge.classList.remove('idle');
                statusBadge.classList.add('training');

                progressDiv.style.display = 'block';
                formDiv.style.display = 'none';

                btnStart.style.display = 'none';
                btnStop.style.display = 'inline-flex';

                // Update progress info
                document.getElementById('currentEpoch').textContent = status.current_epoch || 0;
                document.getElementById('totalEpochs').textContent = status.total_epochs || 0;
                document.getElementById('currentLoss').textContent =
                    status.current_loss ? status.current_loss.toFixed(4) : '-';

                const progressPercent = status.progress_percent || 0;
                document.getElementById('progressFill').style.width = `${progressPercent}%`;

                if (status.eta_seconds) {
                    const minutes = Math.floor(status.eta_seconds / 60);
                    const seconds = status.eta_seconds % 60;
                    document.getElementById('eta').textContent = `${minutes}m ${seconds}s`;
                } else {
                    document.getElementById('eta').textContent = 'Calculando...';
                }

            } else {
                // Show training form
                statusBadge.textContent = 'Inativo';
                statusBadge.classList.remove('training');
                statusBadge.classList.add('idle');

                progressDiv.style.display = 'none';
                formDiv.style.display = 'block';

                btnStart.style.display = 'inline-flex';
                btnStop.style.display = 'none';
            }

        } catch (error) {
            console.error('Erro ao obter status de treino:', error);
        }
    }

    /**
     * Start training with form parameters
     */
    async startTraining() {
        const params = {
            numPresets: parseInt(document.getElementById('numPresets').value),
            minRating: parseInt(document.getElementById('minRating').value),
            epochsClassifier: parseInt(document.getElementById('epochsClassifier').value),
            epochsRefiner: parseInt(document.getElementById('epochsRefiner').value)
        };

        try {
            const result = await apiClient.startTraining(params);
            this.addLog('success', `Treino iniciado: ${params.numPresets} presets, ${params.epochsClassifier + params.epochsRefiner} épocas totais`);
            await this.updateTrainingStatus();
        } catch (error) {
            this.addLog('error', `Erro ao iniciar treino: ${error.message}`);
        }
    }

    /**
     * Stop current training
     */
    async stopTraining() {
        if (!confirm('Tem a certeza que deseja parar o treino?')) {
            return;
        }

        try {
            const result = await apiClient.stopTraining();
            this.addLog('warning', 'Treino parado pelo utilizador');
            await this.updateTrainingStatus();
        } catch (error) {
            this.addLog('error', `Erro ao parar treino: ${error.message}`);
        }
    }

    // ========================================================================
    // FEEDBACK
    // ========================================================================

    /**
     * Update feedback statistics
     */
    async updateFeedbackStats() {
        try {
            const stats = await apiClient.getFeedbackStats();

            document.getElementById('totalFeedbacks').textContent = stats.total_feedbacks;
            document.getElementById('positiveFeedbacks').textContent = stats.positive_count;
            document.getElementById('negativeFeedbacks').textContent = stats.negative_count;
            document.getElementById('mostCorrectedPreset').textContent = stats.most_corrected_preset;
            document.getElementById('mostCorrectedSlider').textContent = stats.most_corrected_slider;

        } catch (error) {
            console.error('Erro ao obter estatísticas de feedback:', error);
        }
    }

    // ========================================================================
    // SETTINGS
    // ========================================================================

    /**
     * Load settings from server
     */
    async loadSettings() {
        try {
            const settings = await apiClient.getSettings();

            document.getElementById('serverUrl').value = settings.server_url;
            document.getElementById('serverPort').value = settings.server_port;
            document.getElementById('confidenceThreshold').value = settings.confidence_threshold * 100;
            document.getElementById('confidenceValue').textContent = `${Math.round(settings.confidence_threshold * 100)}%`;
            document.getElementById('activeLearning').checked = settings.active_learning_enabled;

        } catch (error) {
            console.error('Erro ao carregar configurações:', error);
        }
    }

    /**
     * Save settings to server
     */
    async saveSettings() {
        const settings = {
            server_url: document.getElementById('serverUrl').value,
            server_port: parseInt(document.getElementById('serverPort').value),
            num_presets: 4, // Keep existing
            min_rating: 3, // Keep existing
            classifier_epochs: 50, // Keep existing
            refiner_epochs: 100, // Keep existing
            batch_size: 32, // Keep existing
            patience: 7, // Keep existing
            confidence_threshold: parseFloat(document.getElementById('confidenceThreshold').value) / 100,
            active_learning_enabled: document.getElementById('activeLearning').checked
        };

        try {
            await apiClient.updateSettings(settings);
            this.addLog('success', 'Configurações guardadas com sucesso');
        } catch (error) {
            this.addLog('error', `Erro ao guardar configurações: ${error.message}`);
        }
    }

    // ========================================================================
    // LOGS
    // ========================================================================

    /**
     * Load recent logs from server
     */
    async loadRecentLogs() {
        try {
            const response = await apiClient.getRecentLogs(50);

            if (response.logs && response.logs.length > 0) {
                response.logs.forEach(log => {
                    this.addLog(log.level.toLowerCase(), log.message, log.timestamp);
                });
            }
        } catch (error) {
            console.error('Erro ao carregar logs:', error);
        }
    }

    /**
     * Add log entry to UI
     */
    addLog(level, message, timestamp = null) {
        const container = document.getElementById('logsContainer');

        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${level}`;

        const time = timestamp ? new Date(timestamp).toLocaleTimeString('pt-PT') : new Date().toLocaleTimeString('pt-PT');

        logEntry.innerHTML = `
            <span class="log-time">${time}</span>
            <span class="log-message">${message}</span>
        `;

        container.insertBefore(logEntry, container.firstChild);

        // Keep only last N logs
        this.logs.unshift({ level, message, timestamp: time });
        if (this.logs.length > this.maxLogs) {
            this.logs.pop();
            const lastEntry = container.lastChild;
            if (lastEntry) container.removeChild(lastEntry);
        }

        // Auto-scroll to top
        container.scrollTop = 0;
    }

    /**
     * Clear all logs
     */
    clearLogs() {
        const container = document.getElementById('logsContainer');
        container.innerHTML = '<div class="log-entry info"><span class="log-time">--:--:--</span><span class="log-message">Logs limpos</span></div>';
        this.logs = [];
    }

    /**
     * Connect to WebSocket for real-time logs
     */
    connectWebSocket() {
        apiClient.connectLogsWebSocket(
            (logData) => {
                this.addLog(logData.level.toLowerCase(), logData.message, logData.timestamp);
            },
            (error) => {
                console.error('WebSocket error:', error);
            }
        );
    }

    // ========================================================================
    // EVENT LISTENERS
    // ========================================================================

    /**
     * Setup UI event listeners
     */
    setupEventListeners() {
        // Confidence threshold slider
        const confidenceSlider = document.getElementById('confidenceThreshold');
        const confidenceValue = document.getElementById('confidenceValue');

        confidenceSlider.addEventListener('input', (e) => {
            confidenceValue.textContent = `${e.target.value}%`;
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + R: Refresh
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                this.refreshAll();
            }
        });

        console.log('✅ Event listeners configurados');
    }

    /**
     * Cleanup on page unload
     */
    cleanup() {
        this.stopAutoRefresh();
        apiClient.disconnectLogsWebSocket();
        charts.destroyCharts();
    }
}

// ============================================================================
// INITIALIZE ON DOM READY
// ============================================================================

const dashboard = new NSPDashboard();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        dashboard.initialize();
    });
} else {
    dashboard.initialize();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    dashboard.cleanup();
});
