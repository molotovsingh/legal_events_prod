// API configuration
// Derive dynamically to avoid CORS issues across localhost/127.0.0.1/incognito
const API_URL = (() => {
    try {
        const base = (typeof window !== 'undefined' && typeof window.API_BASE_URL === 'string')
            ? window.API_BASE_URL.trim().replace(/\/$/, '')
            : '';
        // Prefer relative base by default for same-origin; allows absolute override via config.js
        return base; // '' means use relative paths like '/v1/...'
    } catch (e) {
        return '';
    }
})();

// Apply axios baseURL for consistency
try { axios.defaults.baseURL = API_URL || undefined; } catch (_) {}

// Debug badge to show resolved API URL and allow quick copy
function renderApiBadge() {
    try {
        const container = document.getElementById('apiBadge');
        if (!container) return;
        container.textContent = '';

        const badge = document.createElement('span');
        badge.className = 'bg-gray-100 text-gray-700 px-2 py-1 rounded border border-gray-200';
        badge.textContent = `API: ${API_URL || 'same-origin'}`;

        const copyBtn = document.createElement('button');
        copyBtn.className = 'ml-2 text-blue-600 hover:underline';
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(API_URL || window.location.origin);
                copyBtn.textContent = 'Copied!';
                setTimeout(() => (copyBtn.textContent = 'Copy'), 1000);
            } catch (e) {
                // Fallback
                const tmp = document.createElement('input');
                tmp.value = API_URL;
                document.body.appendChild(tmp);
                tmp.select();
                document.execCommand('copy');
                document.body.removeChild(tmp);
                copyBtn.textContent = 'Copied!';
                setTimeout(() => (copyBtn.textContent = 'Copy'), 1000);
            }
        });

        container.appendChild(badge);
        container.appendChild(copyBtn);
    } catch (_) { /* no-op */ }
}

// Initialize DOMPurify with safe configuration
const purifyConfig = {
    ALLOWED_TAGS: ['span', 'div', 'p', 'button', 'table', 'thead', 'tbody', 'tr', 'td', 'th'],
    ALLOWED_ATTR: ['class', 'data-run-id', 'data-case-id'],
    KEEP_CONTENT: true
};

// Authentication state
let authToken = localStorage.getItem('jwt_token');
let currentUser = null;

// Current run tracking for exports
let currentRunId = null;

// Configure axios to include auth token
axios.interceptors.request.use(
    config => {
        if (authToken) {
            config.headers.Authorization = `Bearer ${authToken}`;
        }
        return config;
    },
    error => Promise.reject(error)
);

// Handle 401 responses globally
axios.interceptors.response.use(
    response => response,
    error => {
        if (error.response && error.response.status === 401) {
            // Token expired or invalid
            handleLogout();
            showLoginModal();
        }
        return Promise.reject(error);
    }
);

// Helper function to safely set text content
function safeSetText(elementId, text) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = text;
    }
}

// Helper function to safely create element with text
function createTextElement(tag, text, className = '') {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) {
        element.className = className;
    }
    return element;
}

// Authentication functions
function showLoginModal() {
    const modal = document.getElementById('loginModal');
    modal.classList.remove('hidden');
}

function hideLoginModal() {
    const modal = document.getElementById('loginModal');
    modal.classList.add('hidden');
}

