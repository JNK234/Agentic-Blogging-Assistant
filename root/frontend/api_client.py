# -*- coding: utf-8 -*-
"""
API Client for interacting with the Agentic Blogging Assistant FastAPI backend.
"""
import httpx
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json

from config import API_BASE_URL
from utils.auth import get_auth_headers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Default base URL loaded from environment via config
DEFAULT_API_BASE_URL = API_BASE_URL

# --- Helper Functions ---
def _get_api_url(endpoint: str, base_url: str = DEFAULT_API_BASE_URL) -> str:
    """Constructs the full API URL."""
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def _get_headers(base_url: str = DEFAULT_API_BASE_URL) -> Dict[str, str]:
    """Get authentication headers for API requests."""
    return get_auth_headers(target_audience=base_url)

async def _handle_response(response: httpx.Response) -> Dict[str, Any]:
    """Handles API response, checking status and parsing JSON."""
    if response.status_code >= 400:
        try:
            error_data = response.json()
            error_message = error_data.get("detail") or error_data.get("error", "Unknown API error")
            logger.error(f"API Error ({response.status_code}): {error_message} - URL: {response.url}")
            raise httpx.HTTPStatusError(message=error_message, request=response.request, response=response)
        except json.JSONDecodeError:
            error_message = f"API Error ({response.status_code}): {response.text}"
            logger.error(error_message + f" - URL: {response.url}")
            raise httpx.HTTPStatusError(message=error_message, request=response.request, response=response)
    try:
        return response.json()
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response from {response.url}: {e}")
        raise ValueError(f"Invalid JSON response received from API: {response.text}")

# --- API Client Functions ---

