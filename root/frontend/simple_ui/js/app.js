// ABOUTME: Main application logic for the blogging assistant
// ABOUTME: Coordinates API calls, state management, and UI updates

/**
 * Initialize the application
 */
async function initApp() {
    try {
        await Promise.all([
            loadProjects(),
            loadModelsAndPersonas()
        ]);
    } catch (error) {
        console.error('Initialization failed:', error);
        UI.showStatus('Failed to initialize. Is the backend running?', 'error');
    }
}

/**
 * Load and display projects
 */
async function loadProjects() {
    try {
        const data = await BlogAPI.fetchProjects();
        UI.renderProjects(data.projects || []);
    } catch (error) {
        console.error('Failed to load projects:', error);
    }
}

/**
 * Load available models and personas
 */
async function loadModelsAndPersonas() {
    try {
        const [models, personas] = await Promise.all([
            BlogAPI.fetchModels(),
            BlogAPI.fetchPersonas()
        ]);

        // Populate model select
        const modelSelect = document.getElementById('modelSelect');
        modelSelect.innerHTML = '';
        for (const [provider, modelList] of Object.entries(models)) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = provider;
            modelList.forEach(m => {
                const option = document.createElement('option');
                option.value = provider;
                option.textContent = m;
                optgroup.appendChild(option);
            });
            modelSelect.appendChild(optgroup);
        }

        // Populate persona select
        const personaSelect = document.getElementById('personaSelect');
        personaSelect.innerHTML = '';
        for (const [name, desc] of Object.entries(personas)) {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = `${name} - ${desc}`;
            personaSelect.appendChild(option);
        }
    } catch (error) {
        console.error('Failed to load config:', error);
    }
}

/**
 * Create a new project
 */
async function createProject() {
    const input = document.getElementById('newProjectName');
    const name = input.value.trim();

    if (!name) {
        UI.showStatus('Please enter a project name', 'error');
        return;
    }

    // Set state for new project
    AppState.currentProject = name;
    AppState.currentProjectId = null;
    StateManager.resetWorkflowState();
    UI.resetStepUI();

    document.getElementById('noProjectMessage').classList.add('hidden');
    document.getElementById('workflowContainer').classList.remove('hidden');

    input.value = '';
    UI.goToStep('upload');
    UI.showStatus(`Project "${name}" created. Upload files to continue.`, 'success');
}

/**
 * Select an existing project
 */
async function selectProject(name, id) {
    AppState.currentProject = name;
    AppState.currentProjectId = id;
    StateManager.resetWorkflowState();
    UI.resetStepUI();

    document.getElementById('noProjectMessage').classList.add('hidden');
    document.getElementById('workflowContainer').classList.remove('hidden');

    try {
        UI.showStatus('Loading project...', 'loading');

        // Try to get full project status which has more complete data
        const statusData = await BlogAPI.fetchProjectStatus(id);
        StateManager.restoreFromProjectStatus(statusData);

        // Also load project milestones for any missing data
        const project = await BlogAPI.fetchProject(id);
        if (project.milestones) {
            StateManager.restoreFromMilestones(project.milestones);
        }

        // Update uploaded files from project metadata
        if (project.metadata?.uploaded_files) {
            AppState.uploadedFiles = project.metadata.uploaded_files;
        }

        // Update UI
        loadProjects();
        UI.determineCurrentStep();
        UI.showStatus(`Project "${name}" loaded`, 'success');

    } catch (error) {
        console.error('Failed to load project:', error);
        UI.showStatus(`Failed to load project: ${error.message}`, 'error');
    }
}

/**
 * Handle file selection
 */
function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    StateManager.setSelectedFiles(files);
    UI.renderSelectedFiles();
    document.getElementById('uploadBtn').disabled = files.length === 0;
}

/**
 * Upload selected files
 */
async function uploadFiles() {
    const files = StateManager.getSelectedFiles();
    if (!files.length || !AppState.currentProject) return;

    const model = document.getElementById('modelSelect').value;
    const persona = document.getElementById('personaSelect').value;

    UI.showStatus('Uploading files...', 'loading');
    document.getElementById('uploadBtn').disabled = true;

    try {
        const data = await BlogAPI.uploadFiles(AppState.currentProject, files, model, persona);

        AppState.currentProjectId = data.project_id;
        // Response uses 'files' field
        AppState.uploadedFiles = data.files || [];

        UI.showStatus('Files uploaded successfully!', 'success');
        UI.markStepCompleted('upload');
        loadProjects();
        UI.goToStep('process');

    } catch (error) {
        UI.showStatus(`Upload failed: ${error.message}`, 'error');
    } finally {
        document.getElementById('uploadBtn').disabled = false;
    }
}