async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');

    // Clear previous errors
    errorDiv.classList.add('hidden');
    errorDiv.textContent = '';

    if (!email || !password) {
        errorDiv.textContent = '⚠️ Please enter both email and password';
        errorDiv.classList.remove('hidden');
        return;
    }

    try {
        const response = await axios.post(`${API_URL}/v1/auth/login`, {
            email: email,
            password: password
        });

        authToken = response.data.access_token;
        localStorage.setItem('jwt_token', authToken);

        // Decode token to get user info (optional)
        currentUser = response.data.user || { email: email };

        hideLoginModal();
        updateAuthUI();

        // Refresh the page data
        checkHealth();
        loadRuns();

    } catch (error) {
        let errorMsg = '❌ Login failed. Please try again.';
        
        if (error.response) {
            // Server responded with error
            if (error.response.status === 401) {
                errorMsg = error.response.data.detail || '❌ Invalid email or password';
            } else if (error.response.status === 403) {
                errorMsg = '🚫 Account is disabled. Contact your administrator.';
            } else {
                errorMsg = '❌ Server error: ' + (error.response.data.detail || error.response.statusText);
            }
        } else if (error.request) {
            // No response from server
            errorMsg = '🔌 Cannot connect to server. Please check if the API is running at ' + API_URL;
        }
        
        errorDiv.textContent = errorMsg;
        errorDiv.classList.remove('hidden');
        
        console.error('Login error:', error);
    }
}

function handleLogout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('jwt_token');
    updateAuthUI();
}

function updateAuthUI() {
    const authSection = document.getElementById('authSection');
    const mainContent = document.getElementById('mainContent');

    if (authToken) {
        // User is logged in
        authSection.innerHTML = '';
        const logoutBtn = document.createElement('button');
        logoutBtn.className = 'bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600';
        logoutBtn.textContent = 'Logout';
        logoutBtn.addEventListener('click', handleLogout);
        authSection.appendChild(logoutBtn);

        if (currentUser && currentUser.email) {
            const userSpan = createTextElement('span', `Logged in as: ${currentUser.email}`, 'mr-4');
            authSection.insertBefore(userSpan, logoutBtn);
        }

        mainContent.classList.remove('opacity-50', 'pointer-events-none');
    } else {
        // User is not logged in
        authSection.innerHTML = '';
        const loginBtn = document.createElement('button');
        loginBtn.className = 'bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600';
        loginBtn.textContent = 'Login';
        loginBtn.addEventListener('click', showLoginModal);
        authSection.appendChild(loginBtn);

        mainContent.classList.add('opacity-50', 'pointer-events-none');
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    renderApiBadge();
    updateAuthUI();
    checkHealth();
    loadProviders();
    loadRuns();
    setupEventListeners();

    // Check if we need to show login immediately
    if (!authToken) {
        showLoginModal();
    }
});

function setupEventListeners() {
    // Use addEventListener instead of onclick attributes
    const createClientBtn = document.getElementById('createClientBtn');
    if (createClientBtn) {
        createClientBtn.addEventListener('click', createClient);
    }

    const createCaseBtn = document.getElementById('createCaseBtn');
    if (createCaseBtn) {
        createCaseBtn.addEventListener('click', createCase);
    }

    const startRunBtn = document.getElementById('startRunBtn');
    if (startRunBtn) {
        startRunBtn.addEventListener('click', startRun);
    }

    const refreshRunsBtn = document.getElementById('refreshRunsBtn');
    if (refreshRunsBtn) {
        refreshRunsBtn.addEventListener('click', () => loadRuns());
    }

    const providerSelect = document.getElementById('providerSelect');
    if (providerSelect) {
        providerSelect.addEventListener('change', function(e) {
            loadModels(e.target.value);
        });
    }

    // Login modal events
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) {
        loginBtn.addEventListener('click', handleLogin);
    }

    const cancelLoginBtn = document.getElementById('cancelLoginBtn');
    if (cancelLoginBtn) {
        cancelLoginBtn.addEventListener('click', hideLoginModal);
    }

    // Allow Enter key in password field
    const loginPassword = document.getElementById('loginPassword');
    if (loginPassword) {
        loginPassword.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                handleLogin();
            }
        });
    }

    // Export button events
    const exportCsvBtn = document.getElementById('exportCsvBtn');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', () => exportEvents('csv'));
    }

    const exportXlsxBtn = document.getElementById('exportXlsxBtn');
    if (exportXlsxBtn) {
        exportXlsxBtn.addEventListener('click', () => exportEvents('xlsx'));
    }

    const exportJsonBtn = document.getElementById('exportJsonBtn');
    if (exportJsonBtn) {
        exportJsonBtn.addEventListener('click', () => exportEvents('json'));
    }
}

