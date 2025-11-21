// ABOUTME: API client for communicating with the FastAPI backend
// ABOUTME: Handles all HTTP requests with proper form data formatting

const API_BASE = 'http://localhost:8000';

/**
 * Escape HTML to prevent XSS attacks
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Create FormData from an object (for endpoints that use Form parameters)
 */
function createFormData(data) {
    const formData = new FormData();
    for (const [key, value] of Object.entries(data)) {
        if (value !== null && value !== undefined) {
            if (Array.isArray(value)) {
                value.forEach(v => formData.append(key, v));
            } else {
                formData.append(key, value);
            }
        }
    }
    return formData;
}

/**
 * Make a GET request
 */
async function apiGet(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || error.error || 'API Error');
    }
    return response.json();
}

/**
 * Make a POST request with Form data (for most endpoints)
 */
async function apiPostForm(endpoint, data = {}) {
    const formData = createFormData(data);
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        body: formData
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || error.error || 'API Error');
    }
    return response.json();
}

/**
 * Make a POST request with multipart form data (for file uploads)
 */
async function apiPostMultipart(endpoint, formData) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        body: formData
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || error.error || 'API Error');
    }
    return response.json();
}

/**
 * Make a POST request with no body (for endpoints that take no params)
 */
async function apiPost(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST'
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || error.error || 'API Error');
    }
    return response.json();
}

// API Functions

async function fetchProjects(status = null) {
    const endpoint = status ? `/projects?status=${status}` : '/projects';
    return apiGet(endpoint);
}

async function fetchProject(projectId) {
    return apiGet(`/project/${projectId}`);
}

async function fetchProjectStatus(projectId) {
    return apiGet(`/project_status/${projectId}`);
}

async function fetchModels() {
    return apiGet('/models');
}

async function fetchPersonas() {
    return apiGet('/personas');
}

async function uploadFiles(projectName, files, modelName, persona) {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    formData.append('model_name', modelName);
    formData.append('persona', persona);
    return apiPostMultipart(`/upload/${encodeURIComponent(projectName)}`, formData);
}

async function processFiles(projectName, modelName, filePaths) {
    return apiPostForm(`/process_files/${encodeURIComponent(projectName)}`, {
        model_name: modelName,
        file_paths: filePaths
    });
}

async function generateOutline(projectName, params) {
    return apiPostForm(`/generate_outline/${encodeURIComponent(projectName)}`, {
        model_name: params.modelName,
        notebook_hash: params.notebookHash,
        markdown_hash: params.markdownHash,
        user_guidelines: params.userGuidelines,
        length_preference: params.lengthPreference,
        writing_style: params.writingStyle,
        persona_style: params.persona
    });
}

async function generateSection(projectName, sectionIndex, maxIterations = 3, qualityThreshold = 0.8) {
    return apiPostForm(`/generate_section/${encodeURIComponent(projectName)}`, {
        section_index: sectionIndex,
        max_iterations: maxIterations,
        quality_threshold: qualityThreshold
    });
}

async function compileDraft(projectName, projectId) {
    return apiPostForm(`/compile_draft/${encodeURIComponent(projectName)}`, {
        job_id: projectId
    });
}

async function refineBlog(projectName, projectId, compiledDraft) {
    return apiPostForm(`/refine_blog/${encodeURIComponent(projectName)}`, {
        job_id: projectId,
        compiled_draft: compiledDraft
    });
}

async function generateSocialContent(projectName) {
    // This endpoint takes no body parameters
    return apiPost(`/generate_social_content/${encodeURIComponent(projectName)}`);
}

// Export for use in other modules
window.BlogAPI = {
    escapeHtml,
    fetchProjects,
    fetchProject,
    fetchProjectStatus,
    fetchModels,
    fetchPersonas,
    uploadFiles,
    processFiles,
    generateOutline,
    generateSection,
    compileDraft,
    refineBlog,
    generateSocialContent
};
