"""
Python AST-based code parser.
Extracts imports, classes, functions from Python files.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from fnmatch import fnmatch


class ParseError(Exception):
    """Raised when a file cannot be parsed."""
    pass


def parse_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single Python file and extract structure.
    
    Args:
        filepath: Path to Python file
        
    Returns:
        Dictionary containing:
        - file: relative file path
        - imports: list of imported modules with line numbers
        - classes: list of class names
        - functions: list of function names
        - error: error message if parsing failed
        
        Returns None if file cannot be parsed.
    """
    path = Path(filepath)
    
    if not path.exists():
        return {"file": str(filepath), "error": "File not found"}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return {"file": str(filepath), "error": f"Cannot read file: {e}"}
    
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return {"file": str(filepath), "error": f"Syntax error: {e}"}
    except Exception as e:
        return {"file": str(filepath), "error": f"Parse error: {e}"}
    
    return {
        "file": str(filepath),
        "imports": extract_imports(tree),
        "classes": extract_classes(tree),
        "functions": extract_functions(tree),
    }


def extract_imports(tree: ast.AST) -> List[Dict[str, Any]]:
    """
    Extract all import statements from AST.
    
    Args:
        tree: Python AST
        
    Returns:
        List of imports with format:
        [
            {"module": "os.path", "name": "path", "line": 5, "type": "import"},
            {"module": "sys", "name": None, "line": 6, "type": "import"},
            {"module": "json", "name": "dumps", "line": 7, "type": "from"},
        ]
    """
    imports = []
    
    for node in ast.walk(tree):
        # Handle: import X, import X as Y
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "module": alias.name,
                    "name": alias.asname if alias.asname else alias.name,
                    "line": node.lineno,
                    "type": "import"
                })
        
        # Handle: from X import Y, from X import Y as Z
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                # Handle relative imports: from . import X, from .. import Y
                if node.level > 0:
                    prefix = "." * node.level
                    full_module = f"{prefix}{module}" if module else prefix
                else:
                    full_module = module
                
                imports.append({
                    "module": full_module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                    "type": "from"
                })
    
    return imports


def extract_classes(tree: ast.AST) -> List[str]:
    """
    Extract class names from AST.
    
    Args:
        tree: Python AST
        
    Returns:
        List of class names
    """
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
    return classes


def extract_functions(tree: ast.AST) -> List[str]:
    """
    Extract top-level function names from AST.
    
    Args:
        tree: Python AST
        
    Returns:
        List of function names
    """
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    return functions


def parse_directory(
    root_path: str,
    exclude_patterns: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Parse all Python files in a directory recursively.
    
    Args:
        root_path: Root directory to scan
        exclude_patterns: List of glob patterns to exclude
        
    Returns:
        List of parsed file dictionaries
    """
    if exclude_patterns is None:
        exclude_patterns = ["venv/**", "**/__pycache__/**", "**/*.pyc"]
    
    root = Path(root_path).resolve()
    parsed_files = []
    
    # Find all Python files
    for py_file in root.rglob("*.py"):
        # Convert to relative path for pattern matching
        try:
            rel_path = py_file.relative_to(root)
        except ValueError:
            # File is outside root, skip
            continue
        
        rel_path_str = str(rel_path)
        
        # Check if file should be excluded
        should_exclude = False
        for pattern in exclude_patterns:
            if fnmatch(rel_path_str, pattern):
                should_exclude = True
                break
        
        if should_exclude:
            continue
        
        # Parse the file
        result = parse_file(str(py_file))
        if result:
            # Store relative path for consistency
            result["file"] = rel_path_str
            parsed_files.append(result)
    
    return parsed_files


def resolve_import_to_file(
    import_module: str,
    from_file: str,
    root_path: str
) -> Optional[str]:
    """
    Resolve an import statement to its actual file path.
    
    Args:
        import_module: Module name (e.g., "core.extractor")
        from_file: File doing the import (e.g., "api/routes.py")
        root_path: Project root directory
        
    Returns:
        Relative path to imported file, or None if not found
        
    Examples:
        "core.extractor" -> "core/extractor.py"
        "api.storage" -> "api/storage.py"
        "..utils" (from worker/tasks.py) -> "utils.py" or "utils/__init__.py"
    """
    root = Path(root_path).resolve()
    
    # Handle relative imports
    if import_module.startswith("."):
        from_dir = (root / Path(from_file)).parent
        level = len(import_module) - len(import_module.lstrip("."))
        remaining = import_module.lstrip(".")
        
        # Go up 'level' directories
        target_dir = from_dir
        for _ in range(level - 1):
            target_dir = target_dir.parent
        
        if remaining:
            module_path = target_dir / remaining.replace(".", "/")
        else:
            module_path = target_dir
    else:
        # Absolute import from project root
        module_path = root / import_module.replace(".", "/")
    
    # Try .py file
    py_file = module_path.with_suffix(".py")
    if py_file.exists():
        try:
            return str(py_file.relative_to(root))
        except ValueError:
            return None
    
    # Try package __init__.py
    init_file = module_path / "__init__.py"
    if init_file.exists():
        try:
            return str(init_file.relative_to(root))
        except ValueError:
            return None
    
    # Could be a stdlib or external package
    return None


def module_to_file(module_name: str, root_path: str = ".") -> Optional[str]:
    """
    Convert a module name to its file path.
    
    Args:
        module_name: Python module name (e.g., "api.routes")
        root_path: Project root
        
    Returns:
        File path relative to root, or None if external module
        
    Examples:
        "api.routes" -> "api/routes.py"
        "core.extractor" -> "core/extractor.py"
        "os.path" -> None (stdlib)
    """
    root = Path(root_path).resolve()
    
    # Convert module path to file path
    parts = module_name.split(".")
    
    # Try as .py file
    file_path = root / "/".join(parts)
    py_file = file_path.with_suffix(".py")
    if py_file.exists():
        try:
            return str(py_file.relative_to(root))
        except ValueError:
            return None
    
    # Try as package __init__.py
    init_file = file_path / "__init__.py"
    if init_file.exists():
        try:
            return str(init_file.relative_to(root))
        except ValueError:
            return None
    
    # External or stdlib module
    return None
