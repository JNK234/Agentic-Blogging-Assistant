// ABOUTME: UI rendering functions for the blogging application
// ABOUTME: Handles DOM updates, status messages, and content display

/**
 * Show a status message to the user
 */
function showStatus(message, type) {
    const el = document.getElementById('statusMessage');
    el.textContent = message;
    el.className = `status ${type}`;
    el.classList.remove('hidden');

    if (type === 'success' || type === 'info') {
        setTimeout(() => el.classList.add('hidden'), 5000);
    }
}

/**
 * Navigate to a workflow step
 */
function goToStep(step) {
    // Update step indicators
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    const stepEl = document.querySelector(`[data-step="${step}"]`);
    if (stepEl) stepEl.classList.add('active');

    // Show corresponding panel
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById(`${step}Panel`);
    if (panel) panel.classList.add('active');

    // Refresh panel content
    refreshPanelContent(step);
}

/**
 * Mark a step as completed
 */
function markStepCompleted(step) {
    const stepEl = document.querySelector(`[data-step="${step}"]`);
    if (stepEl) stepEl.classList.add('completed');
}

/**
 * Determine which step to show based on state
 */
function determineCurrentStep() {
    if (AppState.socialContent) {
        markStepCompleted('social');
        goToStep('social');
    } else if (AppState.refinedDraft) {
        markStepCompleted('refine');
        goToStep('social');
    } else if (AppState.compiledDraft) {
        markStepCompleted('compile');
        goToStep('refine');
    } else if (Object.keys(AppState.sections).length > 0) {
        markStepCompleted('outline');
        goToStep('draft');
    } else if (AppState.outline) {
        markStepCompleted('outline');
        goToStep('draft');
    } else if (AppState.processedHashes.notebook_hash || AppState.processedHashes.markdown_hash) {
        markStepCompleted('process');
        goToStep('outline');
    } else if (AppState.uploadedFiles.length > 0) {
        markStepCompleted('upload');
        goToStep('process');
    } else {
        goToStep('upload');
    }
}

/**
 * Refresh panel content based on current state
 */
function refreshPanelContent(step) {
    switch (step) {
        case 'process':
            renderUploadedFiles();
            break;
        case 'outline':
            if (AppState.outline) renderOutline();
            break;
        case 'draft':
            if (AppState.outline) renderDraftPanel();
            break;
        case 'compile':
            if (AppState.compiledDraft) {
                document.getElementById('compiledContent').textContent = AppState.compiledDraft;
                document.getElementById('compiledDraft').classList.remove('hidden');
            }
            break;
        case 'refine':
            if (AppState.refinedDraft) renderRefinedResult();
            break;
        case 'social':
            if (AppState.socialContent) renderSocialContent();
            break;
    }
    updateCostDisplay();
}

/**
 * Reset UI step states
 */
function resetStepUI() {
    document.querySelectorAll('.step').forEach(s => {
        s.classList.remove('completed', 'active');
    });
    document.querySelector('[data-step="upload"]').classList.add('active');

    // Reset all panel content
    document.getElementById('fileList').innerHTML = '';
    document.getElementById('uploadedFilesList').innerHTML = '';
    document.getElementById('outlineResult').classList.add('hidden');
    document.getElementById('compiledDraft').classList.add('hidden');
    document.getElementById('refinedResult').classList.add('hidden');
    document.getElementById('socialResult').classList.add('hidden');
}

/**
 * Render projects list in sidebar
 */
function renderProjects(projects) {
    const list = document.getElementById('projectList');

    if (!projects || !projects.length) {
        list.innerHTML = '<p style="color: #999; font-size: 0.85rem;">No projects yet</p>';
        return;
    }

    list.innerHTML = projects.map(p => {
        const isActive = AppState.currentProject === p.name;
        const safeName = BlogAPI.escapeHtml(p.name);
        const safeId = BlogAPI.escapeHtml(p.id);
        const safeMilestone = BlogAPI.escapeHtml(p.current_milestone || 'New');
        return `
            <div class="project-item ${isActive ? 'active' : ''}"
                 onclick="selectProject('${safeName}', '${safeId}')">
                <div class="name">${safeName}</div>
                <div class="status">${safeMilestone}</div>
            </div>
        `;
    }).join('');
}

/**
 * Render selected files for upload
 */
function renderSelectedFiles() {
    const list = document.getElementById('fileList');
    const files = StateManager.getSelectedFiles();
    list.innerHTML = files.map(f => `
        <div class="file-item">
            <span>${BlogAPI.escapeHtml(f.name)}</span>
            <span>${(f.size / 1024).toFixed(1)} KB</span>
        </div>
    `).join('');
}

/**
 * Render uploaded files list
 */
function renderUploadedFiles() {
    const list = document.getElementById('uploadedFilesList');
    if (!AppState.uploadedFiles.length) {
        list.innerHTML = '<p style="color: #999;">No files uploaded yet</p>';
        return;
    }
    list.innerHTML = AppState.uploadedFiles.map(f => `
        <div class="file-item">
            <span>${BlogAPI.escapeHtml(typeof f === 'string' ? f : f.name || f)}</span>
        </div>
    `).join('');
}

/**
 * Render the generated outline
 */
