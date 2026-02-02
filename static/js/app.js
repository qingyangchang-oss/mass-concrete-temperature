/**
 * Mass Concrete Temperature Modeling Platform
 * Frontend JavaScript utilities
 */

// API helper functions
const api = {
    async get(url) {
        const response = await fetch(url);
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    },

    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    },

    async delete(url) {
        const response = await fetch(url, { method: 'DELETE' });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.status === 204 ? null : response.json();
    }
};

// Chart color schemes
const chartColors = {
    central: {
        line: '#e74c3c',
        fill: 'rgba(231, 76, 60, 0.1)'
    },
    side: {
        line: '#f39c12',
        fill: 'rgba(243, 156, 18, 0.1)'
    },
    surface: {
        line: '#3498db',
        fill: 'rgba(52, 152, 219, 0.1)'
    },
    ambient: {
        line: '#95a5a6',
        fill: 'rgba(149, 165, 166, 0.1)'
    },
    differential: {
        line: '#9b59b6',
        fill: 'rgba(155, 89, 182, 0.2)'
    },
    limit: {
        line: '#e74c3c'
    }
};

// Chart default options
const defaultChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
        legend: {
            position: 'top',
            labels: {
                usePointStyle: true,
                padding: 15
            }
        },
        tooltip: {
            mode: 'index',
            intersect: false,
            callbacks: {
                label: function(context) {
                    return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}°C`;
                }
            }
        }
    },
    scales: {
        x: {
            title: {
                display: true,
                text: 'Time (hours)'
            },
            grid: {
                display: true,
                color: 'rgba(0,0,0,0.05)'
            }
        },
        y: {
            title: {
                display: true,
                text: 'Temperature (°C)'
            },
            grid: {
                display: true,
                color: 'rgba(0,0,0,0.05)'
            }
        }
    },
    interaction: {
        mode: 'nearest',
        axis: 'x',
        intersect: false
    }
};

// Format date for display
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Format datetime for display
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Calculate statistics from data
function calculateStats(data) {
    if (!data || data.length === 0) return null;

    const values = data.filter(v => v !== null && !isNaN(v));
    if (values.length === 0) return null;

    const sum = values.reduce((a, b) => a + b, 0);
    const mean = sum / values.length;
    const max = Math.max(...values);
    const min = Math.min(...values);

    return { mean, max, min, count: values.length };
}

// Export data to CSV
function exportToCSV(data, filename) {
    if (!data || data.length === 0) {
        alert('No data to export');
        return;
    }

    const headers = Object.keys(data[0]);
    const csvRows = [headers.join(',')];

    for (const row of data) {
        const values = headers.map(header => {
            const value = row[header];
            if (value === null || value === undefined) return '';
            if (typeof value === 'number') return value.toFixed(2);
            return `"${value}"`;
        });
        csvRows.push(values.join(','));
    }

    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'export.csv';
    link.click();

    URL.revokeObjectURL(url);
}

// Debounce function for input handlers
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Show loading state
function showLoading(element, message = 'Loading...') {
    if (typeof element === 'string') {
        element = document.getElementById(element);
    }
    if (element) {
        element.innerHTML = `<p class="loading">${message}</p>`;
    }
}

// Show error message
function showError(element, message) {
    if (typeof element === 'string') {
        element = document.getElementById(element);
    }
    if (element) {
        element.innerHTML = `<p class="error">${message}</p>`;
    }
}

// Validate form data
function validateForm(formData, rules) {
    const errors = [];

    for (const [field, rule] of Object.entries(rules)) {
        const value = formData.get(field);

        if (rule.required && (!value || value.trim() === '')) {
            errors.push(`${rule.label || field} is required`);
            continue;
        }

        if (value && rule.type === 'number') {
            const num = parseFloat(value);
            if (isNaN(num)) {
                errors.push(`${rule.label || field} must be a number`);
            } else {
                if (rule.min !== undefined && num < rule.min) {
                    errors.push(`${rule.label || field} must be at least ${rule.min}`);
                }
                if (rule.max !== undefined && num > rule.max) {
                    errors.push(`${rule.label || field} must be at most ${rule.max}`);
                }
            }
        }
    }

    return errors;
}

// Create temperature chart
function createTemperatureChart(ctx, data, options = {}) {
    const chartOptions = {
        ...defaultChartOptions,
        ...options
    };

    return new Chart(ctx, {
        type: 'line',
        data: data,
        options: chartOptions
    });
}

// Format temperature difference with color
function formatDifferential(value, limit = 20) {
    const formatted = value.toFixed(1);
    if (value < limit * 0.75) {
        return `<span style="color: #27ae60">${formatted}°C</span>`;
    } else if (value < limit) {
        return `<span style="color: #f39c12">${formatted}°C</span>`;
    } else {
        return `<span style="color: #e74c3c">${formatted}°C</span>`;
    }
}

// Initialize tooltips (if needed)
function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(el => {
        el.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.dataset.tooltip;
            document.body.appendChild(tooltip);

            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
        });

        el.addEventListener('mouseleave', function() {
            document.querySelectorAll('.tooltip').forEach(t => t.remove());
        });
    });
}

// Document ready handler
document.addEventListener('DOMContentLoaded', function() {
    initTooltips();
});
