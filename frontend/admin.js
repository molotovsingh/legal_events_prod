/**
 * Legal Events - Admin Settings
 * Developer interface for provider/model configuration
 */

// API configuration
const API_URL = (() => {
    try {
        const base = (typeof window !== 'undefined' && typeof window.API_BASE_URL === 'string')
            ? window.API_BASE_URL.trim().replace(/\/$/, '')
            : '';
        return base;
    } catch (_) {
        return '';
    }
})();

// Auth state
let authToken = localStorage.getItem('jwt_token');

// Configure axios
axios.defaults.timeout = 30000;
axios.interceptors.request.use(config => {
    if (authToken) config.headers.Authorization = `Bearer ${authToken}`;
    return config;
});

axios.interceptors.response.use(
    response => response,
    error => {
        if (error.response && error.response.status === 401) {
            handleLogout();
            showLoginModal();
        }
        return Promise.reject(error);
    }
);

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    loadSavedModelSelection();
    await checkAuthStatus();
    await loadProviders();
    await loadModeMappings();
    await loadProviderStatus();
    await loadSystemHealth();
});

// ============================================================================
// Model Selection Persistence
// ============================================================================

function loadSavedModelSelection() {
    const savedModel = localStorage.getItem('extraction_model') || 'anthropic/claude-sonnet-4.5';
    const savedDocExtractor = localStorage.getItem('doc_extractor') || 'docling';

    const modelSelect = document.getElementById('extractionModel');
    const docExtractorSelect = document.getElementById('docExtractorSelect');

    if (modelSelect) {
        modelSelect.value = savedModel;
    }
    if (docExtractorSelect) {
        docExtractorSelect.value = savedDocExtractor;
    }

    updateModelStatus(savedModel);
}

function updateModelStatus(model) {
    const statusEl = document.getElementById('modelStatus');
    if (statusEl) {
        statusEl.textContent = `Current: ${model}`;
    }
}

function saveModelSelection() {
    const modelSelect = document.getElementById('extractionModel');
    const docExtractorSelect = document.getElementById('docExtractorSelect');

    if (modelSelect) {
        const model = modelSelect.value;
        localStorage.setItem('extraction_model', model);
        updateModelStatus(model);
    }
    if (docExtractorSelect) {
        localStorage.setItem('doc_extractor', docExtractorSelect.value);
    }

    showToast('Model selection saved');
}

function showToast(message) {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg z-50 fade-in';
    toast.textContent = message;
    document.body.appendChild(toast);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function setupEventListeners() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    const providerSelect = document.getElementById('providerSelect');
    if (providerSelect) {
        providerSelect.addEventListener('change', (e) => loadModels(e.target.value));
    }

    // Model selection save button
    const saveModelBtn = document.getElementById('saveModelBtn');
    if (saveModelBtn) {
        saveModelBtn.addEventListener('click', saveModelSelection);
    }

    // Update status on model change
    const extractionModel = document.getElementById('extractionModel');
    if (extractionModel) {
        extractionModel.addEventListener('change', (e) => {
            updateModelStatus(e.target.value);
        });
    }
}

// ============================================================================
// Authentication
// ============================================================================

async function checkAuthStatus() {
    if (!authToken) {
        showLoginModal();
        return;
    }
    try {
        const response = await axios.get(`${API_URL}/v1/auth/me`);
        updateAuthUI(true, response.data);
    } catch (error) {
        console.error('Auth check failed:', error);
        showLoginModal();
    }
}

function showLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.remove('hidden');
}

function hideLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.add('hidden');
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail')?.value;
    const password = document.getElementById('loginPassword')?.value;
    const errorEl = document.getElementById('loginError');

    if (!email || !password) {
        if (errorEl) {
            errorEl.textContent = 'Please enter email and password';
            errorEl.classList.remove('hidden');
        }
        return;
    }

    try {
        const response = await axios.post(`${API_URL}/v1/auth/login`, { email, password });
        authToken = response.data.access_token;
        localStorage.setItem('jwt_token', authToken);
        hideLoginModal();
        updateAuthUI(true, response.data.user);
        // Reload data
        await loadProviders();
        await loadModeMappings();
        await loadProviderStatus();
        await loadSystemHealth();
    } catch (error) {
        console.error('Login failed:', error);
        if (errorEl) {
            errorEl.textContent = error.response?.data?.detail || 'Login failed';
            errorEl.classList.remove('hidden');
        }
    }
}

function handleLogout() {
    authToken = null;
    localStorage.removeItem('jwt_token');
    location.reload();
}

function updateAuthUI(loggedIn, user = null) {
    const section = document.getElementById('authSection');
    if (!section) return;

    if (loggedIn && user) {
        section.innerHTML = `
            <div class="flex items-center space-x-3">
                <span class="text-sm text-gray-600">${escapeHtml(user.email || user.name || 'Admin')}</span>
                <button onclick="handleLogout()" class="text-sm text-red-600 hover:text-red-800">Logout</button>
            </div>
        `;
    } else {
        section.innerHTML = `
            <button onclick="showLoginModal()" class="text-sm text-blue-600 hover:text-blue-800">Login</button>
        `;
    }
}

// ============================================================================
// Provider & Model Loading
// ============================================================================

async function loadProviders() {
    const select = document.getElementById('providerSelect');
    if (!select) return;

    try {
        const response = await axios.get(`${API_URL}/v1/providers`);
        select.innerHTML = '';

        response.data.providers.forEach(p => {
            const option = document.createElement('option');
            option.value = p.provider_id;
            option.textContent = `${p.display_name}${p.recommended ? ' (Recommended)' : ''}`;
            option.disabled = !p.enabled;
            select.appendChild(option);
        });

        // Select first enabled provider and load its models
        const firstEnabled = response.data.providers.find(p => p.enabled);
        if (firstEnabled) {
            select.value = firstEnabled.provider_id;
            await loadModels(firstEnabled.provider_id);
        }
    } catch (error) {
        console.error('Failed to load providers:', error);
        select.innerHTML = '<option value="">Failed to load providers</option>';
    }
}