function renderOutline() {
    const container = document.getElementById('outlineResult');
    container.classList.remove('hidden');

    const outline = AppState.outline;
    if (!outline) return;

    const safeTitle = BlogAPI.escapeHtml(outline.title);
    const safeDifficulty = BlogAPI.escapeHtml(outline.difficulty_level);
    const safeIntro = BlogAPI.escapeHtml(outline.introduction);
    const safeConclusion = BlogAPI.escapeHtml(outline.conclusion);

    container.innerHTML = `
        <h4>${safeTitle}</h4>
        <p><strong>Difficulty:</strong> ${safeDifficulty}</p>
        <p><strong>Introduction:</strong> ${safeIntro}</p>

        <h4 style="margin-top: 15px;">Sections</h4>
        ${(outline.sections || []).map((s, i) => {
            const sectionTitle = BlogAPI.escapeHtml(s.title);
            const subsections = (s.subsections || []).map(sub =>
                `<li>${BlogAPI.escapeHtml(sub)}</li>`
            ).join('');
            return `
                <div class="outline-section">
                    <h4>${i + 1}. ${sectionTitle}</h4>
                    <ul>${subsections}</ul>
                    ${s.include_code ? '<span style="color: #27ae60; font-size: 0.8rem;">Includes code</span>' : ''}
                </div>
            `;
        }).join('')}

        <p><strong>Conclusion:</strong> ${safeConclusion}</p>

        <button class="btn btn-success" onclick="goToStep('draft')" style="margin-top: 15px;">
            Continue to Draft Generation
        </button>
    `;
}

/**
 * Render the draft generation panel
 */
function renderDraftPanel() {
    const outline = AppState.outline;
    if (!outline) return;

    // Summary
    document.getElementById('outlineSummary').innerHTML = `
        <strong>${BlogAPI.escapeHtml(outline.title)}</strong>
        <p style="color: #666;">${outline.sections?.length || 0} sections to generate</p>
    `;

    // Sections list
    const list = document.getElementById('sectionsList');
    list.innerHTML = (outline.sections || []).map((s, i) => {
        const section = AppState.sections[i];
        const status = section ? 'completed' : '';
        return `
            <div class="section-item ${status}">
                <div class="index">${i + 1}</div>
                <div class="title">${BlogAPI.escapeHtml(s.title)}</div>
                ${section ? '<span style="color: #27ae60;">Done</span>' : ''}
            </div>
        `;
    }).join('');

    // Progress
    const completed = Object.keys(AppState.sections).length;
    const total = outline.sections?.length || 0;
    const percent = total > 0 ? (completed / total) * 100 : 0;
    document.getElementById('draftProgressFill').style.width = `${percent}%`;
    document.getElementById('draftProgressText').textContent = `${completed} / ${total} sections`;
}

/**
 * Render the refined blog result
 */
function renderRefinedResult() {
    const container = document.getElementById('refinedResult');
    container.classList.remove('hidden');

    // Title options
    const titleContainer = document.getElementById('titleOptions');
    titleContainer.innerHTML = (AppState.titleOptions || []).map((t, i) => `
        <div style="padding: 10px; background: #f0f0f0; border-radius: 4px; margin-bottom: 8px;">
            <strong>Option ${i + 1}:</strong> ${BlogAPI.escapeHtml(t.title)}
            ${t.subtitle ? `<br><em>${BlogAPI.escapeHtml(t.subtitle)}</em>` : ''}
        </div>
    `).join('');

    document.getElementById('summaryContent').textContent = AppState.summary || '';
    document.getElementById('refinedContent').textContent = AppState.refinedDraft || '';
}

/**
 * Render social media content
 */
function renderSocialContent() {
    const container = document.getElementById('socialResult');
    container.classList.remove('hidden');

    const content = AppState.socialContent || {};

    document.getElementById('linkedinContent').textContent = content.linkedin_post || '';
    document.getElementById('twitterContent').textContent = content.x_post || '';
    document.getElementById('newsletterContent').textContent = content.newsletter_content || '';

    // Thread
    if (content.x_thread) {
        const thread = content.x_thread;
        document.getElementById('threadContent').innerHTML =
            (thread.tweets || []).map((t, i) => `
                <div style="padding: 10px; background: #f9f9f9; border-left: 3px solid #1da1f2; margin-bottom: 8px;">
                    <strong>${i + 1}/${thread.total_tweets}</strong>
                    <p>${BlogAPI.escapeHtml(t.content)}</p>
                </div>
            `).join('');
    }
}

/**
 * Switch social content tabs
 */
function showSocialTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    event.target.classList.add('active');
    document.getElementById(`${tab}Tab`).classList.add('active');
}

/**
 * Update cost display
 */
function updateCostDisplay() {
    document.getElementById('totalCost').textContent = `$${AppState.costSummary.total_cost.toFixed(4)}`;
    document.getElementById('totalTokens').textContent = AppState.costSummary.total_tokens.toLocaleString();
}

/**
 * Copy element text to clipboard
 */
function copyToClipboard(elementId) {
    const text = document.getElementById(elementId).textContent;
    navigator.clipboard.writeText(text).then(() => {
        showStatus('Copied to clipboard!', 'success');
    }).catch(() => {
        showStatus('Failed to copy', 'error');
    });
}

/**
 * Download the draft as markdown
 */
function downloadDraft() {
    const content = AppState.refinedDraft || AppState.compiledDraft;
    if (!content) {
        showStatus('No draft available to download', 'error');
        return;
    }

    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${AppState.currentProject || 'blog'}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

// Export for use in other modules
window.UI = {
    showStatus,
    goToStep,
    markStepCompleted,
    determineCurrentStep,
    refreshPanelContent,
    resetStepUI,
    renderProjects,
    renderSelectedFiles,
    renderUploadedFiles,
    renderOutline,
    renderDraftPanel,
    renderRefinedResult,
    renderSocialContent,
    showSocialTab,
    updateCostDisplay,
    copyToClipboard,
    downloadDraft
};
