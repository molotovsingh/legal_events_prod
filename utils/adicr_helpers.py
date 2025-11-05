"""
ADICR Helpers - Utilities for Automated Documentation Integrity and Coverage Report

Provides AST-based code parsing and markdown analysis to detect documentation drift.
"""

import ast
import re
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from pathlib import Path


@dataclass
class ProviderInventory:
    """Inventory of providers extracted from code"""
    providers: Set[str]
    source_file: str
    line_number: int
    registry_name: str


@dataclass
class EnvVarInventory:
    """Inventory of environment variables extracted from config"""
    var_name: str
    dataclass_name: str
    default_value: str
    var_type: str  # 'str', 'bool', 'int', 'float'
    field_name: str


@dataclass
class DocumentationLocation:
    """A location where providers or env vars should be documented"""
    file_path: str
    section: Optional[str]
    line_range: Optional[str]
    description: str


class RegistryExtractor(ast.NodeVisitor):
    """AST visitor to extract provider registries from Python files"""

    def __init__(self, registry_name: str):
        self.registry_name = registry_name
        self.providers: Set[str] = set()
        self.line_number: int = 0

    def visit_Assign(self, node):
        """Visit regular assignment statements to find registry definitions"""
        # Regular assignment: REGISTRY = {...}
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == self.registry_name:
                self.line_number = node.lineno
                self._extract_dict_keys(node.value)

        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        """Visit annotated assignment statements to find registry definitions"""
        # Type-annotated assignment: REGISTRY: Dict[str, Callable] = {...}
        if isinstance(node.target, ast.Name) and node.target.id == self.registry_name:
            self.line_number = node.lineno
            if node.value:
                self._extract_dict_keys(node.value)

        self.generic_visit(node)

    def _extract_dict_keys(self, value_node):
        """Helper to extract dictionary keys from a value node"""
        if isinstance(value_node, ast.Dict):
            for key in value_node.keys:
                if isinstance(key, ast.Constant):
                    self.providers.add(key.value)


class EnvVarExtractor(ast.NodeVisitor):
    """AST visitor to extract environment variable calls from config dataclasses"""

    def __init__(self):
        self.env_vars: List[EnvVarInventory] = []
        self.current_dataclass: Optional[str] = None

    def visit_ClassDef(self, node):
        """Track which dataclass we're in"""
        # Check if it's a dataclass
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == 'dataclass':
                self.current_dataclass = node.name
                self.generic_visit(node)
                self.current_dataclass = None
                return

        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        """Visit annotated assignments like field_name: str = field(...)"""
        if self.current_dataclass and isinstance(node.target, ast.Name):
            field_name = node.target.id

            # Check if value is a field() call with default_factory containing env_* call
            if isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name) and node.value.func.id == 'field':
                    # Look for default_factory= keyword arg
                    for keyword in node.value.keywords:
                        if keyword.arg == 'default_factory' and isinstance(keyword.value, ast.Lambda):
                            # Lambda body should be env_* call
                            lambda_body = keyword.value.body
                            if isinstance(lambda_body, ast.Call) and isinstance(lambda_body.func, ast.Name):
                                func_name = lambda_body.func.id

                                # Check if it's env_str, env_bool, env_int, env_float
                                if func_name in ('env_str', 'env_bool', 'env_int', 'env_float'):
                                    # Extract variable name and default
                                    if len(lambda_body.args) >= 1 and isinstance(lambda_body.args[0], ast.Constant):
                                        var_name = lambda_body.args[0].value
                                        default_val = ""

                                        if len(lambda_body.args) >= 2:
                                            if isinstance(lambda_body.args[1], ast.Constant):
                                                default_val = str(lambda_body.args[1].value)

                                        self.env_vars.append(EnvVarInventory(
                                            var_name=var_name,
                                            dataclass_name=self.current_dataclass,
                                            default_value=default_val,
                                            var_type=func_name.replace('env_', ''),
                                            field_name=field_name
                                        ))

        self.generic_visit(node)


