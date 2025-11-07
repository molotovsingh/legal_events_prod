"""
Storage Key Utilities

Standardized utilities for generating consistent S3/MinIO storage keys.
Ensures uniform key structure across the codebase and prevents key inconsistencies.

Standard Key Pattern:
    clients/{client_id}/cases/{case_id}/runs/{run_id}/{category}/{filename}

Categories:
    - docs: Source documents uploaded by users
    - artifacts: Generated exports (CSV, XLSX, JSON)
"""

import re
from typing import Optional


def generate_document_key(
    client_id: int,
    case_id: int,
    run_id: int,
    filename: str
) -> str:
    """
    Generate standardized storage key for uploaded documents

    Args:
        client_id: Client ID (positive integer)
        case_id: Case ID (positive integer)
        run_id: Run ID (positive integer)
        filename: Document filename (sanitized)

    Returns:
        Storage key in format: clients/{client_id}/cases/{case_id}/runs/{run_id}/docs/{filename}

    Raises:
        ValueError: If any ID is invalid or filename is empty

    Example:
        >>> generate_document_key(1, 42, 100, "contract.pdf")
        'clients/1/cases/42/runs/100/docs/contract.pdf'
    """
    _validate_id(client_id, "client_id")
    _validate_id(case_id, "case_id")
    _validate_id(run_id, "run_id")
    _validate_filename(filename)

    sanitized_filename = _sanitize_filename(filename)
    return f"clients/{client_id}/cases/{case_id}/runs/{run_id}/docs/{sanitized_filename}"


def generate_artifact_key(
    client_id: int,
    case_id: int,
    run_id: int,
    format: str
) -> str:
    """
    Generate standardized storage key for generated artifacts

    Args:
        client_id: Client ID (positive integer)
        case_id: Case ID (positive integer)
        run_id: Run ID (positive integer)
        format: File format (csv, xlsx, json)

    Returns:
        Storage key in format: clients/{client_id}/cases/{case_id}/runs/{run_id}/artifacts/{run_id}.{format}

    Raises:
        ValueError: If any ID is invalid or format is not supported

    Example:
        >>> generate_artifact_key(1, 42, 100, "csv")
        'clients/1/cases/42/runs/100/artifacts/100.csv'
    """
    _validate_id(client_id, "client_id")
    _validate_id(case_id, "case_id")
    _validate_id(run_id, "run_id")
    _validate_format(format)

    format_lower = format.lower()
    return f"clients/{client_id}/cases/{case_id}/runs/{run_id}/artifacts/{run_id}.{format_lower}"


def parse_storage_key(key: str) -> dict:
    """
    Parse a storage key back into its components

    Args:
        key: Storage key to parse

    Returns:
        Dictionary with extracted components:
        - client_id: int
        - case_id: int
        - run_id: int
        - category: str ('docs' or 'artifacts')
        - filename: str

    Raises:
        ValueError: If key doesn't match expected pattern

    Example:
        >>> parse_storage_key("clients/1/cases/42/runs/100/docs/contract.pdf")
        {
            'client_id': 1,
            'case_id': 42,
            'run_id': 100,
            'category': 'docs',
            'filename': 'contract.pdf'
        }
    """
    pattern = r'^clients/(\d+)/cases/(\d+)/runs/(\d+)/(docs|artifacts)/(.+)$'
    match = re.match(pattern, key)

    if not match:
        raise ValueError(
            f"Invalid storage key format: {key}. "
            f"Expected: clients/{{client_id}}/cases/{{case_id}}/runs/{{run_id}}/{{category}}/{{filename}}"
        )

    return {
        'client_id': int(match.group(1)),
        'case_id': int(match.group(2)),
        'run_id': int(match.group(3)),
        'category': match.group(4),
        'filename': match.group(5)
    }


# Private validation functions

def _validate_id(value: int, name: str):
    """Validate that an ID is a positive integer"""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value}")


def _validate_filename(filename: str):
    """Validate that filename is not empty"""
    if not filename or not filename.strip():
        raise ValueError("filename cannot be empty")


def _validate_format(format: str):
    """Validate that format is supported"""
    valid_formats = {'csv', 'xlsx', 'json'}
    if format.lower() not in valid_formats:
        raise ValueError(
            f"Unsupported format: {format}. Must be one of {valid_formats}"
        )


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and special characters

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for storage keys

    Example:
        >>> _sanitize_filename("../../etc/passwd")
        'passwd'
        >>> _sanitize_filename("file with spaces.pdf")
        'file_with_spaces.pdf'
    """
    # Remove path components (security)
    filename = filename.split('/')[-1].split('\\')[-1]

    # Replace spaces and special chars with underscores
    filename = re.sub(r'[^\w\-.]', '_', filename)

    # Remove multiple consecutive underscores
    filename = re.sub(r'_+', '_', filename)

    # Ensure not empty after sanitization
    if not filename or filename == '.':
        raise ValueError("Filename becomes empty after sanitization")

    return filename
