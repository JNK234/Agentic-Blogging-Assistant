# ABOUTME: FastMCP tools for file upload and processing operations
# ABOUTME: Handles base64-encoded file uploads and triggers content processing pipeline

from typing import List, Dict, Any
import logging
import aiohttp
from mcp.server.fastmcp import FastMCP

from ..api_client import BackendAPIClient
from ..utils.file_handler import decode_files
from ..config import settings

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("file-tools")


@mcp.tool()
async def upload_files(
    project_id: str,
    files: List[str]
) -> Dict[str, Any]:
    """
    Upload files to an existing project.

    This tool accepts base64-encoded file contents and uploads them to the specified
    project. Files must be in the format "filename:base64_content" where the filename
    includes the extension (.ipynb, .md, or .py).

    Args:
        project_id: UUID of the project to upload files to
        files: List of base64-encoded files in format "filename:base64_content"
               Supported extensions: .ipynb, .md, .py
               Example: ["notebook.ipynb:SGVsbG8gV29ybGQh", "readme.md:IyBUaXRsZQ=="]

    Returns:
        Dictionary containing:
        - message: Success message
        - project_name: Name of the project
        - project_id: UUID of the project
        - files: List of uploaded file names

    Raises:
        ValueError: If file format is invalid or extension is not supported
        ConnectionError: If unable to connect to the backend API

    Example:
        import base64

        # Encode a file
        with open("notebook.ipynb", "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")

        # Upload to project
        result = await upload_files(
            project_id="123e4567-e89b-12d3-a456-426614174000",
            files=[f"notebook.ipynb:{content}"]
        )
        print(f"Uploaded {len(result['files'])} files")
    """
    try:
        logger.info(f"Uploading {len(files)} files to project: {project_id}")

        # Decode base64 files to (filename, bytes) tuples
        decoded_files = decode_files(files)
        logger.debug(f"Decoded {len(decoded_files)} files")

        # Get project details to find project name
        async with BackendAPIClient() as client:
            project_data = await client.get_project(project_id)
            project_name = project_data.get("project", {}).get("name")

            if not project_name:
                raise ValueError(f"Project not found: {project_id}")

            # Upload files using FormData
            url = f"{client.base_url}/upload/{project_name}"

            data = aiohttp.FormData()
            for filename, content_bytes in decoded_files:
                data.add_field(
                    "files",
                    content_bytes,
                    filename=filename,
                    content_type="application/octet-stream"
                )

            async with client.session.post(url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ConnectionError(
                        f"Upload failed with status {response.status}: {error_text}"
                    )
                result = await response.json()

        logger.info(f"Successfully uploaded {len(decoded_files)} files")
        return result

    except ValueError as e:
        logger.error(f"Validation error uploading files: {e}")
        raise
    except ConnectionError as e:
        logger.error(f"Connection error uploading files: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading files: {e}")
        raise ValueError(f"Failed to upload files: {str(e)}")


@mcp.tool()
async def process_files(
    project_id: str,
    model_name: str = "gpt-4o-mini",
    file_paths: List[str] = None
) -> Dict[str, Any]:
    """
    Process uploaded files for a project.

    This triggers the content parsing pipeline which extracts content from uploaded
    files, creates embeddings, and stores them in the vector database for later use
    in outline and blog generation.

    Args:
        project_id: UUID of the project containing files to process
        model_name: Model to use for processing (default: "gpt-4o-mini")
                    Options: "gpt-4o-mini", "gpt-4o", "claude-3-5-sonnet-20241022",
                            "deepseek-chat", "gemini-2.0-flash-exp"
        file_paths: Optional list of specific file paths to process.
                   If None, processes all uploaded files in the project.
                   Example: ["notebook.ipynb", "guide.md"]

    Returns:
        Dictionary containing:
        - message: Processing status message
        - project_name: Name of the project
        - model_name: Model used for processing
        - files_processed: List of processed file names
        - chunks_created: Number of content chunks created
        - embeddings_stored: Number of embeddings stored in vector DB

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response or project not found

    Example:
        # Process all files in a project
        result = await process_files(
            project_id="123e4567-e89b-12d3-a456-426614174000"
        )
        print(f"Processed {result['files_processed']} files")
        print(f"Created {result['chunks_created']} content chunks")

        # Process specific files only
        result = await process_files(
            project_id="123e4567-e89b-12d3-a456-426614174000",
            file_paths=["notebook.ipynb"],
            model_name="gpt-4o"
        )
    """
    try:
        logger.info(f"Processing files for project: {project_id}")

        async with BackendAPIClient() as client:
            result = await client.process_files(
                project_id=project_id,
                model_name=model_name,
                file_paths=file_paths
            )

        logger.info(f"Successfully processed files for project")
        return result

    except ConnectionError as e:
        logger.error(f"Connection error processing files: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing files: {e}")
        raise ValueError(f"Failed to process files: {str(e)}")