def extract_providers_from_registry(file_path: str, registry_name: str = "EVENT_PROVIDER_REGISTRY") -> ProviderInventory:
    """
    Extract provider keys from a registry dictionary using AST parsing

    Args:
        file_path: Path to Python file containing the registry
        registry_name: Name of the registry variable to extract

    Returns:
        ProviderInventory with provider names and metadata
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, 'r') as f:
        tree = ast.parse(f.read(), filename=str(path))

    extractor = RegistryExtractor(registry_name)
    extractor.visit(tree)

    return ProviderInventory(
        providers=extractor.providers,
        source_file=file_path,
        line_number=extractor.line_number,
        registry_name=registry_name
    )


def extract_env_vars_from_config(file_path: str) -> List[EnvVarInventory]:
    """
    Extract environment variable names from config dataclasses using AST parsing

    Args:
        file_path: Path to config.py file

    Returns:
        List of EnvVarInventory objects
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, 'r') as f:
        tree = ast.parse(f.read(), filename=str(path))

    extractor = EnvVarExtractor()
    extractor.visit(tree)

    return extractor.env_vars


def extract_markdown_section(file_path: str, section_heading: str) -> Optional[str]:
    """
    Extract markdown content under a specific heading

    Args:
        file_path: Path to markdown file
        section_heading: Heading text to search for (case-insensitive)

    Returns:
        Content under the heading, or None if not found
    """
    path = Path(file_path)
    if not path.exists():
        return None

    with open(path, 'r') as f:
        lines = f.readlines()

    # Find the section
    in_section = False
    section_lines = []
    heading_pattern = re.compile(r'^#{1,6}\s+(.+)$')

    for line in lines:
        match = heading_pattern.match(line)

        if match:
            heading_text = match.group(1).strip()

            # Check if this is our target heading
            if heading_text.lower() == section_heading.lower():
                in_section = True
                continue
            elif in_section:
                # Found another heading, stop collecting
                break

        if in_section:
            section_lines.append(line)

    return ''.join(section_lines) if section_lines else None


def find_text_in_file(file_path: str, search_text: str, case_sensitive: bool = False) -> List[int]:
    """
    Find line numbers where text appears in a file

    Args:
        file_path: Path to file
        search_text: Text to search for
        case_sensitive: Whether search should be case-sensitive

    Returns:
        List of line numbers (1-indexed) where text appears
    """
    path = Path(file_path)
    if not path.exists():
        return []

    matches = []
    with open(path, 'r') as f:
        for line_num, line in enumerate(f, start=1):
            search_in = line if case_sensitive else line.lower()
            target = search_text if case_sensitive else search_text.lower()

            if target in search_in:
                matches.append(line_num)

    return matches


def fuzzy_match_heading(file_path: str, heading_text: str, confidence_threshold: float = 0.8) -> Optional[str]:
    """
    Fuzzy match a heading in a markdown file

    Args:
        file_path: Path to markdown file
        heading_text: Heading text to search for
        confidence_threshold: Minimum similarity score (0.0-1.0)

    Returns:
        Matched heading text if found above threshold, else None
    """
    path = Path(file_path)
    if not path.exists():
        return None

    with open(path, 'r') as f:
        lines = f.readlines()

    heading_pattern = re.compile(r'^#{1,6}\s+(.+)$')
    target = heading_text.lower()
    best_match = None
    best_score = 0.0

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            candidate = match.group(1).strip().lower()

            # Simple similarity: count matching words
            target_words = set(target.split())
            candidate_words = set(candidate.split())

            if not target_words:
                continue

            intersection = target_words & candidate_words
            score = len(intersection) / len(target_words)

            if score > best_score:
                best_score = score
                best_match = match.group(1).strip()

    return best_match if best_score >= confidence_threshold else None
