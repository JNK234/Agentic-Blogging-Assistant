# ABOUTME: File handler utility for base64 encoding/decoding of blog content files
# ABOUTME: Supports .ipynb, .md, and .py file types with validation

import base64
from pathlib import Path
from typing import List, Tuple


SUPPORTED_EXTENSIONS = {'.ipynb', '.md', '.py'}


def validate_file_extension(filename: str) -> bool:
    """
    Validate if the file extension is supported.

    Args:
        filename: Name of the file to validate

    Returns:
        True if extension is supported (.ipynb, .md, .py), False otherwise
    """
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS


def encode_file(file_path: str) -> str:
    """
    Encode a file to base64 format with filename prefix.

    Args:
        file_path: Path to the file to encode

    Returns:
        String in format "filename:base64_content"

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file extension is not supported
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not validate_file_extension(path.name):
        raise ValueError(
            f"Unsupported file extension: {path.suffix}. "
            f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    with open(path, 'rb') as f:
        content = f.read()

    encoded_content = base64.b64encode(content).decode('utf-8')
    return f"{path.name}:{encoded_content}"


def decode_files(encoded_files: List[str]) -> List[Tuple[str, bytes]]:
    """
    Decode base64 encoded files.

    Args:
        encoded_files: List of strings in format "filename:base64_content"

    Returns:
        List of tuples containing (filename, file_content_bytes)

    Raises:
        ValueError: If encoded file format is invalid or extension is not supported
    """
    decoded_files = []

    for encoded_file in encoded_files:
        if ':' not in encoded_file:
            raise ValueError(
                f"Invalid encoded file format. Expected 'filename:base64_content', "
                f"got: {encoded_file[:50]}..."
            )

        filename, encoded_content = encoded_file.split(':', 1)

        if not validate_file_extension(filename):
            raise ValueError(
                f"Unsupported file extension: {Path(filename).suffix}. "
                f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        try:
            content = base64.b64decode(encoded_content)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 content for {filename}: {str(e)}")

        decoded_files.append((filename, content))

    return decoded_files
