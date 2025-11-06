"""
CodeMap - Universal Codebase Visualization Tool

A lightweight, project-agnostic tool to visualize code structure and dependencies.
"""

__version__ = "0.1.0"
__author__ = "CodeMap Contributors"

from .parser import parse_file, parse_directory
from .graph import build_graph
from .analyzer import check_rules, categorize_violations
from .config import load_config

__all__ = [
    "parse_file",
    "parse_directory",
    "build_graph",
    "check_rules",
    "categorize_violations",
    "load_config",
]
