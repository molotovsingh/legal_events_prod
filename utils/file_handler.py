"""
File Handling Utilities
"""

import os
import tempfile
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file operations and temporary file management"""

    def __init__(self):
        self.supported_extensions = ['pdf', 'docx', 'txt', 'pptx', 'html', 'eml', 'msg', 'jpg', 'jpeg', 'png']

    def save_uploaded_file(self, uploaded_file, temp_dir: Path) -> Path:
        """
        Save uploaded file to temporary directory

        Args:
            uploaded_file: Streamlit uploaded file object
            temp_dir: Path to temporary directory

        Returns:
            Path to saved file
        """
        file_path = temp_dir / uploaded_file.name
        try:
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            logger.debug(f"Saved file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save file {uploaded_file.name}: {e}")
            raise

    def get_file_extension(self, file_path: Path) -> str:
        """Get file extension without dot"""
        return file_path.suffix.lower().lstrip('.')

    def is_supported_file(self, file_extension: str) -> bool:
        """Check if file extension is supported"""
        return file_extension in self.supported_extensions

    def validate_uploaded_files(self, uploaded_files) -> Tuple[List, List]:
        """
        Validate uploaded files and separate supported from unsupported

        Args:
            uploaded_files: List of uploaded file objects

        Returns:
            Tuple of (supported_files, unsupported_files)
        """
        supported = []
        unsupported = []

        for file in uploaded_files:
            extension = self.get_file_extension(Path(file.name))
            if self.is_supported_file(extension):
                supported.append(file)
            else:
                unsupported.append(file)

        return supported, unsupported

    def get_file_info(self, uploaded_file) -> dict:
        """Get file information"""
        file_size = len(uploaded_file.getbuffer())
        extension = self.get_file_extension(Path(uploaded_file.name))

        return {
            'name': uploaded_file.name,
            'size': file_size,
            'size_mb': round(file_size / (1024 * 1024), 2),
            'extension': extension,
            'supported': self.is_supported_file(extension)
        }