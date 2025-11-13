// API configuration - derive from environment or window.location
const API_URL = (() => {
    try {
        const base = (typeof window !== 'undefined' && typeof window.API_BASE_URL === 'string')
            ? window.API_BASE_URL.trim().replace(/\/$/, '')
            : '';
        return base; // '' => use relative paths
    } catch (_) {
        return '';
    }
})();

try { axios.defaults.baseURL = API_URL || undefined; } catch (_) {}

// Wrap in IIFE to avoid global pollution
(function() {
'use strict';

// State management with security improvements
let authToken = localStorage.getItem('jwt_token');
let currentUser = null;
let currentRunId = null;
let pollInterval = null;

// Token expiration tracking
const TOKEN_KEY = 'jwt_token';
const TOKEN_EXPIRY_KEY = 'jwt_expiry';

function setAuthToken(token, expiresIn = 3600) { // Default 1 hour expiry
    authToken = token;
    localStorage.setItem(TOKEN_KEY, token);
    const expiry = new Date().getTime() + (expiresIn * 1000);
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiry.toString());
}

function isTokenExpired() {
    const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!expiry) return true;
    return new Date().getTime() > parseInt(expiry);
}

function clearAuthToken() {
    authToken = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
}

// Persistent state (last used IDs)
let lastClientId = localStorage.getItem('last_client_id');
let lastCaseId = localStorage.getItem('last_case_id');

// Initialize axios interceptors with security improvements
axios.defaults.timeout = 30000; // 30 second timeout
axios.defaults.withCredentials = false; // Don't send cookies

axios.interceptors.request.use(
    config => {
        if (authToken) {
            config.headers.Authorization = `Bearer ${authToken}`;
        }
        return config;
    },
    error => Promise.reject(error)
);

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

// Debug badge for resolved API URL with quick copy
function renderApiBadge() {
    try {
        const el = document.getElementById('apiBadge');
        if (!el) return;
        el.textContent = '';
        const span = document.createElement('span');
        span.className = 'bg-gray-100 text-gray-700 px-2 py-1 rounded border border-gray-200';
        span.textContent = `API: ${API_URL || 'same-origin'}`;
        const btn = document.createElement('button');
        btn.className = 'ml-2 text-blue-600 underline';
        btn.textContent = 'Copy';
        btn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(API_URL || window.location.origin);
                btn.textContent = 'Copied!';
                setTimeout(() => btn.textContent = 'Copy', 1000);
            } catch (_) {}
        });
        el.appendChild(span);
        el.appendChild(btn);
    } catch (_) {}
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    renderApiBadge();
    // Load providers first since they don't require auth
    try {
        await loadProviders();
    } catch (error) {
        console.error('Failed to load providers on page load:', error);
    }
    
    // Then check auth status
    await checkAuthStatus();
    initializeQuickStart();
});

// Authentication functions
function showLoginModal() {
    document.getElementById('loginModal').classList.remove('hidden');
}

function hideLoginModal() {
    document.getElementById('loginModal').classList.add('hidden');
}

async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');
    const loginBtn = document.getElementById('loginBtn');

    errorDiv.classList.add('hidden');
    errorDiv.textContent = '';

    if (!email || !password) {
        errorDiv.textContent = 'Email and password required';
        errorDiv.classList.remove('hidden');
        return;
    }

    // Show loading state
    if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.textContent = 'Logging in...';
    }

    try {
        const response = await axios.post(`${API_URL}/v1/auth/login`, {
            email: email,
            password: password
        });

        const token = response.data.access_token;
        const expiresIn = response.data.expires_in || 3600; // Default 1 hour
        setAuthToken(token, expiresIn);
        currentUser = response.data.user || { email: email };

        hideLoginModal();
        updateAuthUI();
        
        // Load providers after successful login
        try {
            await loadProviders();
        } catch (providerError) {
            console.error('Failed to load providers after login:', providerError);
            // Don't fail login if providers fail to load
        }
    } catch (error) {
        errorDiv.textContent = error.response?.data?.detail || 'Login failed';
        errorDiv.classList.remove('hidden');
    } finally {
        // Reset button state
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.textContent = 'Login';
        }
    }
}

function handleLogout() {
    clearAuthToken();
    currentUser = null;
    updateAuthUI();
}

