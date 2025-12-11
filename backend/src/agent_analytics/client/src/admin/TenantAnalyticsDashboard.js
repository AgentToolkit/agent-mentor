// TenantAnalyticsDashboard.js
import { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Line, Doughnut } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

// Tenant color mapping (consistent across all charts)
const TENANT_COLOR_MAP = {
  'cmhsxuem5000721pexvwuuina': '#0f62fe', // Acme Corp = Blue
  'bx9ks2em5000721pqrstuvwxy': '#8a3ffc', // TechStart Inc = Purple
  'default': '#ff832b', // Default Tenant = Orange
  'no tenant': '#1192e8', // Unassigned = Cyan
};

// Color palettes
const COLORS = {
  traces: '#0f62fe',
  success: '#24a148',
  severityWarning: '#f1c21b',
  severityError: '#ff832b',
  severityCritical: '#da1e28',
  issueTypes: ['#4589ff', '#0f62fe', '#0043ce', '#002d9c', '#001d6c'],
};

// Helper function to format date to YYYY-MM-DD
const formatDateForInput = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Helper function to format date to ISO string for API
const formatDateForAPI = (dateString) => {
  const date = new Date(dateString);
  return date.toISOString();
};

const TenantAnalyticsDashboard = () => {
  // Initialize default dates: end = tomorrow, start = 7 days back
  const getDefaultDates = () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    return {
      start: formatDateForInput(sevenDaysAgo),
      end: formatDateForInput(tomorrow),
    };
  };

  const [activeTab, setActiveTab] = useState('overview');
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedTenant, setSelectedTenant] = useState('');
  const [error, setError] = useState(null);
  const [dateRange, setDateRange] = useState(getDefaultDates());
  const [dateError, setDateError] = useState('');

  useEffect(() => {
    fetchAnalyticsData();
  }, [dateRange]);

  const fetchAnalyticsData = async () => {
    try {
      setLoading(true);
      const startDate = formatDateForAPI(dateRange.start);
      const endDate = formatDateForAPI(dateRange.end);
      const url = `/api/v1/admin/tenant-stats?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;

      // Get admin API key from localStorage
      const adminApiKey = localStorage.getItem('adminApiKey');

      const headers = {};
      if (adminApiKey) {
        headers['X-API-Key'] = adminApiKey;
      }

      const response = await fetch(url, { headers });
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Unauthorized: Admin API key required or invalid');
        }
        throw new Error('Failed to fetch analytics data');
      }
      const data = await response.json();
      setAnalyticsData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDateChange = (field, value) => {
    const newDateRange = { ...dateRange, [field]: value };

    // Validate date range
    const start = new Date(newDateRange.start);
    const end = new Date(newDateRange.end);
    const diffTime = Math.abs(end - start);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (start > end) {
      setDateError('Start date must be before end date');
      return;
    }

    if (diffDays > 30) {
      setDateError('Date range cannot exceed 30 days');
      return;
    }

    setDateError('');
    setDateRange(newDateRange);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 p-8">
        <div className="bg-white border border-red-200 rounded-lg p-6 max-w-md w-full">
          <div className="text-red-600 font-semibold mb-4">Error: {error}</div>
          {error.includes('Unauthorized') && (
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Admin API Key
              </label>
              <input
                type="password"
                placeholder="Enter your admin API key"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    localStorage.setItem('adminApiKey', e.target.value);
                    window.location.reload();
                  }
                }}
              />
              <button
                onClick={(e) => {
                  const input = e.target.previousElementSibling;
                  localStorage.setItem('adminApiKey', input.value);
                  window.location.reload();
                }}
                className="mt-3 w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Save and Retry
              </button>
              <p className="text-xs text-gray-500 mt-2">
                Your API key will be stored in browser localStorage
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (!analyticsData) return null;

  const tenantIds = Object.keys(analyticsData.tenants);
  const tenants = analyticsData.tenants;
  const totals = analyticsData.totals;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gray-900 text-white px-8 py-4 shadow-md">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-normal tracking-wide text-white">Tenant Analytics Dashboard</h1>
          </div>

          {/* Date Range Selector */}
          <div className="flex items-center gap-4">
            <div className="flex flex-col">
              <label className="text-xs text-gray-300 mb-1 font-medium">Start Date</label>
              <input
                type="date"
                value={dateRange.start}
                onChange={(e) => handleDateChange('start', e.target.value)}
                className="px-3 py-2 text-sm bg-gray-700 border border-gray-600 text-white rounded focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-xs text-gray-300 mb-1 font-medium">End Date</label>
              <input
                type="date"
                value={dateRange.end}
                onChange={(e) => handleDateChange('end', e.target.value)}
                className="px-3 py-2 text-sm bg-gray-700 border border-gray-600 text-white rounded focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
              />
            </div>
          </div>
        </div>

        {/* Date Error Message */}
        {dateError && (
          <div className="mt-3 px-4 py-2 bg-red-900 bg-opacity-50 border border-red-700 rounded text-sm text-red-200">
            {dateError}
          </div>
        )}
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white border-b border-gray-200 px-8">
        <div className="flex gap-0">
          {[
            { id: 'overview', label: 'Overview' },
            { id: 'tenants', label: 'Tenant Comparison' },
            { id: 'details', label: 'Tenant Details' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-4 text-sm font-normal border-b-2 transition-all ${
                activeTab === tab.id
                  ? 'text-gray-900 border-blue-600'
                  : 'text-gray-600 border-transparent hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-8 py-8">
        {activeTab === 'overview' && (
          <OverviewTab totals={totals} />
        )}
        {activeTab === 'tenants' && (
          <TenantComparisonTab tenantIds={tenantIds} tenants={tenants} totals={totals} />
        )}
        {activeTab === 'details' && (
          <TenantDetailsTab
            tenantIds={tenantIds}
            tenants={tenants}
            selectedTenant={selectedTenant}
            setSelectedTenant={setSelectedTenant}
          />
        )}
      </div>
    </div>
  );
};

// Overview Tab Component
const OverviewTab = ({ totals }) => {
  // Combined Traces & Success Rate Chart Data
  const dates = Object.keys(totals.traces.daily).sort();
  const traceValues = dates.map((date) => totals.traces.daily[date]);
  const successRates = dates.map((date) => {
    const totalTraces = totals.traces.daily[date] || 0;
    const issues = totals.issues.daily[date] || 0;
    return totalTraces > 0 ? ((totalTraces - issues) / totalTraces) * 100 : 100;
  });

  const combinedChartData = {
    labels: dates,
    datasets: [
      {
        label: 'Traces',
        data: traceValues,
        backgroundColor: COLORS.traces,
        borderWidth: 0,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
        yAxisID: 'y-traces',
        type: 'bar',
      },
      {
        label: 'Success Rate (%)',
        data: successRates,
        borderColor: COLORS.success,
        backgroundColor: COLORS.success + '20',
        borderWidth: 2,
        fill: false,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: COLORS.success,
        yAxisID: 'y-success',
        type: 'line',
      },
    ],
  };

  const combinedChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { display: true, position: 'bottom' } },
    scales: {
      'y-traces': {
        type: 'linear',
        position: 'left',
        beginAtZero: true,
        title: { display: true, text: 'Traces' },
        grid: { color: '#e0e0e0' },
      },
      'y-success': {
        type: 'linear',
        position: 'right',
        min: 90,
        max: 100,
        title: { display: true, text: 'Success Rate (%)' },
        grid: { drawOnChartArea: false },
      },
      x: { grid: { display: false } },
    },
  };

  // Issues by Type Chart Data
  const issueTypes = Object.keys(totals.issues.by_plugin_metadata_id || {});
  const issueCounts = Object.values(totals.issues.by_plugin_metadata_id || {});
  const issuesTypeData = {
    labels: issueTypes.map((t) => t.replace(/_/g, ' ')),
    datasets: [
      {
        data: issueCounts,
        backgroundColor: COLORS.issueTypes.slice(0, issueTypes.length),
        borderWidth: 0,
      },
    ],
  };

  // Issues by Severity Chart Data
  const severityOrder = ['warning', 'error', 'critical'];
  const severities = Object.keys(totals.issues.by_level || {}).sort(
    (a, b) => severityOrder.indexOf(a) - severityOrder.indexOf(b)
  );
  const severityCounts = severities.map((s) => totals.issues.by_level[s]);
  const severityColors = severities.map((s) => {
    const colorMap = {
      warning: COLORS.severityWarning,
      error: COLORS.severityError,
      critical: COLORS.severityCritical,
    };
    return colorMap[s] || COLORS.severityError;
  });

  const issuesSeverityData = {
    labels: severities.map((s) => s.charAt(0).toUpperCase() + s.slice(1)),
    datasets: [
      {
        label: 'Issues',
        data: severityCounts,
        backgroundColor: severityColors,
        borderWidth: 0,
        barPercentage: 0.5,
        categoryPercentage: 0.8,
      },
    ],
  };

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, grid: { color: '#e0e0e0' } },
      x: { grid: { display: false } },
    },
  };

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { position: 'bottom' } },
  };

  return (
    <div>
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KPICard
          label="Total Traces"
          value={totals.traces.total.toLocaleString()}
          subtitle="Across all tenants"
        />
        <KPICard
          label="Success Rate"
          value={totals.trace_success_metrics.success_rate.toFixed(1) + '%'}
          subtitle="Traces without issues"
        />
        <KPICard
          label="Total Issues"
          value={totals.issues.total.toLocaleString()}
          subtitle="Across all traces"
        />
        <KPICard
          label="Avg Spans/Trace"
          value={totals.spans.avg_spans_per_trace.toFixed(1)}
          subtitle="System complexity"
        />
      </div>

      {/* Combined Chart */}
      <div className="bg-white border border-gray-200 p-6 mb-4 min-h-[400px]">
        <h3 className="text-lg font-normal mb-4 text-gray-900">Traces & Success Rate Over Time</h3>
        <Bar data={combinedChartData} options={combinedChartOptions} />
      </div>

      {/* Issues Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Issues by Type</h3>
          {issueTypes.length > 0 ? (
            <Doughnut data={issuesTypeData} options={doughnutOptions} />
          ) : (
            <div className="text-gray-600 text-center py-8">No issue data available</div>
          )}
        </div>
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Issues by Severity</h3>
          {severities.length > 0 ? (
            <Bar data={issuesSeverityData} options={barChartOptions} />
          ) : (
            <div className="text-gray-600 text-center py-8">No severity data available</div>
          )}
        </div>
      </div>
    </div>
  );
};

// Tenant Comparison Tab Component
const TenantComparisonTab = ({ tenantIds, tenants, totals }) => {
  const tenantNames = tenantIds.map((id) => tenants[id].name || id);
  const tenantTraces = tenantIds.map((id) => tenants[id].traces.total);
  const tenantColors = tenantIds.map((id) => TENANT_COLOR_MAP[id] || COLORS.traces);
  const tenantSuccessRates = tenantIds.map((id) => tenants[id].trace_success_metrics.success_rate);

  const tracesChartData = {
    labels: tenantNames,
    datasets: [
      {
        label: 'Total Traces',
        data: tenantTraces,
        backgroundColor: tenantColors,
        borderWidth: 0,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
      },
    ],
  };

  const successChartData = {
    labels: tenantNames,
    datasets: [
      {
        label: 'Success Rate (%)',
        data: tenantSuccessRates,
        backgroundColor: tenantColors,
        borderWidth: 0,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
      },
    ],
  };

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, grid: { color: '#e0e0e0' } },
      x: { grid: { display: false } },
    },
  };

  const successChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: false, min: 90, max: 100, grid: { color: '#e0e0e0' } },
      x: { grid: { display: false } },
    },
  };

  // Daily Activity by Tenant
  const allDates = Object.keys(totals.traces.daily).sort();
  const dailyDatasets = tenantIds.map((id) => {
    const tenant = tenants[id];
    const color = TENANT_COLOR_MAP[id] || COLORS.traces;
    return {
      label: tenant.name || id,
      data: allDates.map((date) => tenant.traces.daily[date] || 0),
      borderColor: color,
      backgroundColor: color + '15',
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 3,
      pointBackgroundColor: color,
    };
  });

  const dailyChartData = {
    labels: allDates,
    datasets: dailyDatasets,
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { position: 'bottom' } },
    scales: {
      y: { beginAtZero: true, grid: { color: '#e0e0e0' } },
      x: { grid: { display: false } },
    },
  };

  return (
    <div>
      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Traces by Tenant</h3>
          <Bar data={tracesChartData} options={barChartOptions} />
        </div>
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Success Rate by Tenant</h3>
          <Bar data={successChartData} options={successChartOptions} />
        </div>
      </div>

      {/* Comparison Table */}
      <div className="bg-white border border-gray-200 mb-4">
        <div className="p-6">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Tenant Comparison Table</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead className="bg-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900 border-b border-gray-300">
                  Tenant
                </th>
                <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900 border-b border-gray-300">
                  Traces
                </th>
                <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900 border-b border-gray-300">
                  Issues
                </th>
                <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900 border-b border-gray-300">
                  Success Rate
                </th>
                <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900 border-b border-gray-300">
                  Avg Spans/Trace
                </th>
                <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900 border-b border-gray-300">
                  Tasks
                </th>
              </tr>
            </thead>
            <tbody>
              {tenantIds.map((id) => {
                const tenant = tenants[id];
                const successRate = tenant.trace_success_metrics.success_rate;
                const badgeClass =
                  successRate >= 98
                    ? 'bg-green-100 text-green-800'
                    : successRate >= 95
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-red-100 text-red-800';

                return (
                  <tr key={id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900 border-b border-gray-200">
                      <strong>{tenant.name || id}</strong>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 border-b border-gray-200">
                      {tenant.traces.total.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 border-b border-gray-200">
                      {tenant.issues.total.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 border-b border-gray-200">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${badgeClass}`}
                      >
                        {successRate.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 border-b border-gray-200">
                      {tenant.spans.avg_spans_per_trace.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 border-b border-gray-200">
                      {tenant.tasks.total.toLocaleString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Daily Activity */}
      <div className="bg-white border border-gray-200 p-6">
        <h3 className="text-lg font-normal mb-4 text-gray-900">Daily Activity by Tenant</h3>
        <Line data={dailyChartData} options={lineChartOptions} />
      </div>
    </div>
  );
};

// Tenant Details Tab Component
const TenantDetailsTab = ({ tenantIds, tenants, selectedTenant, setSelectedTenant }) => {
  if (!selectedTenant || !tenants[selectedTenant]) {
    return (
      <div>
        <div className="mb-8">
          <label className="block text-xs uppercase tracking-wide text-gray-600 mb-2">
            Select Tenant
          </label>
          <select
            value={selectedTenant}
            onChange={(e) => setSelectedTenant(e.target.value)}
            className="w-full max-w-md px-3 py-2 text-sm bg-gray-100 border-b border-gray-500 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-0"
          >
            <option value="">-- Select a tenant --</option>
            {tenantIds.map((id) => (
              <option key={id} value={id}>
                {tenants[id].name || id}
              </option>
            ))}
          </select>
        </div>
      </div>
    );
  }

  const tenant = tenants[selectedTenant];
  const tenantColor = TENANT_COLOR_MAP[selectedTenant] || COLORS.traces;
  const issueRate = ((tenant.issues.total / tenant.traces.total) * 100).toFixed(2);

  // Daily Traces Chart
  const dates = Object.keys(tenant.traces.daily).sort();
  const traceValues = dates.map((date) => tenant.traces.daily[date]);

  const tracesTimelineData = {
    labels: dates,
    datasets: [
      {
        label: 'Traces',
        data: traceValues,
        backgroundColor: tenantColor,
        borderWidth: 0,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
      },
    ],
  };

  // Spans per Trace Trend
  const spansDates = Object.keys(tenant.spans.daily_avg_spans_per_trace).sort();
  const spansAvg = spansDates.map((date) => tenant.spans.daily_avg_spans_per_trace[date]);

  const spansTrendData = {
    labels: spansDates,
    datasets: [
      {
        label: 'Avg Spans per Trace',
        data: spansAvg,
        borderColor: tenantColor,
        backgroundColor: tenantColor + '15',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: tenantColor,
      },
    ],
  };

  // Daily Issues
  const issuesDates = Object.keys(tenant.issues.daily).sort();
  const issuesValues = issuesDates.map((date) => tenant.issues.daily[date]);

  const issuesTimelineData = {
    labels: issuesDates,
    datasets: [
      {
        label: 'Issues',
        data: issuesValues,
        backgroundColor: COLORS.severityError,
        borderWidth: 0,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
      },
    ],
  };

  // Issues by Type
  const issueTypes = Object.keys(tenant.issues.by_plugin_metadata_id || {});
  const issueCounts = Object.values(tenant.issues.by_plugin_metadata_id || {});

  const issuesTypeData = {
    labels: issueTypes.map((t) => t.replace(/_/g, ' ')),
    datasets: [
      {
        data: issueCounts,
        backgroundColor: COLORS.issueTypes.slice(0, issueTypes.length),
        borderWidth: 0,
      },
    ],
  };

  // Issues by Severity
  const severityOrder = ['warning', 'error', 'critical'];
  const severities = Object.keys(tenant.issues.by_level || {}).sort(
    (a, b) => severityOrder.indexOf(a) - severityOrder.indexOf(b)
  );
  const severityCounts = severities.map((s) => tenant.issues.by_level[s]);
  const severityColors = severities.map((s) => {
    const colorMap = {
      warning: COLORS.severityWarning,
      error: COLORS.severityError,
      critical: COLORS.severityCritical,
    };
    return colorMap[s] || COLORS.severityError;
  });

  const issuesSeverityData = {
    labels: severities.map((s) => s.charAt(0).toUpperCase() + s.slice(1)),
    datasets: [
      {
        label: 'Issues',
        data: severityCounts,
        backgroundColor: severityColors,
        borderWidth: 0,
        barPercentage: 0.5,
        categoryPercentage: 0.8,
      },
    ],
  };

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, grid: { color: '#e0e0e0' } },
      x: { grid: { display: false } },
    },
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, grid: { color: '#e0e0e0' } },
      x: { grid: { display: false } },
    },
  };

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { position: 'bottom' } },
  };

  return (
    <div>
      {/* Tenant Selector */}
      <div className="mb-8">
        <label className="block text-xs uppercase tracking-wide text-gray-600 mb-2">
          Select Tenant
        </label>
        <select
          value={selectedTenant}
          onChange={(e) => setSelectedTenant(e.target.value)}
          className="w-full max-w-md px-3 py-2 text-sm bg-gray-100 border-b border-gray-500 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-0"
        >
          <option value="">-- Select a tenant --</option>
          {tenantIds.map((id) => (
            <option key={id} value={id}>
              {tenants[id].name || id}
            </option>
          ))}
        </select>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KPICard
          label="Traces"
          value={tenant.traces.total.toLocaleString()}
          subtitle={tenant.name || selectedTenant}
        />
        <KPICard
          label="Success Rate"
          value={tenant.trace_success_metrics.success_rate.toFixed(1) + '%'}
          subtitle={`${tenant.trace_success_metrics.traces_without_issues.toLocaleString()} successful traces`}
        />
        <KPICard
          label="Issues"
          value={tenant.issues.total.toLocaleString()}
          subtitle={`${issueRate}% issue rate`}
        />
        <KPICard
          label="Avg Spans/Trace"
          value={tenant.spans.avg_spans_per_trace.toFixed(1)}
          subtitle={`${tenant.spans.total.toLocaleString()} total spans`}
        />
      </div>

      {/* Daily Traces */}
      <div className="bg-white border border-gray-200 p-6 mb-4">
        <h3 className="text-lg font-normal mb-4 text-gray-900">Daily Traces</h3>
        <Bar data={tracesTimelineData} options={barChartOptions} />
      </div>

      {/* Spans & Issues */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Spans per Trace Trend</h3>
          <Line data={spansTrendData} options={lineChartOptions} />
        </div>
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Daily Issues</h3>
          {issuesDates.length > 0 ? (
            <Bar data={issuesTimelineData} options={barChartOptions} />
          ) : (
            <div className="text-gray-600 text-center py-8">No issue data available</div>
          )}
        </div>
      </div>

      {/* Issue Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Issues by Type</h3>
          {issueTypes.length > 0 ? (
            <Doughnut data={issuesTypeData} options={doughnutOptions} />
          ) : (
            <div className="text-gray-600 text-center py-8">No issue data available</div>
          )}
        </div>
        <div className="bg-white border border-gray-200 p-6 min-h-[400px]">
          <h3 className="text-lg font-normal mb-4 text-gray-900">Issues by Severity</h3>
          {severities.length > 0 ? (
            <Bar data={issuesSeverityData} options={barChartOptions} />
          ) : (
            <div className="text-gray-600 text-center py-8">No severity data available</div>
          )}
        </div>
      </div>
    </div>
  );
};

// KPI Card Component
const KPICard = ({ label, value, subtitle }) => (
  <div className="bg-white border border-gray-200 p-6 hover:shadow-md transition-shadow">
    <div className="text-xs uppercase tracking-wide text-gray-600 mb-2">{label}</div>
    <div className="text-3xl font-light text-gray-900 mb-1">{value}</div>
    <div className="text-sm text-gray-600">{subtitle}</div>
  </div>
);

export default TenantAnalyticsDashboard;
