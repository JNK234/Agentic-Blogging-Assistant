// ABOUTME: State management for the blogging application
// ABOUTME: Handles application state and persistence

const AppState = {
    currentProject: null,
    currentProjectId: null,
    uploadedFiles: [],
    processedHashes: {},
    outline: null,
    sections: {},
    compiledDraft: null,
    refinedDraft: null,
    summary: null,
    titleOptions: [],
    socialContent: null,
    costSummary: { total_cost: 0, total_tokens: 0 }
};

// Selected files for upload (not persisted)
let selectedFiles = [];

/**
 * Reset the workflow state for a new project
 */
function resetWorkflowState() {
    AppState.uploadedFiles = [];
    AppState.processedHashes = {};
    AppState.outline = null;
    AppState.sections = {};
    AppState.compiledDraft = null;
    AppState.refinedDraft = null;
    AppState.summary = null;
    AppState.titleOptions = [];
    AppState.socialContent = null;
    AppState.costSummary = { total_cost: 0, total_tokens: 0 };
    selectedFiles = [];
}

/**
 * Restore state from project milestones
 */
function restoreFromMilestones(milestones) {
    if (!Array.isArray(milestones)) return;

    milestones.forEach(m => {
        const data = m.data || {};
        switch (m.milestone_type) {
            case 'FILES_UPLOADED':
                AppState.uploadedFiles = data.files || data.uploaded_files || [];
                break;
            case 'OUTLINE_GENERATED':
                AppState.outline = data.outline;
                AppState.processedHashes = {
                    notebook_hash: data.notebook_hash,
                    markdown_hash: data.markdown_hash
                };
                break;
            case 'DRAFT_COMPLETED':
                AppState.compiledDraft = data.compiled_blog || data.compiled_draft;
                // Restore sections if available
                if (data.sections) {
                    AppState.sections = data.sections;
                }
                break;
            case 'BLOG_REFINED':
                AppState.refinedDraft = data.refined_content || data.refined_draft;
                AppState.summary = data.summary;
                AppState.titleOptions = data.title_options || [];
                break;
            case 'SOCIAL_GENERATED':
                AppState.socialContent = data.social_content || data;
                break;
        }
    });
}

/**
 * Restore state from project status endpoint (more complete data)
 */
function restoreFromProjectStatus(statusData) {
    if (statusData.outline) {
        AppState.outline = statusData.outline;
    }
    if (statusData.generated_sections) {
        // Convert string keys to integers
        AppState.sections = {};
        for (const [key, value] of Object.entries(statusData.generated_sections)) {
            AppState.sections[parseInt(key)] = value;
        }
    }
    if (statusData.final_draft) {
        AppState.compiledDraft = statusData.final_draft;
    }
    if (statusData.refined_draft) {
        AppState.refinedDraft = statusData.refined_draft;
    }
    if (statusData.summary) {
        AppState.summary = statusData.summary;
    }
    if (statusData.title_options) {
        AppState.titleOptions = statusData.title_options;
    }
    if (statusData.social_content) {
        AppState.socialContent = statusData.social_content;
    }
    if (statusData.cost_summary) {
        AppState.costSummary = statusData.cost_summary;
    }
}

/**
 * Update cost summary with new data
 */
function updateCostSummary(summary) {
    if (!summary) return;

    // Add to cumulative totals
    AppState.costSummary.total_cost += summary.total_cost || 0;
    AppState.costSummary.total_tokens += summary.total_tokens || 0;
}

/**
 * Get selected files for upload
 */
function getSelectedFiles() {
    return selectedFiles;
}

/**
 * Set selected files for upload
 */
function setSelectedFiles(files) {
    selectedFiles = files;
}

// Export for use in other modules
window.AppState = AppState;
window.StateManager = {
    resetWorkflowState,
    restoreFromMilestones,
    restoreFromProjectStatus,
    updateCostSummary,
    getSelectedFiles,
    setSelectedFiles
};