async def get_job_status(
    project_id: str,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Get the status of a project for debugging.
    """
    api_url = _get_api_url(f"/project_status/{project_id}", base_url)
    headers = _get_headers(base_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Getting project status for {project_id}")
            response = await client.get(api_url, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during project status check: {e}")
            raise ConnectionError(f"Failed to connect to API for project status: {e}")

async def get_projects(
    status: Optional[str] = None,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    List all projects, optionally filtered by status.
    """
    api_url = _get_api_url("/projects", base_url)
    if status:
        api_url += f"?status={status}"
    headers = _get_headers(base_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Listing projects from {api_url}")
            response = await client.get(api_url, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during project listing: {e}")
            raise ConnectionError(f"Failed to connect to API for project listing: {e}")

async def resume_project(
    project_id: str,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Get complete project state for resumption.
    """
    api_url = _get_api_url(f"/resume/{project_id}", base_url)
    headers = _get_headers(base_url)

    async with httpx.AsyncClient(timeout=60.0) as client: # Higher timeout for large state
        try:
            logger.info(f"Resuming project {project_id} from {api_url}")
            response = await client.get(api_url, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during project resumption: {e}")
            raise ConnectionError(f"Failed to connect to API for project resumption: {e}")

async def upload_files(
    project_name: str,
    files_to_upload: List[Tuple[str, bytes, str]], # List of (filename, content_bytes, content_type)
    base_url: str = DEFAULT_API_BASE_URL,
    model_name: Optional[str] = None,
    persona: Optional[str] = None
) -> Dict[str, Any]:
    """
    Uploads files to the backend.

    Args:
        project_name: The name of the project.
        files_to_upload: A list of tuples, each containing (filename, file_content_bytes, content_type).
        base_url: The base URL of the API.
        model_name: Optional model name for the project (e.g., "gpt-4", "claude-3")
        persona: Optional persona/writing style for the project

    Returns:
        The JSON response from the API.
    """
    api_url = _get_api_url(f"/upload/{project_name}", base_url)
    files_payload = [("files", (filename, content, ctype)) for filename, content, ctype in files_to_upload]

    # Add model_name and persona as form data if provided
    form_data = {}
    if model_name:
        form_data["model_name"] = model_name
    if persona:
        form_data["persona"] = persona

    headers = _get_headers(base_url)

    async with httpx.AsyncClient(timeout=60.0) as client: # Increased timeout for uploads
        try:
            logger.info(f"Uploading {len(files_payload)} files to {api_url} with model={model_name}, persona={persona}")
            response = await client.post(api_url, files=files_payload, data=form_data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during file upload: {e}")
            raise ConnectionError(f"Failed to connect to API for file upload: {e}")

async def process_files(
    project_name: str,
    model_name: str,
    file_paths: List[str],
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Requests the backend to process uploaded files.

    Args:
        project_name: The name of the project.
        model_name: The name of the model to use for processing.
        file_paths: List of file paths (as strings) returned by the upload endpoint.
        base_url: The base URL of the API.

    Returns:
        The JSON response from the API containing file hashes.
    """
    api_url = _get_api_url(f"/process_files/{project_name}", base_url)
    headers = _get_headers(base_url)
    # Prepare data dictionary including model_name and file_paths
    # httpx handles sending lists as multiple form fields when passed in data
    data = {
        "model_name": model_name,
        "file_paths": file_paths # Pass the list of strings directly
    }

    async with httpx.AsyncClient(timeout=120.0) as client: # Increased timeout for processing
        try:
            logger.info(f"Requesting file processing for {project_name} at {api_url} with data: {data}")
            # Send the dictionary containing the list via the 'data=' parameter
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during file processing: {e}")
            raise ConnectionError(f"Failed to connect to API for file processing: {e}")

async def get_personas(base_url: str = DEFAULT_API_BASE_URL) -> Dict[str, Any]:
    """
    Fetches available writing personas/output styles from the backend.

    Args:
        base_url: The base URL of the API.

    Returns:
        Dictionary containing available personas with their names and descriptions.
    """
    api_url = _get_api_url("/personas", base_url)
    headers = _get_headers(base_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Requesting personas at {api_url}")
            response = await client.get(api_url, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during personas fetch: {e}")
            raise ConnectionError(f"Failed to connect to API for personas: {e}")

async def get_models(base_url: str = DEFAULT_API_BASE_URL) -> Dict[str, Any]:
    """
    Fetches available models grouped by provider from the backend.

    Args:
        base_url: The base URL of the API.

    Returns:
        Dictionary containing model providers and their available models.
    """
    api_url = _get_api_url("/models", base_url)
    headers = _get_headers(base_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Requesting models at {api_url}")
            response = await client.get(api_url, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during models fetch: {e}")
            raise ConnectionError(f"Failed to connect to API for models: {e}")

async def generate_outline(
    project_name: str,
    model_name: str,
    notebook_hash: Optional[str] = None,
    markdown_hash: Optional[str] = None,
    user_guidelines: Optional[str] = None, # Added
    length_preference: Optional[str] = None, # Added
    custom_length: Optional[int] = None, # Added
    writing_style: Optional[str] = None, # Added
    persona_style: Optional[str] = None, # Added for output style
    specific_model: Optional[str] = None, # Added for granular model control
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Requests the backend to generate a blog outline.

    Args:
        project_name: The name of the project.
        model_name: The name of the model to use.
        notebook_hash: The hash of the processed notebook content (optional).
        markdown_hash: The hash of the processed markdown content (optional).
        user_guidelines: Optional user-provided guidelines for outline generation.
        length_preference: User's preferred blog length category (optional).
        custom_length: Custom target word count if length_preference is "Custom" (optional).
        writing_style: User's preferred writing style (optional).
        persona_style: Selected writing persona/output style (optional).
        specific_model: Specific model within the provider (optional).
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the project_id and the generated outline.
    """
    api_url = _get_api_url(f"/generate_outline/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {
        "model_name": model_name,
        "notebook_hash": notebook_hash or "", # Send empty string if None
        "markdown_hash": markdown_hash or "", # Send empty string if None
        "user_guidelines": user_guidelines or "", # Added - send empty string if None
        "length_preference": length_preference or "", # Added - send empty string if None
        "custom_length": custom_length or 0, # Added - send 0 if None
        "writing_style": writing_style or "", # Added - send empty string if None
        "persona_style": persona_style or "", # Added - send empty string if None
        "specific_model": specific_model or "" # Added - send empty string if None
    }
    # Filter out empty values if necessary, though FastAPI handles empty strings
    data = {k: v for k, v in data.items() if v is not None}

    async with httpx.AsyncClient(timeout=300.0) as client: # Long timeout for generation
        try:
            logger.info(f"Requesting outline generation for {project_name} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during outline generation: {e}")
            raise ConnectionError(f"Failed to connect to API for outline generation: {e}")

async def generate_section(
    project_name: str,
    project_id: str,
    section_index: int,
    max_iterations: int = 3,
    quality_threshold: float = 0.8,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Requests the backend to generate a specific section of the blog draft.

    Args:
        project_name: The name of the project.
        project_id: The ID of the current project.
        section_index: The index of the section to generate.
        max_iterations: Max refinement iterations for the section.
        quality_threshold: Min quality score for the section.
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the generated section content.
    """
    api_url = _get_api_url(f"/generate_section/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {
        "project_id": project_id,
        "section_index": section_index,
        "max_iterations": max_iterations,
        "quality_threshold": quality_threshold
    }

    async with httpx.AsyncClient(timeout=600.0) as client: # Very long timeout for section generation
        try:
            logger.info(f"Requesting section {section_index} generation for project {project_id} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during section generation: {e}")
            raise ConnectionError(f"Failed to connect to API for section generation: {e}")

async def regenerate_section_with_feedback(
    project_name: str,
    project_id: str,
    section_index: int,
    feedback: str,
    max_iterations: int = 3,
    quality_threshold: float = 0.8,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Requests the backend to regenerate a section with user feedback.

    Args:
        project_name: The name of the project.
        project_id: The ID of the current project.
        section_index: The index of the section to regenerate.
        feedback: The user-provided feedback text.
        max_iterations: Max refinement iterations.
        quality_threshold: Min quality score.
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the regenerated section content.
    """
    api_url = _get_api_url(f"/regenerate_section_with_feedback/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {
        "project_id": project_id,
        "section_index": section_index,
        "feedback": feedback,
        "max_iterations": max_iterations,
        "quality_threshold": quality_threshold
    }

    async with httpx.AsyncClient(timeout=600.0) as client: # Very long timeout
        try:
            logger.info(f"Requesting section {section_index} regeneration with feedback for project {project_id} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during section regeneration: {e}")
            raise ConnectionError(f"Failed to connect to API for section regeneration: {e}")

async def compile_draft(
    project_name: str,
    project_id: str,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Requests the backend to compile the final blog draft.

    Args:
        project_name: The name of the project.
        project_id: The ID of the current project.
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the final compiled draft.
    """
    api_url = _get_api_url(f"/compile_draft/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {"project_id": project_id}

    async with httpx.AsyncClient(timeout=120.0) as client: # Moderate timeout for compilation
        try:
            logger.info(f"Requesting draft compilation for project {project_id} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during draft compilation: {e}")
            raise ConnectionError(f"Failed to connect to API for draft compilation: {e}")


async def refine_blog(
    project_name: str,
    project_id: str,
    compiled_draft: str,  # Added compiled_draft parameter
    title_config: Optional[str] = None,  # JSON string for title configuration
    social_config: Optional[str] = None,  # JSON string for social media configuration
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Requests the backend to refine the compiled blog draft.

    Args:
        project_name: The name of the project.
        project_id: The ID of the project.
        compiled_draft: The full compiled blog draft content as a string.
        title_config: Optional JSON string for title generation configuration.
        social_config: Optional JSON string for social media generation configuration.
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the refined draft, summary, and title options.
    """
    api_url = _get_api_url(f"/refine_blog/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {
        "job_id": project_id,  # Backend expects 'job_id' not 'project_id'
        "compiled_draft": compiled_draft  # Include compiled_draft in the payload
    }

    # Add optional configuration parameters
    if title_config:
        data["title_config"] = title_config
    if social_config:
        data["social_config"] = social_config

    async with httpx.AsyncClient(timeout=300.0) as client: # Long timeout for refinement
        try:
            logger.info(f"Requesting blog refinement for project {project_id} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during blog refinement: {e}")
            raise ConnectionError(f"Failed to connect to API for blog refinement: {e}")


async def refine_standalone(
    project_name: str,
    compiled_draft: str,
    model_name: str = "gemini",
    specific_model: Optional[str] = None,
    title_config: Optional[str] = None,  # JSON string for title configuration
    social_config: Optional[str] = None,  # JSON string for social media configuration
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Refines a blog draft without requiring job state - for resuming after expiry.

    Args:
        project_name: The name of the project.
        compiled_draft: The compiled blog draft content.
        model_name: The model to use for refinement (default: "gemini").
        specific_model: The specific model ID to use (optional).
        title_config: Optional JSON string for title generation configuration.
        social_config: Optional JSON string for social media generation configuration.
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the refined draft, summary, and title options.
    """
    api_url = _get_api_url(f"/refine_standalone/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {
        "compiled_draft": compiled_draft,
        "model_name": model_name,
        "specific_model": specific_model or ""
    }

    # Add optional configuration parameters
    if title_config:
        data["title_config"] = title_config
    if social_config:
        data["social_config"] = social_config

    async with httpx.AsyncClient(timeout=300.0) as client: # Long timeout for refinement
        try:
            logger.info(f"Requesting standalone refinement for project {project_name} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during standalone refinement: {e}")
            raise ConnectionError(f"Failed to connect to API for standalone refinement: {e}")


async def generate_social_content(
    project_name: str,
    project_id: str,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Requests the backend to generate social media content from the compiled draft.

    Args:
        project_name: The name of the project.
        project_id: The ID of the project containing the compiled draft.
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the generated social content (breakdown, linkedin, x, newsletter).
    """
    api_url = _get_api_url(f"/generate_social_content/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {"project_id": project_id}

    async with httpx.AsyncClient(timeout=300.0) as client: # Long timeout for generation
        try:
            logger.info(f"Requesting social content generation for project {project_id} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during social content generation: {e}")
            raise ConnectionError(f"Failed to connect to API for social content generation: {e}")


async def generate_social_content_standalone(
    project_name: str,
    refined_blog_content: str,
    model_name: str = "claude",
    specific_model: Optional[str] = None,
    base_url: str = DEFAULT_API_BASE_URL
) -> Dict[str, Any]:
    """
    Generates social media content from refined blog content without requiring job state.

    Args:
        project_name: The name of the project.
        refined_blog_content: The refined blog content.
        model_name: The model to use for generation.
        base_url: The base URL of the API.

    Returns:
        The JSON response containing the generated social content (breakdown, linkedin, x, newsletter).
    """
    api_url = _get_api_url(f"/generate_social_content_standalone/{project_name}", base_url)
    headers = _get_headers(base_url)
    data = {
        "refined_blog_content": refined_blog_content,
        "model_name": model_name,
        "specific_model": specific_model or ""
    }

    async with httpx.AsyncClient(timeout=300.0) as client: # Long timeout for generation
        try:
            logger.info(f"Requesting standalone social content generation for project {project_name} at {api_url}")
            response = await client.post(api_url, data=data, headers=headers)
            return await _handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed during standalone social content generation: {e}")
            raise ConnectionError(f"Failed to connect to API for standalone social content generation: {e}")

async def health_check(base_url: str = DEFAULT_API_BASE_URL) -> bool:
    """Checks the health of the backend API."""
    api_url = _get_api_url("/health", base_url)
    headers = _get_headers(base_url)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(api_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    logger.info("API health check successful.")
                    return True
            logger.warning(f"API health check failed with status {response.status_code}: {response.text}")
            return False
        except (httpx.RequestError, json.JSONDecodeError) as e:
            logger.error(f"API health check failed: {e}")
            return False

# Example Usage (for testing purposes)
if __name__ == '__main__':
    import asyncio

    async def test_api():
        # --- Test Health Check ---
        is_healthy = await health_check()
        print(f"API Healthy: {is_healthy}")
        if not is_healthy:
            print("API is not running or accessible. Exiting test.")
            return

        # --- Test Upload ---
        project = "test_project_api"
        try:
            # Create dummy files
            dummy_ipynb_content = b'{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
            dummy_md_content = b'# Test Markdown\nSome content.'
            files = [
                ("test.ipynb", dummy_ipynb_content, "application/json"),
                ("notes.md", dummy_md_content, "text/markdown")
            ]
            upload_result = await upload_files(project, files)
            print("\n--- Upload Result ---")
            print(json.dumps(upload_result, indent=2))
            uploaded_paths = upload_result.get("files", [])
            if not uploaded_paths:
                print("Upload failed or returned no paths.")
                return

            # --- Test Process Files ---
            process_result = await process_files(project, "gemini", uploaded_paths)
            print("\n--- Process Files Result ---")
            print(json.dumps(process_result, indent=2))
            file_hashes = process_result.get("file_hashes", {})
            ipynb_hash = next((h for p, h in file_hashes.items() if p.endswith(".ipynb")), None)
            md_hash = next((h for p, h in file_hashes.items() if p.endswith(".md")), None)

            # --- Test Generate Outline ---
            if ipynb_hash or md_hash:
                outline_result = await generate_outline(project, "gemini", ipynb_hash, md_hash)
                print("\n--- Generate Outline Result ---")
                print(json.dumps(outline_result, indent=2))
                project_id = outline_result.get("project_id")

                if project_id:
                    # --- Test Generate Section ---
                    section_result = await generate_section(project, project_id, section_index=0)
                    print("\n--- Generate Section 0 Result ---")
                    print(json.dumps(section_result, indent=2))

                    # --- Test Regenerate Section ---
                    regen_result = await regenerate_section_with_feedback(project, project_id, section_index=0, feedback="Make it more detailed.")
                    print("\n--- Regenerate Section 0 Result ---")
                    print(json.dumps(regen_result, indent=2))

                    # --- Test Compile Draft (assuming all sections generated) ---
                    # In a real scenario, loop through all sections first
                    # For testing, we assume section 0 is enough to test compilation logic
                    print("\nSkipping full section generation for test...")
                    print("Attempting draft compilation (may fail if not all sections generated)...")
                    try:
                        compile_result = await compile_draft(project, project_id)
                        print("\n--- Compile Draft Result ---")
                        print(json.dumps(compile_result, indent=2))

                        # --- Test Generate Social Content ---
                        social_result = await generate_social_content(project, project_id)
                        print("\n--- Generate Social Content Result ---")
                        print(json.dumps(social_result, indent=2))

                    except Exception as compile_err:
                         print(f"Draft compilation/social generation failed (expected if sections missing): {compile_err}")

            else:
                print("Could not get file hashes to proceed with outline generation.")

        except Exception as e:
            print(f"\nAn error occurred during API testing: {e}")

    asyncio.run(test_api())
