/**
 * NSP Control Center V2 - Charts Module
 * Handles all Chart.js visualizations
 */

class NSPCharts {
    constructor() {
        this.charts = {};
        this.chartDefaults = {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        color: '#cbd5e1',
                        font: {
                            family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto'",
                            size: 12
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#94a3b8'
                    },
                    grid: {
                        color: '#475569'
                    }
                },
                y: {
                    ticks: {
                        color: '#94a3b8'
                    },
                    grid: {
                        color: '#475569'
                    }
                }
            }
        };
    }

    /**
     * Initialize all charts
     */
    initializeCharts() {
        this.createPresetDistributionChart();
        this.createWeeklyPredictionsChart();
    }

    /**
     * Create Preset Distribution Pie Chart
     */
    createPresetDistributionChart() {
        const ctx = document.getElementById('presetDistChart');
        if (!ctx) return;

        // Destroy existing chart if any
        if (this.charts.presetDist) {
            this.charts.presetDist.destroy();
        }

        this.charts.presetDist = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Natural', 'Vibrante', 'Moody', 'Suave'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        '#10b981', // green - Natural
                        '#f59e0b', // amber - Vibrante
                        '#6366f1', // indigo - Moody
                        '#8b5cf6'  // purple - Suave
                    ],
                    borderColor: '#1e293b',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#cbd5e1',
                            padding: 15,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Update Preset Distribution Chart with new data
     */
    updatePresetDistribution(presetDistribution) {
        if (!this.charts.presetDist) return;

        const presetMap = {
            'Preset 0': 0,
            'Preset 1': 1,
            'Preset 2': 2,
            'Preset 3': 3
        };

        const data = [0, 0, 0, 0];

        // Map preset names to indices
        for (const [presetName, count] of Object.entries(presetDistribution)) {
            const index = presetMap[presetName];
            if (index !== undefined) {
                data[index] = count;
            }
        }

        this.charts.presetDist.data.datasets[0].data = data;
        this.charts.presetDist.update();
    }

    /**
     * Create Weekly Predictions Bar Chart
     */
    createWeeklyPredictionsChart() {
        const ctx = document.getElementById('weeklyChart');
        if (!ctx) return;

        // Destroy existing chart if any
        if (this.charts.weekly) {
            this.charts.weekly.destroy();
        }

        // Generate last 7 days labels
        const labels = [];
        const today = new Date();
        for (let i = 6; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString('pt-PT', { weekday: 'short', day: 'numeric' }));
        }

        this.charts.weekly = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Sucessos',
                        data: [0, 0, 0, 0, 0, 0, 0],
                        backgroundColor: '#10b981',
                        borderRadius: 4
                    },
                    {
                        label: 'Falhas',
                        data: [0, 0, 0, 0, 0, 0, 0],
                        backgroundColor: '#ef4444',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#cbd5e1',
                            padding: 15,
                            font: {
                                size: 12
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        ticks: {
                            color: '#94a3b8'
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: {
                            color: '#94a3b8',
                            stepSize: 10
                        },
                        grid: {
                            color: '#475569'
                        }
                    }
                }
            }
        });
    }

    /**
     * Update Weekly Predictions Chart with new data
     * Expected format: { dates: ['2025-11-07', ...], success: [10, ...], failures: [2, ...] }
     */
    updateWeeklyPredictions(weeklyData) {
        if (!this.charts.weekly) return;

        // Update labels if provided
        if (weeklyData.labels) {
            this.charts.weekly.data.labels = weeklyData.labels;
        }

        // Update success data
        if (weeklyData.success) {
            this.charts.weekly.data.datasets[0].data = weeklyData.success;
        }

        // Update failure data
        if (weeklyData.failures) {
            this.charts.weekly.data.datasets[1].data = weeklyData.failures;
        }

        this.charts.weekly.update();
    }

    /**
     * Update all charts with mock data (for testing)
     */
    updateWithMockData() {
        // Mock preset distribution
        this.updatePresetDistribution({
            'Preset 0': 45,
            'Preset 1': 30,
            'Preset 2': 15,
            'Preset 3': 10
        });

        // Mock weekly data
        this.updateWeeklyPredictions({
            success: [20, 35, 42, 38, 45, 50, 48],
            failures: [2, 3, 1, 4, 2, 3, 2]
        });
    }

    /**
     * Reset all charts to zero data
     */
    resetCharts() {
        if (this.charts.presetDist) {
            this.charts.presetDist.data.datasets[0].data = [0, 0, 0, 0];
            this.charts.presetDist.update();
        }

        if (this.charts.weekly) {
            this.charts.weekly.data.datasets[0].data = [0, 0, 0, 0, 0, 0, 0];
            this.charts.weekly.data.datasets[1].data = [0, 0, 0, 0, 0, 0, 0];
            this.charts.weekly.update();
        }
    }

    /**
     * Destroy all charts (cleanup)
     */
    destroyCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
    }
}

// Create global instance
const charts = new NSPCharts();
