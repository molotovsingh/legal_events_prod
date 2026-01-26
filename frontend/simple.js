/**
 * Legal Events Extraction - Simple Interface
 * Wizard Flow UI with file management, drag-drop, and recent work
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

try { axios.defaults.baseURL = API_URL || undefined; } catch (_) {}

(function() {
'use strict';

// ============================================================================
// State Management
// ============================================================================

let authToken = localStorage.getItem('jwt_token');
let currentUser = null;
let currentRunId = null;
let pollInterval = null;
let selectedFiles = []; // Array of File objects for visual list

const TOKEN_KEY = 'jwt_token';
const TOKEN_EXPIRY_KEY = 'jwt_expiry';

// Persistent state
let lastClientId = localStorage.getItem('last_client_id');
let lastCaseId = localStorage.getItem('last_case_id');

// ============================================================================
// Token Management
// ============================================================================

function setAuthToken(token, expiresIn = 3600) {
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

// ============================================================================
// Axios Setup
// ============================================================================

axios.defaults.timeout = 30000;
axios.defaults.withCredentials = false;

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

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Setup UI event listeners
    setupEventListeners();

    // Render API badge
    renderApiBadge();

    // Load providers
    try {
        await loadProviders();
    } catch (error) {
        console.error('Failed to load providers:', error);
    }

    // Check auth status
    await checkAuthStatus();

    // Initialize dropdowns
    await initializeQuickStart();

    // Load recent work
    await loadRecentWork();
});

function setupEventListeners() {
    // Login modal
    const cancelLoginBtn = document.getElementById('cancelLoginBtn');
    const loginBtn = document.getElementById('loginBtn');
    if (cancelLoginBtn) cancelLoginBtn.addEventListener('click', hideLoginModal);
    if (loginBtn) loginBtn.addEventListener('click', handleLogin);

    // File input and drag-drop
    const fileInput = document.getElementById('fileInput');
    const folderInput = document.getElementById('folderInput');
    const dropZone = document.getElementById('dropZone');
    const selectFilesBtn = document.getElementById('selectFilesBtn');
    const selectFolderBtn = document.getElementById('selectFolderBtn');

    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }

    if (folderInput) {
        folderInput.addEventListener('change', handleFolderSelect);
    }

    if (selectFilesBtn) {
        selectFilesBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Select Files clicked');
            fileInput?.click();
        });
    }

    if (selectFolderBtn) {
        selectFolderBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Select Folder clicked');
            folderInput?.click();
        });
    }

    if (dropZone) {
        dropZone.addEventListener('dragover', handleDragOver);
        dropZone.addEventListener('dragleave', handleDragLeave);
        dropZone.addEventListener('drop', handleDrop);
    }

    // Client/Case dropdowns
    const clientSelect = document.getElementById('quickClientSelect');
    const caseSelect = document.getElementById('quickCaseSelect');

    if (clientSelect) {
        clientSelect.addEventListener('change', async (e) => {
            const clientId = e.target.value;
            if (clientId && clientId !== '__new__') {
                localStorage.setItem('last_client_id', clientId);
                lastClientId = clientId;
                await loadCases(clientId);
            } else {
                const cs = document.getElementById('quickCaseSelect');
                if (cs) {
                    cs.innerHTML = '<option value="">Select client first...</option>';
                    cs.disabled = true;
                }
            }
            updateButtonStates();
        });
    }

    if (caseSelect) {
        caseSelect.addEventListener('change', (e) => {
            const caseId = e.target.value;
            if (caseId && caseId !== '__new__') {
                localStorage.setItem('last_case_id', caseId);
                lastCaseId = caseId;
            }
            updateButtonStates();
        });
    }

    // Toggle buttons
    const toggleAdvanced = document.getElementById('toggleAdvanced');
    const toggleNewCase = document.getElementById('toggleNewCase');

    if (toggleAdvanced) {
        toggleAdvanced.addEventListener('click', () => toggleSection('advancedSettings', 'advancedIcon'));
    }

    if (toggleNewCase) {
        toggleNewCase.addEventListener('click', () => toggleSection('newCaseSection', 'newCaseIcon'));
    }

    // Create client/case buttons
    const createClientBtn = document.getElementById('createClientBtn');
    const createCaseBtn = document.getElementById('createCaseBtn');

    if (createClientBtn) createClientBtn.addEventListener('click', createClient);
    if (createCaseBtn) createCaseBtn.addEventListener('click', createCase);

    // Action buttons
    const estimateCostBtn = document.getElementById('estimateCostBtn');
    const startProcessingBtn = document.getElementById('startProcessingBtn');
    const refreshRecentBtn = document.getElementById('refreshRecentBtn');

    if (estimateCostBtn) estimateCostBtn.addEventListener('click', estimateCost);
    if (startProcessingBtn) startProcessingBtn.addEventListener('click', startProcessing);
    if (refreshRecentBtn) refreshRecentBtn.addEventListener('click', loadRecentWork);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('loginModal');
            if (modal && !modal.classList.contains('hidden')) {
                hideLoginModal();
            }
        }
    });
}

// ============================================================================
// API Badge
// ============================================================================

function renderApiBadge() {
    const el = document.getElementById('apiBadge');
    if (!el) return;
    el.textContent = API_URL ? `API: ${API_URL}` : 'API: local';
}

// ============================================================================
// Authentication
// ============================================================================

function showLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.remove('hidden');
}

function hideLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) modal.classList.add('hidden');
    // Clear fields
    const email = document.getElementById('loginEmail');
    const password = document.getElementById('loginPassword');
    const error = document.getElementById('loginError');
    if (email) email.value = '';
    if (password) password.value = '';
    if (error) error.classList.add('hidden');
}

async function handleLogin() {
    const email = document.getElementById('loginEmail')?.value.trim();
    const password = document.getElementById('loginPassword')?.value;
    const errorDiv = document.getElementById('loginError');
    const loginBtn = document.getElementById('loginBtn');

    if (errorDiv) {
        errorDiv.classList.add('hidden');
        errorDiv.textContent = '';
    }

    if (!email || !password) {
        if (errorDiv) {
            errorDiv.textContent = 'Email and password required';
            errorDiv.classList.remove('hidden');
        }
        return;
    }

    if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.textContent = 'Signing in...';
    }

    try {
        const response = await axios.post(`${API_URL}/v1/auth/login`, { email, password });
        const token = response.data.access_token;
        const expiresIn = response.data.expires_in || 3600;
        setAuthToken(token, expiresIn);
        currentUser = response.data.user || { email };

        hideLoginModal();
        updateAuthUI();

        // Reload data after login
        await loadProviders();
        await initializeQuickStart();
        await loadRecentWork();
    } catch (error) {
        if (errorDiv) {
            errorDiv.textContent = error.response?.data?.detail || 'Login failed';
            errorDiv.classList.remove('hidden');
        }
    } finally {
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.textContent = 'Sign In';
        }
    }
}

function handleLogout() {
    clearAuthToken();
    currentUser = null;
    selectedFiles = [];
    updateAuthUI();
    updateFileList();
    updateButtonStates();
}

async function checkAuthStatus() {
    if (!authToken || isTokenExpired()) {
        clearAuthToken();
        showLoginModal();
        return;
    }

    try {
        await axios.get(`${API_URL}/v1/auth/me`);
        currentUser = { authenticated: true };
        updateAuthUI();
    } catch (error) {
        handleLogout();
        showLoginModal();
    }
}

function updateAuthUI() {
    const authSection = document.getElementById('authSection');

    if (authToken && currentUser) {
        if (authSection) {
            authSection.innerHTML = `
                <button id="logoutBtn" class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded-lg transition">
                    Logout
                </button>
            `;
            document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);
        }
    } else {
        if (authSection) {
            authSection.innerHTML = `
                <button id="showLoginBtn" class="px-3 py-1.5 text-sm btn-primary rounded-lg">
                    Login
                </button>
            `;
            document.getElementById('showLoginBtn')?.addEventListener('click', showLoginModal);
        }
    }
}

// ============================================================================
// File Management
// ============================================================================

function handleFileSelect(e) {
    const files = Array.from(e.target.files || []);
    addFiles(files);
    // Reset input so same files can be re-selected
    e.target.value = '';
}

function handleFolderSelect(e) {
    console.log('Folder selected, files:', e.target.files?.length);
    const files = Array.from(e.target.files || []);
    console.log('Files to add:', files.map(f => f.name));
    // webkitRelativePath contains folder/subfolder/file.pdf
    addFiles(files);
    // Reset input so same folder can be re-selected
    e.target.value = '';
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    const dropZone = document.getElementById('dropZone');
    if (dropZone) dropZone.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    const dropZone = document.getElementById('dropZone');
    if (dropZone) dropZone.classList.remove('dragover');
}

async function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    const dropZone = document.getElementById('dropZone');
    if (dropZone) dropZone.classList.remove('dragover');

    const items = e.dataTransfer?.items;
    if (items && items.length > 0) {
        // Use DataTransferItem API to support folder drops
        const files = await getFilesFromDataTransferItems(items);
        addFiles(files);
    } else {
        // Fallback for older browsers
        const files = Array.from(e.dataTransfer?.files || []);
        addFiles(files);
    }
}

/**
 * Extract files from DataTransferItemList, recursively reading folders
 */