async function loadModels(providerId) {
    const select = document.getElementById('modelSelect');
    if (!select || !providerId) return;

    try {
        const response = await axios.get(`${API_URL}/v1/models?provider=${providerId}`);
        select.innerHTML = '';

        if (response.data.models?.length > 0) {
            response.data.models.forEach(m => {
                const option = document.createElement('option');
                option.value = m.model_id;
                const cost = m.cost_input_per_million ? `$${m.cost_input_per_million}/M` : '';
                option.textContent = `${m.display_name} ${cost}${m.is_recommended ? ' (Recommended)' : ''}`;
                if (m.is_recommended) option.selected = true;
                select.appendChild(option);
            });
        } else {
            select.innerHTML = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Failed to load models:', error);
        select.innerHTML = '<option value="">Failed to load models</option>';
    }
}

// ============================================================================
// Mode Mappings
// ============================================================================

const MODE_ICONS = {
    'star': '⭐',
    'scales': '⚖️',
    'bolt': '⚡',
    'dollar': '💰'
};

async function loadModeMappings() {
    const container = document.getElementById('modeMappings');
    if (!container) return;

    try {
        const modesResponse = await axios.get(`${API_URL}/v1/modes`);
        container.innerHTML = '';

        for (const mode of modesResponse.data.modes) {
            // Get full mode details including provider/model
            const detailResp = await axios.get(`${API_URL}/v1/modes/${mode.id}`);
            const detail = detailResp.data;

            const icon = MODE_ICONS[mode.icon] || '📄';
            const card = document.createElement('div');
            card.className = 'mode-mapping-card p-4';
            card.innerHTML = `
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center">
                        <span class="text-xl mr-2">${icon}</span>
                        <span class="font-semibold text-gray-900">${escapeHtml(mode.name)}</span>
                    </div>
                    <span class="text-xs text-gray-500 bg-gray-200 px-2 py-1 rounded">${escapeHtml(mode.id)}</span>
                </div>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between">
                        <span class="text-gray-500">Provider:</span>
                        <span class="font-medium text-gray-900">${escapeHtml(detail.provider)}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-gray-500">Model:</span>
                        <span class="font-medium text-gray-900 text-xs">${escapeHtml(detail.model)}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-gray-500">OCR:</span>
                        <span class="font-medium text-gray-900">${escapeHtml(detail.doc_extractor)}</span>
                    </div>
                </div>
                <div class="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
                    ${escapeHtml(mode.estimated_speed)}
                </div>
            `;
            container.appendChild(card);
        }
    } catch (error) {
        console.error('Failed to load mode mappings:', error);
        container.innerHTML = '<div class="text-red-500 text-sm col-span-full">Failed to load mode mappings</div>';
    }
}

// ============================================================================
// Provider Status
// ============================================================================

async function loadProviderStatus() {
    const container = document.getElementById('providerStatus');
    if (!container) return;

    try {
        const response = await axios.get(`${API_URL}/v1/providers`);
        container.innerHTML = '';

        response.data.providers.forEach(p => {
            const isWorking = p.is_working && p.enabled;
            const card = document.createElement('div');
            card.className = `provider-card p-4 rounded-lg border ${isWorking ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`;
            card.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <span class="font-medium text-gray-900">${escapeHtml(p.display_name)}</span>
                    <span class="text-xs px-2 py-1 rounded-full ${isWorking ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}">
                        ${isWorking ? 'Active' : 'Inactive'}
                    </span>
                </div>
                <div class="text-xs text-gray-500">${escapeHtml(p.notes || 'No description')}</div>
                ${p.documentation_url ? `<a href="${escapeHtml(p.documentation_url)}" target="_blank" class="text-xs text-blue-600 hover:underline mt-2 inline-block">Documentation →</a>` : ''}
            `;
            container.appendChild(card);
        });
    } catch (error) {
        console.error('Failed to load provider status:', error);
        container.innerHTML = '<div class="text-red-500 text-sm col-span-full">Failed to load provider status</div>';
    }
}

// ============================================================================
// System Health
// ============================================================================

async function loadSystemHealth() {
    const container = document.getElementById('systemHealth');
    if (!container) return;

    try {
        const response = await axios.get(`${API_URL}/health`);
        const health = response.data;

        const statusColors = {
            'healthy': 'status-healthy',
            'degraded': 'status-degraded',
            'unhealthy': 'status-unhealthy'
        };

        container.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center">
                    <span class="text-lg mr-2">${health.status === 'healthy' ? '✅' : health.status === 'degraded' ? '⚠️' : '❌'}</span>
                    <span class="font-semibold text-gray-900">Overall: ${health.status.charAt(0).toUpperCase() + health.status.slice(1)}</span>
                </div>
                <span class="text-xs text-gray-500">${new Date(health.timestamp).toLocaleString()}</span>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                ${Object.entries(health.components).map(([name, status]) => `
                    <div class="p-3 rounded-lg ${statusColors[status] || 'bg-gray-100'}">
                        <div class="text-sm font-medium capitalize">${escapeHtml(name)}</div>
                        <div class="text-xs capitalize">${escapeHtml(status)}</div>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (error) {
        console.error('Failed to load system health:', error);
        container.innerHTML = '<div class="text-red-500 text-sm">Failed to load system health</div>';
    }
}

// ============================================================================
// Utilities
// ============================================================================

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
