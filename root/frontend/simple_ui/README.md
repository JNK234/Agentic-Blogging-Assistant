# Simple Blog UI

A minimal vanilla HTML/CSS/JavaScript frontend for the Agentic Blogging Assistant.

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

## Quick Start

### 1. Start the Backend

```bash
cd root/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start the Simple UI

Option A - Python server:
```bash
cd root/frontend/simple_ui
python server.py
```

Option B - Direct file:
```bash
# Just open index.html in your browser
open root/frontend/simple_ui/index.html
```

Option C - Python http.server:
```bash
cd root/frontend/simple_ui
python -m http.server 3000
```

### 3. Open in Browser

Navigate to `http://localhost:3000` (or open the file directly)

## Workflow

1. **Create/Select Project** - Use the sidebar to create a new project or select existing
2. **Upload Files** - Upload your source content (.ipynb, .md, .py)
3. **Process** - Process files for content indexing
4. **Generate Outline** - Configure and generate a structured outline
5. **Generate Draft** - Generate sections one-by-one or all at once
6. **Compile** - Compile sections into a complete draft
7. **Refine** - Add intro, conclusion, and generate title options
8. **Social** - Generate platform-specific social media content

## Configuration

- **Model**: Select the LLM provider (OpenAI, Claude, Gemini, Deepseek)
- **Persona**: Choose writing style (NeuraForge professional, Student sharing)

## API Configuration

The UI connects to the backend at `http://localhost:8000` by default.

To change this, edit the `API_BASE` constant in `index.html`:

```javascript
const API_BASE = 'http://localhost:8000';
```

## Browser Support

Works in all modern browsers (Chrome, Firefox, Safari, Edge).

No build step or npm required - just HTML, CSS, and JavaScript.