async function loadProviders() {
    const select = document.getElementById('providerSelect');
    select.textContent = ''; // Clear existing options

    try {
        const response = await axios.get(`${API_URL}/v1/providers`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const providers = response.data.providers;

        // Helper function to calculate status from API fields
        const getStatus = (provider) => {
            if (!provider.enabled) return 'disabled';
            return provider.is_working ? 'available' : 'unavailable';
        };

        // Find openrouter provider (standardized default v0.11.0+)
        const openrouter = providers.find(p => p.provider_id === 'openrouter');
        const others = providers.filter(p => p.provider_id !== 'openrouter');

        if (openrouter && getStatus(openrouter) === 'available') {
            const option = document.createElement('option');
            option.value = openrouter.provider_id;
            option.textContent = `${openrouter.name} (${getStatus(openrouter)})`;
            option.selected = true;
            select.appendChild(option);
        }

        others.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider.provider_id;
            const status = getStatus(provider);
            option.textContent = `${provider.name} (${status})`;
            if (status !== 'available') {
                option.disabled = true;
            }
            select.appendChild(option);
        });

        // Load models for default provider
        if (openrouter) {
            loadModels(openrouter.provider_id);
        }
    } catch (error) {
        console.error('Failed to load providers:', error);
        const option = document.createElement('option');
        option.textContent = 'Failed to load providers';
        select.appendChild(option);
    }
}

async function loadModels(providerId) {
    const modelSelect = document.getElementById('modelSelect');
    modelSelect.textContent = ''; // Clear existing options

    if (!providerId) {
        const option = document.createElement('option');
        option.textContent = 'Select a provider first';
        modelSelect.appendChild(option);
        return;
    }

    const option = document.createElement('option');
    option.textContent = 'Loading models...';
    modelSelect.appendChild(option);

    try {
        const response = await axios.get(`${API_URL}/v1/models`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const models = response.data.models.filter(m => m.provider === providerId);

        modelSelect.textContent = ''; // Clear loading message

        if (models.length === 0) {
            const option = document.createElement('option');
            option.textContent = 'No models available';
            modelSelect.appendChild(option);
            return;
        }

        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.model_id;
            option.textContent = `${model.display_name} ($${model.cost_input_per_million}/M tokens)`;
            if (model.is_recommended) {
                option.selected = true;
            }
            modelSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load models:', error);
        modelSelect.textContent = '';
        const option = document.createElement('option');
        option.textContent = 'Failed to load models';
        modelSelect.appendChild(option);
    }
}

async function checkHealth() {
    try {
        const response = await axios.get(`${API_URL}/health`);
        const health = response.data;

        const statusEl = document.getElementById('statusText');
        statusEl.textContent = ''; // Clear existing content

        if (health.status === 'healthy') {
            const span = createTextElement('span', '✅ All systems operational', 'text-green-600');
            statusEl.appendChild(span);
        } else {
            const span = createTextElement('span', '⚠️ Some systems degraded', 'text-yellow-600');
            statusEl.appendChild(span);
        }

        // Show component status
        const components = health.components;
        const statusDiv = document.createElement('div');
        statusDiv.className = 'mt-2 text-xs';

        for (const [component, status] of Object.entries(components)) {
            const icon = status === 'healthy' ? '✅' : '❌';
            const span = createTextElement('span', `${icon} ${component}`, 'mr-3');
            statusDiv.appendChild(span);
        }
        statusEl.appendChild(statusDiv);

    } catch (error) {
        const statusEl = document.getElementById('statusText');
        statusEl.textContent = '';
        const span = createTextElement('span', '❌ Cannot connect to API', 'text-red-600');
        statusEl.appendChild(span);
        console.error('Health check failed:', error);
    }
}

async function createClient() {
    const name = document.getElementById('clientName').value;
    if (!name) {
        alert('Please enter a client name');
        return;
    }

    try {
        const response = await axios.post(`${API_URL}/v1/clients`, {
            name: name,
            reference_code: `REF-${Date.now()}`
        }, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });

        const client = response.data;
        const resultEl = document.getElementById('clientResult');
        resultEl.textContent = '';
        const span = createTextElement('span', `✅ Created: Client ID ${client.id}`, 'text-green-600');
        resultEl.appendChild(span);
        document.getElementById('clientId').value = client.id;

    } catch (error) {
        const errorMsg = error.response?.data?.detail || error.message;
        const statusCode = error.response?.status;

        let displayMsg = errorMsg;
        if (statusCode === 401) {
            displayMsg = 'Authentication required. Please login first.';
        }

        const resultEl = document.getElementById('clientResult');
        resultEl.textContent = '';
        const span = createTextElement('span', `❌ Error: ${displayMsg}`, 'text-red-600');
        resultEl.appendChild(span);
    }
}