/**
 * Process uploaded files
 */
async function processFiles() {
    if (!AppState.currentProject || !AppState.uploadedFiles.length) {
        UI.showStatus('No files to process', 'error');
        return;
    }

    const model = document.getElementById('modelSelect').value;

    UI.showStatus('Processing files... This may take a moment.', 'loading');
    document.getElementById('processBtn').disabled = true;

    try {
        const data = await BlogAPI.processFiles(
            AppState.currentProject,
            model,
            AppState.uploadedFiles
        );

        // Response returns file_hashes dict
        const hashes = data.file_hashes || {};
        // Extract hashes by file type
        AppState.processedHashes = {
            notebook_hash: null,
            markdown_hash: null
        };

        for (const [filepath, hash] of Object.entries(hashes)) {
            if (filepath.endsWith('.ipynb')) {
                AppState.processedHashes.notebook_hash = hash;
            } else if (filepath.endsWith('.md')) {
                AppState.processedHashes.markdown_hash = hash;
            }
        }

        UI.showStatus('Files processed successfully!', 'success');
        UI.markStepCompleted('process');
        UI.goToStep('outline');

    } catch (error) {
        UI.showStatus(`Processing failed: ${error.message}`, 'error');
    } finally {
        document.getElementById('processBtn').disabled = false;
    }
}

/**
 * Generate blog outline
 */
async function generateOutline() {
    if (!AppState.currentProject) return;

    const model = document.getElementById('modelSelect').value;
    const persona = document.getElementById('personaSelect').value;

    if (!AppState.processedHashes.notebook_hash && !AppState.processedHashes.markdown_hash) {
        UI.showStatus('Please process files first', 'error');
        return;
    }

    UI.showStatus('Generating outline... This may take a moment.', 'loading');
    document.getElementById('outlineBtn').disabled = true;

    try {
        const data = await BlogAPI.generateOutline(AppState.currentProject, {
            modelName: model,
            notebookHash: AppState.processedHashes.notebook_hash,
            markdownHash: AppState.processedHashes.markdown_hash,
            userGuidelines: document.getElementById('userGuidelines').value,
            lengthPreference: document.getElementById('lengthPreference').value,
            writingStyle: document.getElementById('writingStyle').value,
            persona: persona
        });

        // Update project ID if returned
        if (data.project_id) {
            AppState.currentProjectId = data.project_id;
        }

        AppState.outline = data.outline;
        StateManager.updateCostSummary(data.cost_summary);

        UI.renderOutline();
        UI.updateCostDisplay();
        UI.showStatus('Outline generated successfully!', 'success');
        UI.markStepCompleted('outline');

    } catch (error) {
        UI.showStatus(`Outline generation failed: ${error.message}`, 'error');
    } finally {
        document.getElementById('outlineBtn').disabled = false;
    }
}

/**
 * Generate all blog sections
 */
async function generateAllSections() {
    if (!AppState.outline) return;

    const total = AppState.outline.sections?.length || 0;
    document.getElementById('generateSectionsBtn').disabled = true;
    document.getElementById('generateNextBtn').disabled = true;

    for (let i = 0; i < total; i++) {
        if (AppState.sections[i]) continue; // Skip completed
        await generateSection(i);
    }

    UI.showStatus('All sections generated!', 'success');
    UI.markStepCompleted('draft');
    document.getElementById('generateSectionsBtn').disabled = false;
    document.getElementById('generateNextBtn').disabled = false;
    UI.goToStep('compile');
}

/**
 * Generate next incomplete section
 */
async function generateNextSection() {
    if (!AppState.outline) return;

    const total = AppState.outline.sections?.length || 0;
    for (let i = 0; i < total; i++) {
        if (!AppState.sections[i]) {
            await generateSection(i);

            // Check if all done
            if (Object.keys(AppState.sections).length === total) {
                UI.showStatus('All sections generated!', 'success');
                UI.markStepCompleted('draft');
            }
            return;
        }
    }

    UI.showStatus('All sections already generated!', 'info');
}

/**
 * Generate a single section
 */