async function getFilesFromDataTransferItems(items) {
    const files = [];
    const entries = [];

    // Collect all entries first
    for (const item of items) {
        const entry = item.webkitGetAsEntry?.();
        if (entry) {
            entries.push(entry);
        }
    }

    // Read all entries (files and folders)
    for (const entry of entries) {
        const entryFiles = await readEntry(entry);
        files.push(...entryFiles);
    }

    return files;
}

/**
 * Recursively read a FileSystemEntry (file or directory)
 */
async function readEntry(entry) {
    if (entry.isFile) {
        return new Promise((resolve) => {
            entry.file(
                file => resolve([file]),
                () => resolve([])
            );
        });
    } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const allEntries = [];

        // readEntries may not return all entries in one call, so we loop
        const readBatch = () => {
            return new Promise((resolve) => {
                reader.readEntries(
                    entries => resolve(entries),
                    () => resolve([])
                );
            });
        };

        let batch;
        do {
            batch = await readBatch();
            allEntries.push(...batch);
        } while (batch.length > 0);

        // Recursively read all entries
        const files = [];
        for (const subEntry of allEntries) {
            const subFiles = await readEntry(subEntry);
            files.push(...subFiles);
        }
        return files;
    }
    return [];
}

function addFiles(files) {
    const validExtensions = ['pdf', 'txt', 'doc', 'docx', 'eml', 'rtf'];
    const maxSize = 10 * 1024 * 1024; // 10MB
    let skippedCount = 0;
    let addedCount = 0;

    for (const file of files) {
        // Check for duplicates (use webkitRelativePath if available for uniqueness)
        const fileKey = file.webkitRelativePath || file.name;
        if (selectedFiles.some(f => (f.webkitRelativePath || f.name) === fileKey && f.size === file.size)) {
            continue;
        }

        // Validate by extension (primary check - works for folder uploads)
        const ext = file.name.split('.').pop()?.toLowerCase();
        if (!validExtensions.includes(ext)) {
            skippedCount++;
            continue;
        }

        // Validate size
        if (file.size > maxSize) {
            skippedCount++;
            console.warn(`File too large: ${file.name} (${formatFileSize(file.size)}, max 10MB)`);
            continue;
        }

        selectedFiles.push(file);
        addedCount++;
    }

    // Show summary for folder uploads (multiple files)
    if (files.length > 1 && skippedCount > 0) {
        console.log(`Added ${addedCount} files, skipped ${skippedCount} (unsupported types or too large)`);
    }

    updateFileList();
    updateButtonStates();
    updateStepProgress();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
    updateButtonStates();
    updateStepProgress();
}