async function createCase() {
    const clientId = document.getElementById('clientId').value;
    const caseName = document.getElementById('caseName').value;

    if (!clientId || !caseName) {
        alert('Please enter both Client ID and Case Name');
        return;
    }

    try {
        const response = await axios.post(`${API_URL}/v1/cases`, {
            client_id: parseInt(clientId),
            name: caseName
        }, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });

        const caseData = response.data;
        const resultEl = document.getElementById('caseResult');
        resultEl.textContent = '';
        const span = createTextElement('span', `✅ Created: Case ID ${caseData.id}`, 'text-green-600');
        resultEl.appendChild(span);
        document.getElementById('caseIdForRun').value = caseData.id;

    } catch (error) {
        // Improved error message extraction
        let errorMsg = 'Unknown error occurred';

        if (error.response?.data) {
            // Try to extract detail field (FastAPI standard)
            if (typeof error.response.data.detail === 'string') {
                errorMsg = error.response.data.detail;
            } else if (typeof error.response.data.detail === 'object') {
                errorMsg = JSON.stringify(error.response.data.detail);
            } else if (error.response.data.message) {
                errorMsg = error.response.data.message;
            } else {
                errorMsg = JSON.stringify(error.response.data);
            }
        } else if (error.message) {
            errorMsg = error.message;
        }

        // Add status code specific messages
        const statusCode = error.response?.status;
        if (statusCode === 401) {
            errorMsg = 'Authentication required. Please login first.';
        } else if (statusCode === 404) {
            errorMsg = 'Client not found. Please check the Client ID.';
        }

        const resultEl = document.getElementById('caseResult');
        resultEl.textContent = '';
        const span = createTextElement('span', `❌ Error: ${errorMsg}`, 'text-red-600');
        resultEl.appendChild(span);
    }
}

