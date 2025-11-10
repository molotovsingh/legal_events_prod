// API configuration
const API_URL = 'http://localhost:8000';

// Initialize DOMPurify with safe configuration
const purifyConfig = {
    ALLOWED_TAGS: ['span', 'div', 'p', 'button', 'table', 'thead', 'tbody', 'tr', 'td', 'th'],
    ALLOWED_ATTR: ['class', 'data-run-id', 'data-case-id'],
    KEEP_CONTENT: true
};

// Authentication state
let authToken = localStorage.getItem('jwt_token');
let currentUser = null;

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
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;

    if (!email || !password) {
        alert('Please enter both email and password');
        return;
    }

    try {
        const response = await axios.post(`${API_URL}/v1/auth/login`, {
            username: email,
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
        const errorMsg = error.response?.data?.detail || 'Invalid credentials';
        document.getElementById('loginError').textContent = errorMsg;
        document.getElementById('loginError').classList.remove('hidden');
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
}

async function loadProviders() {
    const select = document.getElementById('providerSelect');
    select.textContent = ''; // Clear existing options

    try {
        const response = await axios.get(`${API_URL}/v1/providers`);
        const providers = response.data.providers;

        // Find langextract (working provider)
        const langextract = providers.find(p => p.id === 'langextract');
        const others = providers.filter(p => p.id !== 'langextract');

        if (langextract && langextract.status === 'available') {
            const option = document.createElement('option');
            option.value = langextract.id;
            option.textContent = `${langextract.name} (${langextract.status})`;
            option.selected = true;
            select.appendChild(option);
        }

        others.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider.id;
            option.textContent = `${provider.name} (${provider.status})`;
            if (provider.status !== 'available') {
                option.disabled = true;
            }
            select.appendChild(option);
        });

        // Load models for default provider
        if (langextract) {
            loadModels(langextract.id);
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
        const response = await axios.get(`${API_URL}/v1/models`);
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
            name: caseName,
            description: 'Test case created from UI'
        });

        const caseData = response.data;
        const resultEl = document.getElementById('caseResult');
        resultEl.textContent = '';
        const span = createTextElement('span', `✅ Created: Case ID ${caseData.id}`, 'text-green-600');
        resultEl.appendChild(span);
        document.getElementById('caseIdForRun').value = caseData.id;

    } catch (error) {
        const errorMsg = error.response?.data?.detail || error.message;
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
        // Upload files
        const formData = new FormData();
        for (let file of files) {
            formData.append('files', file);
        }

        const uploadResponse = await axios.post(`${API_URL}/v1/upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });

        const uploadedFiles = uploadResponse.data.files;

        // Create manifest
        const manifest = uploadedFiles.map(f => ({
            filename: f.filename,
            storage_path: f.storage_path
        }));

        // Start run
        const runResponse = await axios.post(`${API_URL}/v1/runs`, {
            case_id: parseInt(caseId),
            provider: provider || 'langextract',
            model: model || null,
            files: manifest
        });

        const runId = runResponse.data.run_id;
        uploadResult.textContent = '';
        const span = createTextElement('span', `✅ Run ${runId} started!`, 'text-green-600');
        uploadResult.appendChild(span);

        // Start monitoring
        monitorRun(runId);

    } catch (error) {
        uploadResult.textContent = '';
        const errorMsg = error.response?.data?.detail || error.message;
        const span = createTextElement('span', `❌ Error: ${errorMsg}`, 'text-red-600');
        uploadResult.appendChild(span);
    }
}

async function monitorRun(runId) {
    const interval = setInterval(async () => {
        try {
            const response = await axios.get(`${API_URL}/v1/runs/${runId}`);
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
            params: { limit, offset }
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

async function viewRun(runId) {
    try {
        const response = await axios.get(`${API_URL}/v1/events?run_id=${runId}`);
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

// Global functions for backward compatibility (but secured)
window.viewRun = viewRun;
window.loadRuns = loadRuns;