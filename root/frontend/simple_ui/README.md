# Simple Blog UI

A minimal vanilla HTML/CSS/JavaScript frontend for the Agentic Blogging Assistant.

## Project Structure

```
simple_ui/
├── index.html          # Main HTML file
├── css/
│   └── styles.css      # All styles
├── js/
│   ├── api.js          # API client (handles Form data correctly)
│   ├── state.js        # Application state management
│   ├── ui.js           # UI rendering functions
│   └── app.js          # Main application logic
├── server.py           # Simple Python HTTP server
└── README.md           # This file
```

## Features

- **Project Management**: Create, switch, and resume blog projects
- **File Upload**: Upload Jupyter notebooks, Markdown, and Python files
- **Content Processing**: Process uploaded files for analysis
- **Outline Generation**: Generate structured blog outlines with customization
- **Section-by-Section Drafting**: Generate blog content one section at a time
- **Draft Compilation**: Compile all sections into a complete draft
- **Blog Refinement**: Generate introduction, conclusion, and title options
- **Social Content**: Create LinkedIn, Twitter/X, and newsletter content
- **Cost Tracking**: Real-time token and cost monitoring
- **XSS Protection**: All user content is properly escaped

## Quick Start

### 1. Start the Backend

```bash
cd root/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start the Simple UI

**Option A - Python server (recommended):**
```bash
cd root/frontend/simple_ui
python server.py
```

**Option B - Python http.server:**
```bash
cd root/frontend/simple_ui
python -m http.server 3000
```

**Option C - Direct file:**
```bash
# Just open index.html in your browser
open root/frontend/simple_ui/index.html
```

### 3. Open in Browser

Navigate to `http://localhost:3000`

## Workflow

1. **Create/Select Project** - Use the sidebar to create a new project or select existing
2. **Upload Files** - Upload your source content (.ipynb, .md, .py)
3. **Process** - Process files for content indexing
4. **Generate Outline** - Configure and generate a structured outline
5. **Generate Draft** - Generate sections one-by-one or all at once
6. **Compile** - Compile sections into a complete draft
7. **Refine** - Add intro, conclusion, and generate title options
8. **Social** - Generate platform-specific social media content

## API Configuration

The UI connects to the backend at `http://localhost:8000` by default.

To change this, edit the `API_BASE` constant in `js/api.js`:

```javascript
const API_BASE = 'http://localhost:8000';
```

## Code Organization

### api.js
- `BlogAPI` object with all API functions
- Handles Form data encoding for backend endpoints
- XSS escaping utility

### state.js
- `AppState` object holds all application state
- `StateManager` for state manipulation functions
- Milestone restoration from backend

### ui.js
- `UI` object with all rendering functions
- Status messages, navigation, content display
- Copy to clipboard, download functionality

### app.js
- Main application logic
- Event handlers for all user actions
- Workflow orchestration

## Browser Support

Works in all modern browsers (Chrome, Firefox, Safari, Edge).

No build step or npm required - just HTML, CSS, and JavaScript.

## Key Fixes in This Version

1. **Form Data**: Backend endpoints use Form parameters, not JSON - now handled correctly
2. **Job ID Parameter**: Compile and refine endpoints require `job_id` - now included
3. **Response Parsing**: Correctly handles response field names (`files` vs `uploaded_files`)
4. **XSS Protection**: All dynamic content is escaped before rendering
5. **State Restoration**: Properly restores state when selecting existing projects