async function startRun() {
    const caseId = document.getElementById('caseIdForRun').value;
    const files = document.getElementById('fileInput').files;
    const provider = document.getElementById('providerSelect').value;
    const model = document.getElementById('modelSelect').value;
    const docExtractor = document.getElementById('docExtractorSelect').value;

    if (!authToken) {
        showLoginModal();
        alert('Please login to start processing.');
        return;
    }

    if (!caseId || files.length === 0) {
        alert('Please enter Case ID and select files');
        return;
    }

    const uploadResult = document.getElementById('uploadResult');
    uploadResult.textContent = '';

    // Show loading spinner
    const spinnerDiv = document.createElement('div');
    spinnerDiv.className = 'spinner';
    uploadResult.appendChild(spinnerDiv);
    const processingText = createTextElement('span', ' Processing...', '');
    uploadResult.appendChild(processingText);

    try {
        // Calculate SHA256 hashes for integrity verification
        const fileHashes = {};
        for (let file of files) {
            try {
                const hash = await calculateFileSHA256(file);
                fileHashes[file.name] = hash;
                console.log(`File: ${file.name}, SHA256: ${hash}`);
            } catch (err) {
                console.warn(`Could not calculate hash for ${file.name}:`, err);
            }
        }

        // Step 1: Create run (no files)
        const runCreateResp = await axios.post(`${API_URL}/v1/runs`, {
            case_id: parseInt(caseId),
            provider: provider || 'openrouter',
            model: model || null,
            doc_extractor: docExtractor || 'docling'
        }, { headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {} });

        const runId = runCreateResp.data.run_id;

        // Step 2: Upload each file via run-specific endpoint
        const manifest = [];
        for (let file of files) {
            const fd = new FormData();
            fd.append('file', file);
            const upResp = await axios.put(`${API_URL}/v1/runs/${runId}/upload`, fd, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {})
                }
            });
            const payload = upResp.data;
            manifest.push({
                filename: file.name,
                size_bytes: file.size,
                sha256: fileHashes[file.name] || '',
                storage_key: payload.storage_key,
                mime_type: file.type || 'application/pdf'
            });
        }

        // Step 3: Start run with manifest (requires auth)
        await axios.put(`${API_URL}/v1/runs/${runId}/start`, { files: manifest }, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });

        uploadResult.textContent = '';
        const span = createTextElement('span', `✅ Run ${runId} started!`, 'text-green-600');
        uploadResult.appendChild(span);

        // Start monitoring
        monitorRun(runId);

    } catch (error) {
        uploadResult.textContent = '';

        // Improved error message extraction
        let errorMsg = 'Unknown error occurred';

        if (error.response?.data) {
            // Try to extract detail field (FastAPI standard)
            if (typeof error.response.data.detail === 'string') {
                errorMsg = error.response.data.detail;
            } else if (typeof error.response.data.detail === 'object') {
                errorMsg = JSON.stringify(error.response.data.detail);
            } else if (error.response.data.message) {
                errorMsg = error.response.data.message;
            } else {
                errorMsg = JSON.stringify(error.response.data);
            }
        } else if (error.request) {
            // Request was made but no response received (network error)
            errorMsg = 'Cannot connect to API. Please check if the API is running at ' + API_URL;
        } else if (error.message) {
            errorMsg = error.message;
        }

        // Add status code specific messages
        const statusCode = error.response?.status;
        if (statusCode === 401) {
            errorMsg = 'Authentication required. Please login first.';
        } else if (statusCode === 404) {
            errorMsg = 'Case not found. Please check the Case ID.';
        } else if (statusCode === 500) {
            errorMsg = 'Server error. Please try again or contact support.';
        }

        const span = createTextElement('span', `❌ Error: ${errorMsg}`, 'text-red-600');
        uploadResult.appendChild(span);
    }
}

async function monitorRun(runId) {
    const interval = setInterval(async () => {
        try {
            const response = await axios.get(`${API_URL}/v1/runs/${runId}`, {
                headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
            });
            const run = response.data;

            // Update run in list
            updateRunInList(run);

            // If complete, stop monitoring and load events
            if (['success', 'failed', 'partial'].includes(run.status)) {
                clearInterval(interval);
                if (run.status !== 'failed') {
                    loadEvents(runId);
                }
            }
        } catch (error) {
            console.error('Monitor error:', error);
            clearInterval(interval);
        }
    }, 2000); // Check every 2 seconds
}