async function checkAuthStatus() {
    if (!authToken || isTokenExpired()) {
        clearAuthToken();
        showLoginModal();
        return;
    }

    try {
        await axios.get(`${API_URL}/v1/auth/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        currentUser = { authenticated: true };
        updateAuthUI();
    } catch (error) {
        handleLogout();
        showLoginModal();
    }
}

function updateAuthUI() {
    const authSection = document.getElementById('authSection');
    const mainContent = document.getElementById('mainContent');

    if (authToken && currentUser) {
        authSection.innerHTML = '<button onclick="handleLogout()" class="compact-btn btn-secondary">Logout</button>';
        mainContent.classList.remove('hidden');
    } else {
        authSection.innerHTML = '<button onclick="showLoginModal()" class="compact-btn btn-primary">Login</button>';
        mainContent.classList.add('hidden');
    }
}

// Provider management
let providersLoaded = false; // Flag to prevent duplicate event listeners

async function loadProviders() {
    try {
        const response = await axios.get(`${API_URL}/v1/providers`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const providerSelect = document.getElementById('providerSelect');
        providerSelect.innerHTML = '';

        response.data.providers.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider.provider_id;
            option.textContent = `${provider.display_name} ${provider.is_working ? '' : '(Limited)'}`;
            providerSelect.appendChild(option);
        });

        // Set default and load models
        if (response.data.providers.length > 0) {
            const defaultProvider = response.data.providers.find(p => p.recommended) || response.data.providers[0];
            providerSelect.value = defaultProvider.provider_id;
            await loadModels(defaultProvider.provider_id);
        }

        // Add change listener only once
        if (!providersLoaded) {
            providerSelect.addEventListener('change', (e) => loadModels(e.target.value));
            providersLoaded = true;
        }
    } catch (error) {
        console.error('Failed to load providers:', error);
        // Show error in UI if user is logged in
        if (authToken) {
            const providerSelect = document.getElementById('providerSelect');
            providerSelect.innerHTML = '<option value="">Failed to load providers</option>';
            
            // Show user-friendly error
            const statusDiv = document.getElementById('quickStartStatus') || document.getElementById('uploadStatus');
            if (statusDiv) {
                statusDiv.innerHTML = '<span class="text-red-600">Failed to load providers. Please refresh the page.</span>';
            }
        }
    }
}

async function loadModels(providerKey) {
    try {
        const response = await axios.get(`${API_URL}/v1/models?provider=${providerKey}`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const modelSelect = document.getElementById('modelSelect');
        
        modelSelect.innerHTML = '';
        
        if (response.data.models && response.data.models.length > 0) {
            response.data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.model_id;
                option.textContent = `${model.display_name} ${model.is_recommended ? '⭐' : ''}`;
                modelSelect.appendChild(option);
            });
            
            // Select the first recommended model, or first model if none recommended
            const recommendedModel = response.data.models.find(m => m.is_recommended);
            if (recommendedModel) {
                modelSelect.value = recommendedModel.model_id;
            } else if (response.data.models.length > 0) {
                modelSelect.value = response.data.models[0].model_id;
            }
        } else {
            modelSelect.innerHTML = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Failed to load models:', error);
        const modelSelect = document.getElementById('modelSelect');
        modelSelect.innerHTML = '<option value="">Failed to load models</option>';
    }
}

// Quick Start functionality with validation
async function initializeQuickStart() {
    const quickClientId = document.getElementById('quickClientId');
    const quickCaseId = document.getElementById('quickCaseId');
    const quickStartBtn = document.getElementById('quickStartBtn');
    const quickStartBadge = document.getElementById('quickStartBadge');

    // Validate stored IDs against server
    if (lastClientId && lastCaseId) {
        try {
            // Verify client exists
            const clientResponse = await axios.get(`${API_URL}/v1/clients/${lastClientId}`, {
                headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
            });
            if (!clientResponse.data) {
                throw new Error('Client not found');
            }
            
            // Verify case exists and belongs to client
            const caseResponse = await axios.get(`${API_URL}/v1/cases/${lastCaseId}`, {
                headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
            });
            if (!caseResponse.data || caseResponse.data.client_id !== parseInt(lastClientId)) {
                throw new Error('Case not found or invalid');
            }
            
            // IDs are valid
            quickClientId.value = lastClientId;
            quickCaseId.value = lastCaseId;
            quickStartBtn.disabled = false;
            quickStartBadge.textContent = 'Ready';
            quickStartBadge.className = 'status-badge status-success';
        } catch (error) {
            console.error('Quick Start validation failed:', error);
            // Clear invalid IDs
            localStorage.removeItem('last_client_id');
            localStorage.removeItem('last_case_id');
            lastClientId = null;
            lastCaseId = null;
            
            // Show not ready state
            quickClientId.value = '';
            quickCaseId.value = '';
            quickStartBtn.disabled = true;
            quickStartBadge.textContent = 'Not Ready';
            quickStartBadge.className = 'status-badge status-pending';
        }
    } else {
        // No stored IDs
        quickClientId.value = '';
        quickCaseId.value = '';
        quickStartBtn.disabled = true;
        quickStartBadge.textContent = 'Not Ready';
        quickStartBadge.className = 'status-badge status-pending';
    }
}

async function quickStartRun() {
    const caseId = document.getElementById('quickCaseId').value;
    const files = document.getElementById('quickFileInput').files;
    const statusDiv = document.getElementById('quickStartStatus');

    if (!caseId || files.length === 0) {
        statusDiv.innerHTML = '<span class="text-red-600">Case ID and files required</span>';
        return;
    }

    await processRun(caseId, files, statusDiv);
}

// Client/Case creation
async function createClient() {
    const clientName = document.getElementById('clientName').value.trim();
    const statusDiv = document.getElementById('clientStatus');

    if (!clientName) {
        statusDiv.innerHTML = '<span class="text-red-600">Client name required</span>';
        return;
    }

    statusDiv.innerHTML = '<span class="text-blue-600"><span class="spinner"></span> Creating...</span>';

    try {
        const response = await axios.post(`${API_URL}/v1/clients`, { 
            name: clientName 
        }, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        lastClientId = response.data.id;
        localStorage.setItem('last_client_id', lastClientId);

        document.getElementById('clientIdForCase').value = lastClientId;
        statusDiv.innerHTML = `<span class="text-green-600">Created: ID ${lastClientId}</span>`;
        
        // Update quick start
        document.getElementById('quickClientId').value = lastClientId;
    } catch (error) {
        console.error('Client creation error:', error);
        const errorMsg = error.response?.data?.detail || error.message || 'Failed to create client';
        statusDiv.innerHTML = `<span class="text-red-600">Error: ${errorMsg}</span>`;
    }
}

async function createCase() {
    const clientId = document.getElementById('clientIdForCase').value;
    const caseName = document.getElementById('caseName').value.trim();
    const statusDiv = document.getElementById('caseStatus');

    if (!clientId || !caseName) {
        statusDiv.innerHTML = '<span class="text-red-600">Client ID and case name required</span>';
        return;
    }

    statusDiv.innerHTML = '<span class="text-blue-600"><span class="spinner"></span> Creating...</span>';

    try {
        const response = await axios.post(`${API_URL}/v1/cases`, {
            client_id: parseInt(clientId),
            name: caseName
        }, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        lastCaseId = response.data.id;
        localStorage.setItem('last_case_id', lastCaseId);

        document.getElementById('caseIdForRun').value = lastCaseId;
        statusDiv.innerHTML = `<span class="text-green-600">Created: ID ${lastCaseId}</span>`;
        
        // Update quick start with validation
        await initializeQuickStart();
    } catch (error) {
        console.error('Case creation error:', error);
        const errorMsg = error.response?.data?.detail || error.message || 'Failed to create case';
        statusDiv.innerHTML = `<span class="text-red-600">Error: ${errorMsg}</span>`;
    }
}

async function startRun() {
    const caseId = document.getElementById('caseIdForRun').value;
    const files = document.getElementById('fileInput').files;
    const statusDiv = document.getElementById('uploadStatus');

    if (!authToken) {
        showLoginModal();
        statusDiv.innerHTML = '<span class="text-red-600">Login required to start processing</span>';
        return;
    }

    if (!caseId || files.length === 0) {
        statusDiv.innerHTML = '<span class="text-red-600">Case ID and files required</span>';
        return;
    }

    await processRun(caseId, files, statusDiv);
}

// Unified run processing
async function processRun(caseId, files, statusDiv) {
    const provider = document.getElementById('providerSelect').value;
    const model = document.getElementById('modelSelect').value;
    const docExtractor = document.getElementById('docExtractorSelect').value;

    if (!provider || !model) {
        statusDiv.innerHTML = '<span class="text-red-600">Provider and model required</span>';
        return;
    }

    // File validation
    const validTypes = ['application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    const maxSize = 10 * 1024 * 1024; // 10MB
    
    for (let file of files) {
        if (!validTypes.includes(file.type)) {
            statusDiv.innerHTML = `<span class="text-red-600">Invalid file type: ${file.name}. Only PDF, TXT, DOC, DOCX allowed.</span>`;
            return;
        }
        if (file.size > maxSize) {
            statusDiv.innerHTML = `<span class="text-red-600">File too large: ${file.name}. Maximum 10MB.</span>`;
            return;
        }
    }

    statusDiv.innerHTML = '<span class="text-blue-600"><span class="spinner"></span> Preparing run...</span>';

    try {
        // Step 1: Create run (no files)
        const runCreate = await axios.post(`${API_URL}/v1/runs`, {
            case_id: parseInt(caseId),
            provider: provider,
            model: model,
            doc_extractor: docExtractor
        }, { headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {} });

        currentRunId = runCreate.data.run_id;

    // Step 2: Upload each file to the run
    const manifest = [];
    for (let file of files) {
        const fd = new FormData();
        fd.append('file', file);
        const upResp = await axios.put(`${API_URL}/v1/runs/${currentRunId}/upload`, fd, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {})
                }
            });
        const data = upResp.data;
        const sha = await calculateFileSHA256(file).catch(() => '');
        manifest.push({
            filename: file.name,
            size_bytes: file.size,
            sha256: sha,
            storage_key: data.storage_key,
            mime_type: file.type || 'application/pdf'
        });
    }

        // Step 3: Start the run
        await axios.put(`${API_URL}/v1/runs/${currentRunId}/start`, { files: manifest }, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });

        statusDiv.innerHTML = `<span class="text-green-600">Run ${currentRunId} started</span>`;

        // Show results section and start polling
        showResults();
        startPolling();
    } catch (error) {
        console.error('Run creation error:', error);
        const errorMsg = error.response?.data?.detail || error.message || 'Failed to start run';
        statusDiv.innerHTML = `<span class="text-red-600">Error: ${errorMsg}</span>`;
    }
}

// File integrity helper
async function calculateFileSHA256(file) {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// Results display
function showResults() {
    const resultsSection = document.getElementById('resultsSection');
    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

async function refreshResults() {
    if (!currentRunId) return;

    try {
        const response = await axios.get(`${API_URL}/v1/runs/${currentRunId}`, {
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
        });
        const run = response.data;

        const resultsBadge = document.getElementById('resultsBadge');
        const resultsContent = document.getElementById('resultsContent');
        const exportButtons = document.getElementById('exportButtons');

        // Update badge
        if (run.status === 'completed') {
            resultsBadge.textContent = 'Completed';
            resultsBadge.className = 'status-badge status-success';
            stopPolling();
            exportButtons.classList.remove('hidden');
        } else if (run.status === 'failed') {
            resultsBadge.textContent = 'Failed';
            resultsBadge.className = 'status-badge status-error';
            stopPolling();
        } else {
            resultsBadge.textContent = 'Processing';
            resultsBadge.className = 'status-badge status-processing';
        }

        // Display summary using DOM methods instead of innerHTML
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'text-xs space-y-1 mb-3';
        
        const runIdDiv = document.createElement('div');
        runIdDiv.innerHTML = '<strong>Run ID:</strong> ';
        runIdDiv.appendChild(document.createTextNode(run.id));
        summaryDiv.appendChild(runIdDiv);
        
        const statusDiv = document.createElement('div');
        statusDiv.innerHTML = '<strong>Status:</strong> ';
        statusDiv.appendChild(document.createTextNode(run.status));
        summaryDiv.appendChild(statusDiv);
        
        const docsDiv = document.createElement('div');
        docsDiv.innerHTML = '<strong>Documents:</strong> ';
        docsDiv.appendChild(document.createTextNode(run.documents?.length || 0));
        summaryDiv.appendChild(docsDiv);

        if (run.run_metadata) {
            if (run.run_metadata.total_seconds) {
                const timeDiv = document.createElement('div');
                timeDiv.innerHTML = '<strong>Processing Time:</strong> ';
                timeDiv.appendChild(document.createTextNode(run.run_metadata.total_seconds.toFixed(1) + 's'));
                summaryDiv.appendChild(timeDiv);
            }
            if (run.run_metadata.cost_usd) {
                const costDiv = document.createElement('div');
                costDiv.innerHTML = '<strong>Cost:</strong> $';
                costDiv.appendChild(document.createTextNode(run.run_metadata.cost_usd.toFixed(4)));
                summaryDiv.appendChild(costDiv);
            }
        }

        resultsContent.innerHTML = '';
        resultsContent.appendChild(summaryDiv);

        // Fetch and display events
        if (run.status === 'completed') {
            const eventsResponse = await axios.get(`${API_URL}/v1/runs/${currentRunId}/events`, {
                headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
            });
            const events = eventsResponse.data;

            if (events.length > 0) {
                const eventsDiv = document.createElement('div');
                eventsDiv.className = 'text-xs';
                eventsDiv.innerHTML = '<strong>Events Extracted:</strong> ';
                eventsDiv.appendChild(document.createTextNode(events.length));
                resultsContent.appendChild(eventsDiv);

                const tableDiv = document.createElement('div');
                tableDiv.className = 'mt-2 overflow-x-auto';
                
                const table = document.createElement('table');
                table.className = 'w-full text-xs border-collapse';
                
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');
                headerRow.className = 'border-b bg-gray-50';
                
                ['Type', 'Date', 'Description'].forEach(headerText => {
                    const th = document.createElement('th');
                    th.className = 'p-2 text-left';
                    th.textContent = headerText;
                    headerRow.appendChild(th);
                });
                thead.appendChild(headerRow);
                table.appendChild(thead);
                
                const tbody = document.createElement('tbody');
                events.slice(0, 10).forEach(event => {
                    const row = document.createElement('tr');
                    row.className = 'border-b';
                    
                    const typeCell = document.createElement('td');
                    typeCell.className = 'p-2';
                    typeCell.textContent = event.event_type || 'N/A';
                    row.appendChild(typeCell);
                    
                    const dateCell = document.createElement('td');
                    dateCell.className = 'p-2';
                    dateCell.textContent = event.event_date || 'N/A';
                    row.appendChild(dateCell);
                    
                    const descCell = document.createElement('td');
                    descCell.className = 'p-2';
                    descCell.textContent = (event.description || '').substring(0, 60) + '...';
                    row.appendChild(descCell);
                    
                    tbody.appendChild(row);
                });
                table.appendChild(tbody);
                tableDiv.appendChild(table);
                resultsContent.appendChild(tableDiv);
                
                if (events.length > 10) {
                    const noteDiv = document.createElement('div');
                    noteDiv.className = 'text-xs text-gray-500 mt-2';
                    noteDiv.textContent = `Showing 10 of ${events.length} events. Export for full data.`;
                    resultsContent.appendChild(noteDiv);
                }
            } else {
                const noEventsDiv = document.createElement('div');
                noEventsDiv.className = 'text-xs text-gray-500 mt-2';
                noEventsDiv.textContent = 'No events extracted';
                resultsContent.appendChild(noEventsDiv);
            }
        }
    } catch (error) {
        console.error('Failed to refresh results:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-red-600 text-xs mt-2';
        errorDiv.textContent = 'Failed to load results. Please refresh the page.';
        resultsContent.appendChild(errorDiv);
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(refreshResults, 3000);
    refreshResults();
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopPolling();
});

// Cleanup on visibility change (tab switching)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopPolling();
    } else if (currentRunId) {
        startPolling();
    }
});

// Export functionality
async function exportData(format) {
    if (!currentRunId) return;

    try {
        const response = await axios.get(`${API_URL}/v1/runs/${currentRunId}/export/${format}`, {
            responseType: 'blob'
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        
        const extensions = { csv: 'csv', xlsx: 'xlsx', json: 'json' };
        link.setAttribute('download', `events_run_${currentRunId}.${extensions[format]}`);
        
        document.body.appendChild(link);
        link.click();
        link.remove();
    } catch (error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-red-600 text-xs mt-2';
        errorDiv.textContent = 'Export failed: ' + (error.response?.data?.detail || 'Unknown error');
        
        const resultsContent = document.getElementById('resultsContent');
        if (resultsContent) {
            resultsContent.appendChild(errorDiv);
        } else {
            // Fallback to alert if no results content
            alert('Export failed: ' + (error.response?.data?.detail || 'Unknown error'));
        }
    }
}

// UI utilities
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const body = section.querySelector('.section-body');
    
    if (body.classList.contains('hidden')) {
        body.classList.remove('hidden');
        section.classList.remove('collapsed');
    } else {
        body.classList.add('hidden');
        section.classList.add('collapsed');
    }
}

// Add ARIA labels for accessibility
document.addEventListener('DOMContentLoaded', function() {
    // Add ARIA labels to form inputs
    const inputs = document.querySelectorAll('input, select, button');
    inputs.forEach(input => {
        if (!input.getAttribute('aria-label') && input.id) {
            input.setAttribute('aria-label', input.id.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()));
        }
    });
    
    // Add keyboard navigation support
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modal = document.getElementById('loginModal');
            if (!modal.classList.contains('hidden')) {
                hideLoginModal();
            }
        }
    });
});

})(); // End IIFE