async function generateSection(index) {
    UI.showStatus(`Generating section ${index + 1}...`, 'loading');

    // Update UI to show generating
    const items = document.querySelectorAll('.section-item');
    if (items[index]) items[index].classList.add('generating');

    try {
        const data = await BlogAPI.generateSection(
            AppState.currentProject,
            index,
            3,  // max_iterations
            0.8 // quality_threshold
        );

        AppState.sections[index] = {
            title: data.section_title,
            content: data.section_content
        };

        StateManager.updateCostSummary(data.cost_summary);
        UI.renderDraftPanel();
        UI.updateCostDisplay();
        UI.showStatus(`Section ${index + 1} generated!`, 'success');

    } catch (error) {
        UI.showStatus(`Section generation failed: ${error.message}`, 'error');
        if (items[index]) items[index].classList.remove('generating');
    }
}

/**
 * Compile all sections into a draft
 */
async function compileDraft() {
    if (!AppState.currentProject || !AppState.currentProjectId) {
        UI.showStatus('No project selected', 'error');
        return;
    }

    // Check if all sections are generated
    const total = AppState.outline?.sections?.length || 0;
    const generated = Object.keys(AppState.sections).length;
    if (generated < total) {
        UI.showStatus(`Please generate all sections first (${generated}/${total} complete)`, 'error');
        return;
    }

    UI.showStatus('Compiling draft...', 'loading');
    document.getElementById('compileBtn').disabled = true;

    try {
        const data = await BlogAPI.compileDraft(
            AppState.currentProject,
            AppState.currentProjectId
        );

        AppState.compiledDraft = data.draft;
        StateManager.updateCostSummary(data.cost_summary);

        document.getElementById('compiledContent').textContent = AppState.compiledDraft;
        document.getElementById('compiledDraft').classList.remove('hidden');

        UI.updateCostDisplay();
        UI.showStatus('Draft compiled successfully!', 'success');
        UI.markStepCompleted('compile');

    } catch (error) {
        UI.showStatus(`Compilation failed: ${error.message}`, 'error');
    } finally {
        document.getElementById('compileBtn').disabled = false;
    }
}

/**
 * Refine the blog draft
 */
async function refineBlog() {
    if (!AppState.currentProject || !AppState.currentProjectId) {
        UI.showStatus('No project selected', 'error');
        return;
    }

    if (!AppState.compiledDraft) {
        UI.showStatus('Please compile the draft first', 'error');
        return;
    }

    UI.showStatus('Refining blog...', 'loading');
    document.getElementById('refineBtn').disabled = true;

    try {
        const data = await BlogAPI.refineBlog(
            AppState.currentProject,
            AppState.currentProjectId,
            AppState.compiledDraft
        );

        AppState.refinedDraft = data.refined_draft;
        AppState.summary = data.summary;
        AppState.titleOptions = data.title_options || [];

        StateManager.updateCostSummary(data.cost_summary);
        UI.renderRefinedResult();
        UI.updateCostDisplay();
        UI.showStatus('Blog refined successfully!', 'success');
        UI.markStepCompleted('refine');

    } catch (error) {
        UI.showStatus(`Refinement failed: ${error.message}`, 'error');
    } finally {
        document.getElementById('refineBtn').disabled = false;
    }
}

/**
 * Generate social media content
 */
async function generateSocialContent() {
    if (!AppState.currentProject) {
        UI.showStatus('No project selected', 'error');
        return;
    }

    if (!AppState.refinedDraft) {
        UI.showStatus('Please refine the blog first', 'error');
        return;
    }

    UI.showStatus('Generating social content...', 'loading');
    document.getElementById('socialBtn').disabled = true;

    try {
        const data = await BlogAPI.generateSocialContent(AppState.currentProject);

        // Response structure may vary
        AppState.socialContent = data.social_content || data;
        StateManager.updateCostSummary(data.cost_summary);

        UI.renderSocialContent();
        UI.updateCostDisplay();
        UI.showStatus('Social content generated!', 'success');
        UI.markStepCompleted('social');

    } catch (error) {
        UI.showStatus(`Social generation failed: ${error.message}`, 'error');
    } finally {
        document.getElementById('socialBtn').disabled = false;
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', initApp);

// Export global functions for HTML onclick handlers
window.loadProjects = loadProjects;
window.createProject = createProject;
window.selectProject = selectProject;
window.handleFileSelect = handleFileSelect;
window.uploadFiles = uploadFiles;
window.processFiles = processFiles;
window.generateOutline = generateOutline;
window.generateAllSections = generateAllSections;
window.generateNextSection = generateNextSection;
window.compileDraft = compileDraft;
window.refineBlog = refineBlog;
window.generateSocialContent = generateSocialContent;
window.goToStep = UI.goToStep;
window.showSocialTab = UI.showSocialTab;
window.copyToClipboard = UI.copyToClipboard;
window.downloadDraft = UI.downloadDraft;