async function loadRuns(limit = 20, offset = 0) {
    try {
        // Fetch runs using the new efficient GET /v1/runs endpoint
        const response = await axios.get(`${API_URL}/v1/runs`, {
            params: {
                skip: 0,
                limit: 10,
                include_metadata: true
            },
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });

        const runs = response.data.runs;
        const pagination = response.data.pagination;

        const runsListEl = document.getElementById('runsList');
        runsListEl.textContent = ''; // Clear existing content

        if (runs.length === 0) {
            const p = createTextElement('p', 'No runs found. Create a client, case, and run to get started.', 'text-gray-500');
            runsListEl.appendChild(p);
        } else {
            for (const run of runs) {
                const runEl = createRunElement(run);
                runsListEl.appendChild(runEl);
            }

            // Add pagination controls if needed
            if (pagination.total > limit) {
                const paginationEl = createPaginationElement(pagination, limit, offset);
                runsListEl.appendChild(paginationEl);
            }
        }

    } catch (error) {
        console.error('Load runs error:', error);
        const runsListEl = document.getElementById('runsList');
        runsListEl.textContent = '';
        const p = createTextElement('p', 'Failed to load runs. Please check API connection.', 'text-red-600');
        runsListEl.appendChild(p);
    }
}

function createRunElement(run) {
    const statusColors = {
        'queued': 'bg-gray-100',
        'processing': 'bg-yellow-100',
        'success': 'bg-green-100',
        'failed': 'bg-red-100',
        'partial': 'bg-orange-100'
    };

    const statusColor = statusColors[run.status] || 'bg-gray-100';
    const createdDate = new Date(run.created_at).toLocaleString();

    const runDiv = document.createElement('div');
    runDiv.className = `border rounded p-4 hover:bg-gray-50 ${statusColor}`;
    runDiv.setAttribute('data-run-id', run.run_id);

    const flexDiv = document.createElement('div');
    flexDiv.className = 'flex justify-between items-center';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'flex-1';

    // Title line
    const titleDiv = document.createElement('div');
    titleDiv.className = 'flex items-center space-x-2';

    const runLabel = createTextElement('span', `Run ${run.run_id}`, 'font-semibold');
    const sep1 = createTextElement('span', '|', 'text-sm text-gray-600');
    const caseLabel = createTextElement('span', `Case ${run.case_id}`, 'text-sm text-gray-600');
    const sep2 = createTextElement('span', '|', 'text-sm text-gray-600');

    const statusClass = run.status === 'success' ? 'text-green-700' :
                       run.status === 'failed' ? 'text-red-700' : 'text-gray-700';
    const statusLabel = createTextElement('span', run.status.toUpperCase(), `text-sm font-medium ${statusClass}`);

    titleDiv.appendChild(runLabel);
    titleDiv.appendChild(sep1);
    titleDiv.appendChild(caseLabel);
    titleDiv.appendChild(sep2);
    titleDiv.appendChild(statusLabel);

    // Details line
    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'text-sm text-gray-600 mt-1';
    detailsDiv.textContent = `${run.provider} / ${run.model || 'default'} | ${run.counts.processed}/${run.counts.total} docs | ${createdDate}`;

    contentDiv.appendChild(titleDiv);
    contentDiv.appendChild(detailsDiv);

    // View button
    const viewBtn = document.createElement('button');
    viewBtn.className = 'bg-blue-500 text-white px-3 py-1 rounded text-sm hover:bg-blue-600';
    viewBtn.textContent = 'View';
    viewBtn.addEventListener('click', () => viewRun(run.run_id));

    flexDiv.appendChild(contentDiv);
    flexDiv.appendChild(viewBtn);
    runDiv.appendChild(flexDiv);

    return runDiv;
}

