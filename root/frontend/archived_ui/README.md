# Archived UI Files

This directory contains unused UI files that were archived to keep the main frontend directory clean.

## Archived Files:

### `app.py`
- **Archived Date:** 2024-09-14
- **Original Location:** `root/frontend/app.py`
- **Status:** Legacy UI file, replaced by `new_app_api.py`
- **File Date:** 2024-03-29
- **Description:** Original Streamlit UI implementation

### `app_with_projects.py`
- **Archived Date:** 2024-09-14
- **Original Location:** `root/frontend/app_with_projects.py`
- **Status:** Project-specific UI variant, not used by launch scripts
- **File Date:** 2024-09-04
- **Description:** Enhanced UI with project management features

### `streamlit_app.py`
- **Archived Date:** 2024-09-14
- **Original Location:** `root/frontend/streamlit_app.py`
- **Status:** Alternative UI, used by `run_app.sh` but not needed
- **File Date:** 2024-09-04
- **Description:** Alternative Streamlit UI implementation

## Active UI Files (Not Archived):

- ✅ `new_app_api.py` - **ONLY** production UI (used by `launch.sh`)

## Restoration:

If you need to restore any of these files:
```bash
cp archived_ui/[filename] ../[filename]
```

## Safe to Delete:

These archived files can be safely deleted if you're confident they won't be needed in the future.