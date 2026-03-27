/**
 * NSP Control Center V2 - API Client
 * Handles all HTTP requests to the backend FastAPI server
 */

class NSPApiClient {
    constructor(baseUrl = 'http://127.0.0.1:5000') {
        this.baseUrl = baseUrl;
        this.apiPrefix = '/api/dashboard';
        this.wsConnection = null;
        this.wsReconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    /**
     * Generic HTTP request handler
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${this.apiPrefix}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        try {
            const response = await fetch(url, { ...defaultOptions, ...options });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * GET request
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    // ========================================================================
    // SERVER STATUS
    // ========================================================================

    /**
     * Get server status and metrics
     */
    async getServerStatus() {
        return this.get('/status');
    }

    /**
     * Check if server is online
     */
    async isServerOnline() {
        try {
            const status = await this.getServerStatus();
            return status.status === 'online';
        } catch (error) {
            return false;
        }
    }

    // ========================================================================
    // METRICS
    // ========================================================================

    /**
     * Get prediction metrics
     */
    async getPredictionMetrics() {
        return this.get('/metrics');
    }

    // ========================================================================
    // TRAINING
    // ========================================================================

    /**
     * Get training status
     */
    async getTrainingStatus() {
        return this.get('/training/status');
    }

    /**
     * Start training with parameters
     */
    async startTraining(params = {}) {
        const queryParams = new URLSearchParams({
            num_presets: params.numPresets || 4,
            min_rating: params.minRating || 3,
            epochs_classifier: params.epochsClassifier || 50,
            epochs_refiner: params.epochsRefiner || 100,
        });

        return this.post(`/training/start?${queryParams}`);
    }

    /**
     * Stop current training
     */
    async stopTraining() {
        return this.post('/training/stop');
    }

    // ========================================================================
    // FEEDBACK
    // ========================================================================

    /**
     * Get feedback statistics
     */
    async getFeedbackStats() {
        return this.get('/feedback/stats');
    }

    // ========================================================================
    // SETTINGS
    // ========================================================================

    /**
     * Get current settings
     */
    async getSettings() {
        return this.get('/settings');
    }

    /**
     * Update settings
     */
    async updateSettings(settings) {
        return this.put('/settings', settings);
    }

    // ========================================================================
    // LOGS
    // ========================================================================

    /**
     * Get recent logs
     */
    async getRecentLogs(limit = 100) {
        return this.get(`/logs/recent?limit=${limit}`);
    }

    /**
     * Connect to WebSocket for real-time logs
     */
    connectLogsWebSocket(onMessage, onError = null) {
        const wsUrl = this.baseUrl.replace('http', 'ws') + this.apiPrefix + '/ws/logs';

        try {
            this.wsConnection = new WebSocket(wsUrl);

            this.wsConnection.onopen = () => {
                console.log('✅ WebSocket conectado');
                this.wsReconnectAttempts = 0;
            };

            this.wsConnection.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    onMessage(data);
                } catch (error) {
                    console.error('Erro ao processar mensagem WebSocket:', error);
                }
            };

            this.wsConnection.onerror = (error) => {
                console.error('WebSocket erro:', error);
                if (onError) onError(error);
            };

            this.wsConnection.onclose = () => {
                console.warn('⚠️  WebSocket desconectado');

                // Tentar reconectar
                if (this.wsReconnectAttempts < this.maxReconnectAttempts) {
                    this.wsReconnectAttempts++;
                    const delay = Math.min(1000 * Math.pow(2, this.wsReconnectAttempts), 30000);
                    console.log(`Tentando reconectar em ${delay/1000}s (tentativa ${this.wsReconnectAttempts}/${this.maxReconnectAttempts})`);

                    setTimeout(() => {
                        this.connectLogsWebSocket(onMessage, onError);
                    }, delay);
                }
            };

        } catch (error) {
            console.error('Erro ao conectar WebSocket:', error);
            if (onError) onError(error);
        }
    }

    /**
     * Disconnect WebSocket
     */
    disconnectLogsWebSocket() {
        if (this.wsConnection) {
            this.wsConnection.close();
            this.wsConnection = null;
        }
    }

    // ========================================================================
    // UTILITY METHODS
    // ========================================================================

    /**
     * Format uptime seconds to human readable string
     */
    static formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (days > 0) {
            return `${days}d ${hours}h ${minutes}m`;
        } else if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    }

    /**
     * Format milliseconds to seconds
     */
    static formatMs(ms) {
        if (ms >= 1000) {
            return `${(ms / 1000).toFixed(1)}s`;
        }
        return `${Math.round(ms)}ms`;
    }

    /**
     * Format memory in MB
     */
    static formatMemory(mb) {
        if (mb >= 1024) {
            return `${(mb / 1024).toFixed(1)} GB`;
        }
        return `${Math.round(mb)} MB`;
    }

    /**
     * Format percentage
     */
    static formatPercent(value) {
        return `${Math.round(value * 100)}%`;
    }
}

// Create global instance
const apiClient = new NSPApiClient();