function createPaginationElement(pagination, limit, offset) {
    const paginationDiv = document.createElement('div');
    paginationDiv.className = 'mt-4 flex justify-between items-center text-sm text-gray-600';

    // Showing text
    const showingSpan = createTextElement(
        'span',
        `Showing ${offset + 1}-${Math.min(offset + limit, pagination.total)} of ${pagination.total} runs`,
        ''
    );

    // Button container
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'space-x-2';

    // Previous button
    const prevBtn = document.createElement('button');
    if (pagination.has_prev) {
        prevBtn.className = 'bg-gray-300 px-3 py-1 rounded hover:bg-gray-400';
        prevBtn.textContent = 'Previous';
        prevBtn.addEventListener('click', () => loadRuns(limit, offset - limit));
    } else {
        prevBtn.className = 'bg-gray-200 px-3 py-1 rounded text-gray-400 cursor-not-allowed';
        prevBtn.textContent = 'Previous';
        prevBtn.disabled = true;
    }

    // Next button
    const nextBtn = document.createElement('button');
    if (pagination.has_next) {
        nextBtn.className = 'bg-gray-300 px-3 py-1 rounded hover:bg-gray-400';
        nextBtn.textContent = 'Next';
        nextBtn.addEventListener('click', () => loadRuns(limit, offset + limit));
    } else {
        nextBtn.className = 'bg-gray-200 px-3 py-1 rounded text-gray-400 cursor-not-allowed';
        nextBtn.textContent = 'Next';
        nextBtn.disabled = true;
    }

    buttonsDiv.appendChild(prevBtn);
    buttonsDiv.appendChild(nextBtn);

    paginationDiv.appendChild(showingSpan);
    paginationDiv.appendChild(buttonsDiv);

    return paginationDiv;
}

function updateRunInList(run) {
    const runEl = document.querySelector(`[data-run-id="${run.run_id}"]`);
    if (runEl) {
        const newRunEl = createRunElement(run);
        runEl.replaceWith(newRunEl);
    }
}