function updateFileList() {
    const fileList = document.getElementById('fileList');
    const fileCountLabel = document.getElementById('fileCountLabel');
    const fileBadge = document.getElementById('fileBadge');

    if (!fileList) return;

    fileList.innerHTML = '';

    if (selectedFiles.length === 0) {
        if (fileCountLabel) fileCountLabel.textContent = 'No files selected';
        if (fileBadge) fileBadge.classList.add('hidden');
        return;
    }

    // Calculate total size
    const totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
    const sizeStr = formatFileSize(totalSize);

    if (fileCountLabel) {
        fileCountLabel.textContent = `${selectedFiles.length} file${selectedFiles.length > 1 ? 's' : ''} • ${sizeStr}`;
    }

    if (fileBadge) {
        fileBadge.textContent = `${selectedFiles.length} file${selectedFiles.length > 1 ? 's' : ''}`;
        fileBadge.classList.remove('hidden');
    }

    // Render file items
    selectedFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'file-item flex items-center justify-between p-3 bg-gray-50 rounded-lg';

        const ext = file.name.split('.').pop()?.toLowerCase() || 'file';
        const icon = ext === 'pdf' ? '📄' : ext === 'doc' || ext === 'docx' ? '📝' : ext === 'eml' ? '📧' : '📃';

        // Show folder path if file came from a folder upload
        const relativePath = file.webkitRelativePath || '';
        const folderPath = relativePath ? relativePath.split('/').slice(0, -1).join('/') : '';
        const folderLabel = folderPath ? `<span class="text-gray-400 text-xs mr-1">📁 ${escapeHtml(folderPath)}/</span>` : '';

        item.innerHTML = `
            <div class="flex items-center flex-1 min-w-0">
                <span class="text-lg mr-3">${icon}</span>
                <div class="min-w-0">
                    <div class="font-medium text-sm text-gray-900 truncate">${folderLabel}${escapeHtml(file.name)}</div>
                    <div class="text-xs text-gray-500">${formatFileSize(file.size)}</div>
                </div>
            </div>
            <button class="remove-btn ml-3 w-6 h-6 flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition" data-index="${index}">
                ×
            </button>
        `;

        item.querySelector('.remove-btn')?.addEventListener('click', () => removeFile(index));
        fileList.appendChild(item);
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Step Progress
// ============================================================================

function updateStepProgress() {
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3');
    const stepLabel = document.getElementById('stepLabel');
    const stepPercent = document.getElementById('stepPercent');

    const hasFiles = selectedFiles.length > 0;
    const hasClient = document.getElementById('quickClientSelect')?.value &&
                      document.getElementById('quickClientSelect')?.value !== '__new__';
    const hasCase = document.getElementById('quickCaseSelect')?.value &&
                    document.getElementById('quickCaseSelect')?.value !== '__new__';

    let currentStep = 1;
    let percent = 0;

    if (hasFiles) {
        currentStep = 2;
        percent = 33;
    }

    if (hasFiles && hasClient && hasCase) {
        currentStep = 3;
        percent = 66;
    }

    // Update step indicators
    if (step1) {
        step1.className = 'step-indicator flex-1 h-2 rounded-full ' +
            (currentStep >= 1 ? 'step-active' : 'step-pending');
    }
    if (step2) {
        step2.className = 'step-indicator flex-1 h-2 rounded-full ' +
            (currentStep >= 2 ? 'step-active' : 'step-pending');
    }
    if (step3) {
        step3.className = 'step-indicator flex-1 h-2 rounded-full ' +
            (currentStep >= 3 ? 'step-active' : 'step-pending');
    }

    // Update labels
    const steps = [
        'Step 1 of 3: Select Documents',
        'Step 2 of 3: Configure Settings',
        'Step 3 of 3: Ready to Process'
    ];

    if (stepLabel) stepLabel.textContent = steps[currentStep - 1];
    if (stepPercent) stepPercent.textContent = `${percent}%`;
}

// ============================================================================
// Button States
// ============================================================================

function updateButtonStates() {
    const hasFiles = selectedFiles.length > 0;
    const hasClient = document.getElementById('quickClientSelect')?.value &&
                      document.getElementById('quickClientSelect')?.value !== '__new__';
    const hasCase = document.getElementById('quickCaseSelect')?.value &&
                    document.getElementById('quickCaseSelect')?.value !== '__new__';

    const estimateCostBtn = document.getElementById('estimateCostBtn');
    const startProcessingBtn = document.getElementById('startProcessingBtn');

    if (estimateCostBtn) {
        estimateCostBtn.disabled = !hasFiles;
    }

    if (startProcessingBtn) {
        startProcessingBtn.disabled = !(hasFiles && hasClient && hasCase);
    }

    updateStepProgress();
}

// ============================================================================
// Providers & Models
// ============================================================================

let providersLoaded = false;

async function loadProviders() {
    try {
        const response = await axios.get(`${API_URL}/v1/providers`);
        const providerSelect = document.getElementById('providerSelect');
        if (!providerSelect) return;

        providerSelect.innerHTML = '';

        response.data.providers.forEach(provider => {
            const option = document.createElement('option');
            option.value = provider.provider_id;
            option.textContent = `${provider.display_name}${provider.recommended ? ' ⭐' : ''}`;
            providerSelect.appendChild(option);
        });

        if (response.data.providers.length > 0) {
            const defaultProvider = response.data.providers.find(p => p.recommended) || response.data.providers[0];
            providerSelect.value = defaultProvider.provider_id;
            await loadModels(defaultProvider.provider_id);
        }

        if (!providersLoaded) {
            providerSelect.addEventListener('change', (e) => loadModels(e.target.value));
            providersLoaded = true;
        }
    } catch (error) {
        console.error('Failed to load providers:', error);
    }
}

async function loadModels(providerKey) {
    try {
        const response = await axios.get(`${API_URL}/v1/models?provider=${providerKey}`);
        const modelSelect = document.getElementById('modelSelect');
        if (!modelSelect) return;

        modelSelect.innerHTML = '';

        if (response.data.models?.length > 0) {
            response.data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.model_id;
                option.textContent = `${model.display_name}${model.is_recommended ? ' ⭐' : ''}`;
                modelSelect.appendChild(option);
            });

            const recommended = response.data.models.find(m => m.is_recommended);
            if (recommended) {
                modelSelect.value = recommended.model_id;
            }
        } else {
            modelSelect.innerHTML = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

// ============================================================================
// Clients & Cases
// ============================================================================

async function loadClients() {
    const clientSelect = document.getElementById('quickClientSelect');
    if (!clientSelect) return [];

    try {
        const response = await axios.get(`${API_URL}/v1/clients`);
        const clients = response.data || [];

        clientSelect.innerHTML = '<option value="">Select client...</option>';
        clientSelect.innerHTML += '<option value="__new__">+ Create New Client</option>';

        clients.forEach(client => {
            const option = document.createElement('option');
            option.value = client.id;
            option.textContent = client.name;
            clientSelect.appendChild(option);
        });

        if (lastClientId && clients.some(c => c.id === parseInt(lastClientId))) {
            clientSelect.value = lastClientId;
        }

        return clients;
    } catch (error) {
        console.error('Failed to load clients:', error);
        clientSelect.innerHTML = '<option value="">Failed to load</option>';
        return [];
    }
}

async function loadCases(clientId) {
    const caseSelect = document.getElementById('quickCaseSelect');
    if (!caseSelect) return [];

    if (!clientId || clientId === '__new__') {
        caseSelect.innerHTML = '<option value="">Select client first...</option>';
        caseSelect.disabled = true;
        return [];
    }

    caseSelect.innerHTML = '<option value="">Loading...</option>';
    caseSelect.disabled = true;

    try {
        const response = await axios.get(`${API_URL}/v1/clients/${clientId}/cases`);
        const cases = response.data || [];

        caseSelect.innerHTML = '<option value="">Select case...</option>';
        caseSelect.innerHTML += '<option value="__new__">+ Create New Case</option>';

        cases.forEach(c => {
            const option = document.createElement('option');
            option.value = c.id;
            option.textContent = c.name;
            caseSelect.appendChild(option);
        });

        caseSelect.disabled = false;

        if (lastCaseId && cases.some(c => c.id === parseInt(lastCaseId))) {
            caseSelect.value = lastCaseId;
        }

        return cases;
    } catch (error) {
        console.error('Failed to load cases:', error);
        caseSelect.innerHTML = '<option value="">Failed to load</option>';
        caseSelect.disabled = false;
        return [];
    }
}

async function initializeQuickStart() {
    await loadClients();
    if (lastClientId) {
        await loadCases(lastClientId);
    }
    updateButtonStates();
}

async function createClient() {
    const clientName = document.getElementById('clientName')?.value.trim();
    const statusDiv = document.getElementById('clientStatus');

    if (!clientName) {
        if (statusDiv) statusDiv.innerHTML = '<span class="text-red-600">Client name required</span>';
        return;
    }

    if (statusDiv) statusDiv.innerHTML = '<span class="text-blue-600"><span class="spinner"></span> Creating...</span>';

    try {
        const response = await axios.post(`${API_URL}/v1/clients`, { name: clientName });
        lastClientId = response.data.id;
        localStorage.setItem('last_client_id', lastClientId);

        if (statusDiv) statusDiv.innerHTML = `<span class="text-green-600">Created! ID: ${lastClientId}</span>`;

        // Refresh clients and select the new one
        await loadClients();
        const clientSelect = document.getElementById('quickClientSelect');
        if (clientSelect) clientSelect.value = lastClientId;
        await loadCases(lastClientId);

        // Clear input
        const input = document.getElementById('clientName');
        if (input) input.value = '';

        updateButtonStates();
    } catch (error) {
        if (statusDiv) statusDiv.innerHTML = `<span class="text-red-600">${error.response?.data?.detail || 'Failed'}</span>`;
    }
}

async function createCase() {
    const caseName = document.getElementById('caseName')?.value.trim();
    const statusDiv = document.getElementById('caseStatus');
    const clientId = document.getElementById('quickClientSelect')?.value;

    if (!clientId || clientId === '__new__') {
        if (statusDiv) statusDiv.innerHTML = '<span class="text-red-600">Select a client first</span>';
        return;
    }

    if (!caseName) {
        if (statusDiv) statusDiv.innerHTML = '<span class="text-red-600">Case name required</span>';
        return;
    }

    if (statusDiv) statusDiv.innerHTML = '<span class="text-blue-600"><span class="spinner"></span> Creating...</span>';

    try {
        const response = await axios.post(`${API_URL}/v1/cases`, {
            client_id: parseInt(clientId),
            name: caseName
        });
        lastCaseId = response.data.id;
        localStorage.setItem('last_case_id', lastCaseId);

        if (statusDiv) statusDiv.innerHTML = `<span class="text-green-600">Created! ID: ${lastCaseId}</span>`;

        // Refresh cases and select the new one
        await loadCases(clientId);
        const caseSelect = document.getElementById('quickCaseSelect');
        if (caseSelect) caseSelect.value = lastCaseId;

        // Clear input
        const input = document.getElementById('caseName');
        if (input) input.value = '';

        updateButtonStates();
    } catch (error) {
        if (statusDiv) statusDiv.innerHTML = `<span class="text-red-600">${error.response?.data?.detail || 'Failed'}</span>`;
    }
}

// ============================================================================
// Cost Estimation
// ============================================================================

async function estimateCost() {
    if (selectedFiles.length === 0) return;

    const costEstimate = document.getElementById('costEstimate');
    const costValue = document.getElementById('costValue');
    const tokenCount = document.getElementById('tokenCount');
    const btn = document.getElementById('estimateCostBtn');

    if (costEstimate) costEstimate.classList.remove('hidden');
    if (costValue) costValue.textContent = 'Calculating...';
    if (tokenCount) tokenCount.textContent = '';
    if (btn) btn.disabled = true;

    // Get settings
    const useSmartProvider = document.getElementById('useSmartProvider')?.checked !== false;
    const useLocalOCR = document.getElementById('useLocalOCR')?.checked !== false;
    const provider = useSmartProvider ? 'openrouter' : (document.getElementById('providerSelect')?.value || 'openrouter');
    const model = useSmartProvider ? 'meta-llama/llama-3.3-70b-instruct' : (document.getElementById('modelSelect')?.value || 'meta-llama/llama-3.3-70b-instruct');
    const docExtractor = useLocalOCR ? 'docling' : (document.getElementById('docExtractorSelect')?.value || 'docling');

    let uploaded = [];

    try {
        // Upload files temporarily
        const formData = new FormData();
        for (const file of selectedFiles) {
            formData.append('files', file);
        }

        const uploadResp = await axios.post(`${API_URL}/v1/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });

        uploaded = uploadResp.data.files || [];

        if (uploaded.length === 0) {
            if (costValue) costValue.textContent = 'Upload failed';
            return;
        }

        // Request estimate
        const filesPayload = uploaded.map(u => ({
            filename: u.filename,
            storage_key: u.storage_path,
            size_bytes: u.size_bytes,
            mime_type: u.mime_type
        }));

        const estResp = await axios.post(`${API_URL}/v1/estimate-tokens`, {
            provider,
            model,
            doc_extractor: docExtractor,
            files: filesPayload,
            enable_classification: document.getElementById('enableClassification')?.checked || false
        });

        const totals = estResp.data.totals;
        const cost = totals.cost_input_usd != null ? `$${totals.cost_input_usd.toFixed(4)}` : 'N/A';
        const tokens = totals.total_input_tokens.toLocaleString();

        if (costValue) costValue.textContent = cost;
        if (tokenCount) tokenCount.textContent = `${tokens} tokens`;

    } catch (error) {
        console.error('Estimate error:', error);
        if (costValue) costValue.textContent = error.response?.data?.detail || 'Failed';
    } finally {
        if (btn) btn.disabled = false;

        // Cleanup temp files
        if (uploaded.length > 0) {
            const keys = uploaded.map(u => u.storage_path).filter(Boolean);
            if (keys.length > 0) {
                try {
                    await axios.post(`${API_URL}/v1/uploads/cleanup`, { keys });
                } catch (e) {
                    console.warn('Cleanup failed:', e);
                }
            }
        }
    }
}

// ============================================================================
// Processing
// ============================================================================

async function startProcessing() {
    const caseId = document.getElementById('quickCaseSelect')?.value;

    if (!caseId || caseId === '__new__' || selectedFiles.length === 0) {
        alert('Please select a case and add files');
        return;
    }

    // Get settings
    const useSmartProvider = document.getElementById('useSmartProvider')?.checked !== false;
    const useLocalOCR = document.getElementById('useLocalOCR')?.checked !== false;
    const provider = useSmartProvider ? 'openrouter' : (document.getElementById('providerSelect')?.value || 'openrouter');
    const model = useSmartProvider ? 'meta-llama/llama-3.3-70b-instruct' : (document.getElementById('modelSelect')?.value || 'meta-llama/llama-3.3-70b-instruct');
    const docExtractor = useLocalOCR ? 'docling' : (document.getElementById('docExtractorSelect')?.value || 'docling');

    const btn = document.getElementById('startProcessingBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Starting...';
    }

    try {
        // Create run
        const runCreate = await axios.post(`${API_URL}/v1/runs`, {
            case_id: parseInt(caseId),
            provider,
            model,
            doc_extractor: docExtractor,
            enable_classification: document.getElementById('enableClassification')?.checked || false
        });

        currentRunId = runCreate.data.run_id;

        // Upload files
        const manifest = [];
        for (const file of selectedFiles) {
            const fd = new FormData();
            fd.append('file', file);

            const upResp = await axios.put(`${API_URL}/v1/runs/${currentRunId}/upload`, fd, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const sha = await calculateFileSHA256(file).catch(() => '');
            manifest.push({
                filename: file.name,
                size_bytes: file.size,
                sha256: sha,
                storage_key: upResp.data.storage_key,
                mime_type: file.type || 'application/pdf'
            });
        }

        // Start processing
        await axios.put(`${API_URL}/v1/runs/${currentRunId}/start`, { files: manifest });

        // Show processing section
        showProcessingSection();
        startPolling();

    } catch (error) {
        console.error('Processing error:', error);
        alert(error.response?.data?.detail || 'Failed to start processing');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span class="mr-2">🚀</span> Start Processing';
        }
    }
}

async function calculateFileSHA256(file) {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// ============================================================================
// Processing Status & Polling
// ============================================================================

function showProcessingSection() {
    const section = document.getElementById('processingSection');
    if (section) {
        section.classList.remove('hidden');
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(refreshStatus, 2000);
    refreshStatus();
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

async function refreshStatus() {
    if (!currentRunId) return;

    try {
        const response = await axios.get(`${API_URL}/v1/runs/${currentRunId}`);
        const run = response.data;

        const processingStatus = document.getElementById('processingStatus');
        const processingBadge = document.getElementById('processingBadge');
        const processingDocLabel = document.getElementById('processingDocLabel');
        const processingPercent = document.getElementById('processingPercent');
        const processingProgressBar = document.getElementById('processingProgressBar');

        const counts = run.counts || {};
        const total = counts.total || 0;
        const processed = counts.processed || 0;
        const failed = counts.failed || 0;
        const pending = counts.pending || 0;
        const done = processed + failed;
        const percent = total > 0 ? Math.round((done / total) * 100) : 0;

        if (processingDocLabel) processingDocLabel.textContent = `${done} of ${total} documents processed`;
        if (processingPercent) processingPercent.textContent = `${percent}%`;
        if (processingProgressBar) processingProgressBar.style.width = `${percent}%`;

        // Update status
        if (run.status === 'success' || run.status === 'completed') {
            if (processingStatus) processingStatus.textContent = 'Complete!';
            if (processingBadge) {
                processingBadge.textContent = 'Complete';
                processingBadge.className = 'badge badge-green';
            }
            if (processingProgressBar) processingProgressBar.classList.add('bg-green-500');
            stopPolling();
            showResults(run);
        } else if (run.status === 'failed') {
            if (processingStatus) processingStatus.textContent = 'Failed';
            if (processingBadge) {
                processingBadge.textContent = 'Failed';
                processingBadge.className = 'badge badge-red';
            }
            if (processingProgressBar) processingProgressBar.classList.add('bg-red-500');
            stopPolling();
        } else if (run.status === 'partial' || run.status === 'partial_success') {
            if (processingStatus) processingStatus.textContent = 'Partial success';
            if (processingBadge) {
                processingBadge.textContent = 'Partial';
                processingBadge.className = 'badge badge-yellow';
            }
            stopPolling();
            showResults(run);
        } else {
            if (processingStatus) processingStatus.textContent = `Processing... ${pending} remaining`;
        }

    } catch (error) {
        console.error('Status refresh error:', error);
    }
}

function showResults(run) {
    const section = document.getElementById('resultsSection');
    const content = document.getElementById('resultsContent');
    const badge = document.getElementById('resultsBadge');
    const status = document.getElementById('resultsStatus');

    if (section) section.classList.remove('hidden');

    const counts = run.counts || {};
    const timings = run.timings || {};

    if (status) {
        status.textContent = `${counts.processed || 0} documents processed`;
    }

    if (badge) {
        if (run.status === 'success' || run.status === 'completed') {
            badge.textContent = 'Complete';
            badge.className = 'badge badge-green';
        } else if (run.status === 'partial' || run.status === 'partial_success') {
            badge.textContent = 'Partial';
            badge.className = 'badge badge-yellow';
        }
    }

    if (content) {
        content.innerHTML = `
            <div class="grid grid-cols-2 gap-4 mb-4">
                <div class="bg-gray-50 rounded-lg p-3">
                    <div class="text-xs text-gray-500">Documents</div>
                    <div class="text-lg font-semibold text-gray-900">${counts.processed || 0} / ${counts.total || 0}</div>
                </div>
                <div class="bg-gray-50 rounded-lg p-3">
                    <div class="text-xs text-gray-500">Processing Time</div>
                    <div class="text-lg font-semibold text-gray-900">${timings.total_seconds ? timings.total_seconds.toFixed(1) + 's' : 'N/A'}</div>
                </div>
            </div>
            ${run.cost_usd ? `<div class="text-sm text-gray-600 mb-4">Cost: $${run.cost_usd.toFixed(4)}</div>` : ''}
        `;
    }

    section?.scrollIntoView({ behavior: 'smooth' });

    // Refresh recent work
    loadRecentWork();
}

// ============================================================================
// Recent Work
// ============================================================================

async function loadRecentWork() {
    const list = document.getElementById('recentWorkList');
    if (!list) return;

    if (!authToken) {
        list.innerHTML = '<div class="text-sm text-gray-500 text-center py-4">Login to see recent work</div>';
        return;
    }

    try {
        const response = await axios.get(`${API_URL}/v1/runs?limit=5&order_by=created_at&order=desc`);
        const runs = response.data.runs || [];

        if (runs.length === 0) {
            list.innerHTML = '<div class="text-sm text-gray-500 text-center py-4">No recent runs</div>';
            return;
        }

        list.innerHTML = '';

        runs.forEach(run => {
            const item = document.createElement('div');
            item.className = 'recent-item flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer';

            const statusIcon = run.status === 'success' || run.status === 'completed' ? '🟢' :
                              run.status === 'processing' ? '🟡' :
                              run.status === 'failed' ? '🔴' : '⚪';

            const counts = run.counts || {};
            const timeAgo = getTimeAgo(run.created_at);

            item.innerHTML = `
                <div class="flex items-center min-w-0">
                    <span class="mr-3">${statusIcon}</span>
                    <div class="min-w-0">
                        <div class="font-medium text-sm text-gray-900">Run #${run.run_id}</div>
                        <div class="text-xs text-gray-500">${counts.total || 0} docs • ${timeAgo}</div>
                    </div>
                </div>
                <div class="text-xs text-gray-500">${run.status}</div>
            `;

            item.addEventListener('click', () => {
                currentRunId = run.run_id;
                showProcessingSection();
                refreshStatus();
                if (run.status === 'processing') {
                    startPolling();
                }
            });

            list.appendChild(item);
        });

    } catch (error) {
        console.error('Failed to load recent work:', error);
        list.innerHTML = '<div class="text-sm text-gray-500 text-center py-4">Failed to load</div>';
    }
}

function getTimeAgo(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

// ============================================================================
// Export
// ============================================================================

async function exportData(format) {
    if (!currentRunId) return;

    try {
        const response = await axios.get(`${API_URL}/v1/runs/${currentRunId}/export?fmt=${format}`, {
            responseType: 'blob'
        });

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
        alert('Export failed: ' + (error.response?.data?.detail || 'Unknown error'));
    }
}

// ============================================================================
// UI Utilities
// ============================================================================

function toggleSection(sectionId, iconId) {
    const section = document.getElementById(sectionId);
    const icon = document.getElementById(iconId);

    if (section) {
        section.classList.toggle('hidden');
        if (icon) {
            icon.textContent = section.classList.contains('hidden') ? '▶' : '▼';
        }
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', stopPolling);

document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopPolling();
    } else if (currentRunId) {
        const processingSection = document.getElementById('processingSection');
        if (processingSection && !processingSection.classList.contains('hidden')) {
            startPolling();
        }
    }
});

// ============================================================================
// Global Exports
// ============================================================================

window.showLoginModal = showLoginModal;
window.hideLoginModal = hideLoginModal;
window.handleLogin = handleLogin;
window.handleLogout = handleLogout;
window.exportData = exportData;

})();
