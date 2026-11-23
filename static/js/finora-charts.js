/**
 * FINORA - Interactive Financial Charts (Chart.js)
 * High-precision formatting with INR (₹) denomination support
 */

window.finoraCharts = {
  monthlyTrendChart: null,
  categoryChart: null,
  weeklyChart: null,

  init: function() {
    this.fetchAndRender();
  },

  fetchAndRender: function() {
    fetch('/api/charts-data/')
      .then(res => res.json())
      .then(data => {
        this.renderMonthlyTrend(data.monthly_trend);
        this.renderCategoryBreakdown(data.category_breakdown);
        if (data.weekly_spending && document.getElementById('weeklyChart')) {
          this.renderWeeklyChart(data.weekly_spending);
        }
      })
      .catch(err => console.error('Error fetching financial chart data:', err));
  },

  renderMonthlyTrend: function(trendData) {
    const ctx = document.getElementById('monthlyTrendChart');
    if (!ctx) return;

    if (this.monthlyTrendChart) {
      this.monthlyTrendChart.destroy();
    }

    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(16, 24, 40, 0.06)';
    const textColor = isDark ? '#98A2B3' : '#475467';
    const sym = window.FINORA_CURRENCY_SYMBOL || '₹';

    this.monthlyTrendChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: trendData.labels,
        datasets: [
          {
            label: 'Income (Inflow)',
            data: trendData.income,
            backgroundColor: 'rgba(22, 166, 117, 0.85)',
            borderColor: '#16A675',
            borderWidth: 1.5,
            borderRadius: 7,
          },
          {
            label: 'Expenses (Outflow)',
            data: trendData.expenses,
            backgroundColor: 'rgba(116, 86, 216, 0.85)',
            borderColor: '#7456D8',
            borderWidth: 1.5,
            borderRadius: 7,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { color: textColor, font: { weight: '700', size: 12 } }
          },
          tooltip: {
            backgroundColor: isDark ? '#0D121E' : '#FFFFFF',
            titleColor: isDark ? '#FFF' : '#0F172A',
            bodyColor: isDark ? '#CBD5E1' : '#334155',
            borderColor: isDark ? 'rgba(255,255,255,0.1)' : '#E2E8F0',
            borderWidth: 1,
            padding: 12,
            boxPadding: 6,
            callbacks: {
              label: function(context) {
                let label = context.dataset.label || '';
                if (label) label += ': ';
                label += sym + context.parsed.y.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                return label;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: textColor, font: { weight: '600' } }
          },
          y: {
            grid: { color: gridColor },
            ticks: {
              color: textColor,
              callback: function(val) {
                if (val >= 100000) return sym + (val / 100000).toFixed(1) + 'L';
                if (val >= 1000) return sym + (val / 1000).toFixed(0) + 'k';
                return sym + val;
              }
            }
          }
        }
      }
    });
  },

  renderCategoryBreakdown: function(catData) {
    const ctx = document.getElementById('categoryPieChart');
    if (!ctx) return;

    if (this.categoryChart) {
      this.categoryChart.destroy();
    }

    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    const textColor = isDark ? '#94A3B8' : '#64748B';
    const sym = window.FINORA_CURRENCY_SYMBOL || '₹';

    if (!catData.totals || catData.totals.length === 0 || catData.totals.every(v => v === 0)) {
      return;
    }

    this.categoryChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: catData.labels,
        datasets: [{
          data: catData.totals,
          backgroundColor: catData.colors,
          borderWidth: 3,
          borderColor: isDark ? '#0D121E' : '#FFFFFF',
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: {
            position: 'right',
            labels: { color: textColor, font: { size: 11, weight: '600' } }
          },
          tooltip: {
            backgroundColor: isDark ? '#0D121E' : '#FFFFFF',
            titleColor: isDark ? '#FFF' : '#0F172A',
            bodyColor: isDark ? '#CBD5E1' : '#334155',
            borderColor: isDark ? 'rgba(255,255,255,0.1)' : '#E2E8F0',
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: function(context) {
                return ' ' + context.label + ': ' + sym + context.parsed.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
              }
            }
          }
        }
      }
    });
  },

  renderWeeklyChart: function(weekData) {
    const ctx = document.getElementById('weeklyChart');
    if (!ctx) return;

    if (this.weeklyChart) {
      this.weeklyChart.destroy();
    }

    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
    const textColor = isDark ? '#94A3B8' : '#64748B';
    const sym = window.FINORA_CURRENCY_SYMBOL || '₹';

    this.weeklyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: weekData.labels,
        datasets: [{
          label: 'Spending',
          data: weekData.data,
          fill: true,
          borderColor: '#3B82F6',
          backgroundColor: 'rgba(59, 130, 246, 0.12)',
          tension: 0.45,
          pointRadius: 5,
          pointHoverRadius: 7,
          pointBackgroundColor: '#3B82F6',
          borderWidth: 2.5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                return ' Spend: ' + sym + context.parsed.y.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: textColor, font: { weight: '600' } } },
          y: {
            grid: { color: gridColor },
            ticks: {
              color: textColor,
              callback: function(val) {
                if (val >= 1000) return sym + (val / 1000).toFixed(0) + 'k';
                return sym + val;
              }
            }
          }
        }
      }
    });
  },

  updateTheme: function() {
    this.fetchAndRender();
  }
};

document.addEventListener('DOMContentLoaded', () => {
  if (typeof Chart !== 'undefined') {
    window.finoraCharts.init();
  }
});