async function showRunDetails(runId) {
    try {
        const response = await axios.get(`${API_URL}/v1/runs/${runId}`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const run = response.data;

        const detailsPanel = document.getElementById('runDetails');
        const contentDiv = document.getElementById('runDetailsContent');

        // Clear existing content
        contentDiv.textContent = '';

        // Create details table
        const detailsTable = document.createElement('table');
        detailsTable.className = 'w-full text-sm';

        const details = [
            { label: 'Run ID', value: run.run_id },
            { label: 'Case ID', value: run.case_id },
            { label: 'Status', value: run.status },
            { label: 'Provider', value: run.provider || 'N/A' },
            { label: 'Model', value: run.model || 'Default' },
            { label: 'Document Extractor', value: run.doc_extractor || 'docling' },
            { label: 'Documents', value: run.documents?.length || 0 },
            { label: 'Events Extracted', value: run.event_count || 0 },
            { label: 'Created', value: new Date(run.created_at).toLocaleString() },
            { label: 'Processing Time', value: run.total_seconds ? `${run.total_seconds.toFixed(2)}s` : 'N/A' },
            { label: 'Estimated Cost', value: run.cost_usd ? `$${run.cost_usd.toFixed(4)}` : 'N/A' }
        ];

        const tbody = document.createElement('tbody');
        details.forEach(item => {
            const tr = document.createElement('tr');
            tr.className = 'border-b';

            const labelTd = document.createElement('td');
            labelTd.className = 'py-2 font-medium text-gray-700';
            labelTd.textContent = item.label + ':';

            const valueTd = document.createElement('td');
            valueTd.className = 'py-2 pl-4';

            // Special formatting for status
            if (item.label === 'Status') {
                const statusSpan = document.createElement('span');
                statusSpan.className = run.status === 'completed' ? 'text-green-600' :
                                     run.status === 'failed' ? 'text-red-600' :
                                     run.status === 'processing' ? 'text-blue-600' :
                                     'text-gray-600';
                statusSpan.textContent = item.value;
                valueTd.appendChild(statusSpan);
            } else {
                valueTd.textContent = item.value;
            }

            tr.appendChild(labelTd);
            tr.appendChild(valueTd);
            tbody.appendChild(tr);
        });

        detailsTable.appendChild(tbody);
        contentDiv.appendChild(detailsTable);

        // Show the panel
        detailsPanel.classList.remove('hidden');

    } catch (error) {
        console.error('Failed to load run details:', error);
    }
}

async function viewRun(runId) {
    try {
        // Track current run for exports
        currentRunId = runId;

        // First get run details
        await showRunDetails(runId);

        const response = await axios.get(`${API_URL}/v1/runs/${runId}/events`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const events = response.data.events;

        const contentEl = document.getElementById('eventsContent');
        contentEl.textContent = ''; // Clear existing content

        // Only sanitize if we absolutely need HTML structure
        // For now, use DOM methods for everything
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'mb-4 text-sm text-gray-600';
        summaryDiv.textContent = `Run ${runId}: Found ${events.length} legal events`;

        const tableContainer = document.createElement('div');
        tableContainer.className = 'overflow-x-auto';

        if (events.length > 0) {
            const table = createEventsTable(events);
            tableContainer.appendChild(table);
        } else {
            const p = createTextElement('p', 'No events extracted', 'text-gray-500');
            tableContainer.appendChild(p);
        }

        contentEl.appendChild(summaryDiv);
        contentEl.appendChild(tableContainer);

        // Show events section
        document.getElementById('eventsSection').classList.remove('hidden');

    } catch (error) {
        console.error('View run error:', error);
        alert('Failed to load run events');
    }
}

function createEventsTable(events) {
    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-gray-200';

    // Create thead
    const thead = document.createElement('thead');
    thead.className = 'bg-gray-50';
    const headerRow = document.createElement('tr');

    const headers = ['#', 'Date', 'Event Particulars', 'Citation', 'Document'];
    headers.forEach(header => {
        const th = document.createElement('th');
        th.className = 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider';
        th.textContent = header;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    // Create tbody
    const tbody = document.createElement('tbody');
    tbody.className = 'bg-white divide-y divide-gray-200';

    events.forEach(event => {
        const row = document.createElement('tr');

        const numberTd = createTextElement('td', event.number || '-', 'px-6 py-4 whitespace-nowrap text-sm');
        const dateTd = createTextElement('td', event.date || '-', 'px-6 py-4 whitespace-nowrap text-sm');

        const particularsTd = document.createElement('td');
        particularsTd.className = 'px-6 py-4 text-sm truncate-cell';
        particularsTd.textContent = event.event_particulars || '-';
        particularsTd.setAttribute('data-full-text', event.event_particulars || '-');

        const citationTd = document.createElement('td');
        citationTd.className = 'px-6 py-4 text-sm truncate-cell';
        citationTd.textContent = event.citation || '-';
        citationTd.setAttribute('data-full-text', event.citation || '-');

        const documentTd = createTextElement('td', event.document_name || '-', 'px-6 py-4 whitespace-nowrap text-sm');

        row.appendChild(numberTd);
        row.appendChild(dateTd);
        row.appendChild(particularsTd);
        row.appendChild(citationTd);
        row.appendChild(documentTd);

        tbody.appendChild(row);
    });

    table.appendChild(thead);
    table.appendChild(tbody);

    return table;
}

async function loadEvents(runId) {
    await viewRun(runId);
}

// File integrity functions
async function calculateFileSHA256(file) {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
}

// Export functionality
async function exportEvents(format) {
    if (!currentRunId) {
        alert('No run selected');
        return;
    }

    try {
        const response = await axios.get(
            `${API_URL}/v1/runs/${currentRunId}/export?fmt=${format}`,
            {
                responseType: 'blob',
                headers: {
                    Authorization: authToken ? `Bearer ${authToken}` : undefined
                }
            }
        );

        // Create blob and download
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `run_${currentRunId}_events.${format}`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Export error:', error);
        const message = error.response?.status === 401
            ? 'Authentication required. Please login first.'
            : `Failed to export events: ${error.message}`;
        alert(message);
    }
}

// Global functions for backward compatibility (but secured)
window.viewRun = viewRun;
window.loadRuns = loadRuns;
