"""
Dependency graph builder.
Builds nodes and edges from parsed files and configuration.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from fnmatch import fnmatch


def build_graph(
    parsed_files: List[Dict[str, Any]],
    config: Dict[str, Any],
    root_path: str = "."
) -> Dict[str, Any]:
    """
    Build dependency graph from parsed files.
    
    Args:
        parsed_files: List of parsed file dictionaries from parser
        config: Configuration dictionary
        root_path: Project root path
        
    Returns:
        Graph dictionary with:
        - nodes: List of module nodes
        - edges: List of import edges
        - external: List of external/stdlib imports
    """
    nodes = []
    edges = []
    external_imports = set()
    
    # Create file path to module mapping
    file_to_module = {}
    for parsed in parsed_files:
        if "error" in parsed:
            continue
        filepath = parsed["file"]
        module_name = filepath_to_module(filepath)
        file_to_module[filepath] = module_name
    
    # Build nodes
    for parsed in parsed_files:
        if "error" in parsed:
            continue
            
        filepath = parsed["file"]
        module_name = file_to_module[filepath]
        service = classify_service(filepath, config)
        
        node = {
            "id": module_name,
            "file": filepath,
            "service": service,
            "type": "module",
            "classes": parsed.get("classes", []),
            "functions": parsed.get("functions", [])
        }
        nodes.append(node)
    
    # Build edges from imports
    for parsed in parsed_files:
        if "error" in parsed:
            continue
            
        from_file = parsed["file"]
        from_module = file_to_module[from_file]
        
        for imp in parsed.get("imports", []):
            # Resolve the import to a target file
            target_file = resolve_import(imp, from_file, root_path, file_to_module)
            
            if target_file:
                # Internal import
                target_module = file_to_module.get(target_file)
                if target_module:
                    edge = {
                        "from": from_module,
                        "from_file": from_file,
                        "to": target_module,
                        "to_file": target_file,
                        "type": "import",
                        "line": imp.get("line"),
                        "import_type": imp.get("type")
                    }
                    edges.append(edge)
            else:
                # External import (stdlib or third-party)
                external_imports.add(imp["module"])
    
    return {
        "nodes": nodes,
        "edges": edges,
        "external": sorted(list(external_imports)),
        "file_count": len([n for n in nodes]),
        "import_count": len(edges)
    }


def classify_service(filepath: str, config: Dict[str, Any]) -> str:
    """
    Determine which service a file belongs to based on config patterns.
    
    Args:
        filepath: Relative file path
        config: Configuration dictionary
        
    Returns:
        Service name, or "unknown" if no match
    """
    services = config.get("services", [])
    
    for service in services:
        patterns = service.get("paths", [])
        for pattern in patterns:
            if match_pattern(filepath, pattern):
                return service["name"]
    
    return "unknown"


def match_pattern(filepath: str, pattern: str) -> bool:
    """
    Check if a filepath matches a glob pattern.
    Supports ** for recursive matching.
    
    Args:
        filepath: File path to check
        pattern: Glob pattern (e.g., "api/**/*.py")
        
    Returns:
        True if filepath matches pattern
    """
    # Use Path.match() which supports ** glob patterns
    from pathlib import PurePath
    return PurePath(filepath).match(pattern)


def filepath_to_module(filepath: str) -> str:
    """
    Convert a file path to a Python module name.
    
    Args:
        filepath: Relative file path (e.g., "api/routes.py")
        
    Returns:
        Module name (e.g., "api.routes")
        
    Examples:
        "api/routes.py" -> "api.routes"
        "core/__init__.py" -> "core"
        "worker/tasks.py" -> "worker.tasks"
    """
    path = Path(filepath)
    
    # Remove .py extension
    if path.suffix == ".py":
        path = path.with_suffix("")
    
    # Convert path separators to dots
    parts = list(path.parts)
    
    # Handle __init__.py files (represent the package)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    
    return ".".join(parts)


def resolve_import(
    imp: Dict[str, Any],
    from_file: str,
    root_path: str,
    file_to_module: Dict[str, str]
) -> Optional[str]:
    """
    Resolve an import to its target file within the project.
    
    Args:
        imp: Import dictionary from parser
        from_file: File doing the import
        root_path: Project root
        file_to_module: Mapping of files to module names
        
    Returns:
        Target file path, or None if external
    """
    module = imp.get("module", "")
    
    # Handle relative imports
    if module.startswith("."):
        return resolve_relative_import(module, from_file, root_path, file_to_module)
    
    # Handle absolute imports
    return resolve_absolute_import(module, root_path, file_to_module)


def resolve_relative_import(
    module: str,
    from_file: str,
    root_path: str,
    file_to_module: Dict[str, str]
) -> Optional[str]:
    """
    Resolve a relative import (e.g., from .utils import X).
    
    Args:
        module: Relative module name (e.g., ".utils", "..core")
        from_file: File doing the import
        root_path: Project root
        file_to_module: File to module mapping
        
    Returns:
        Target file path, or None
    """
    root = Path(root_path).resolve()
    from_path = (root / from_file).resolve()
    from_dir = from_path.parent
    
    # Count levels
    level = len(module) - len(module.lstrip("."))
    remaining = module.lstrip(".")
    
    # Go up directories
    target_dir = from_dir
    for _ in range(level - 1):
        target_dir = target_dir.parent
    
    # Build target module name
    if remaining:
        target_parts = list(target_dir.relative_to(root).parts) + remaining.split(".")
    else:
        target_parts = list(target_dir.relative_to(root).parts)
    
    target_module = ".".join(target_parts)
    
    # Find matching file
    for filepath, modname in file_to_module.items():
        if modname == target_module:
            return filepath
        # Also check if it's a submodule
        if modname.startswith(target_module + "."):
            return filepath
    
    return None


def resolve_absolute_import(
    module: str,
    root_path: str,
    file_to_module: Dict[str, str]
) -> Optional[str]:
    """
    Resolve an absolute import (e.g., from api.routes import X).
    
    Args:
        module: Module name (e.g., "api.routes")
        root_path: Project root
        file_to_module: File to module mapping
        
    Returns:
        Target file path, or None if external
    """
    # Direct match
    for filepath, modname in file_to_module.items():
        if modname == module:
            return filepath
    
    # Check if it's a submodule (from api.routes import X -> api/routes.py)
    # Split and try progressively
    parts = module.split(".")
    for i in range(len(parts), 0, -1):
        partial = ".".join(parts[:i])
        for filepath, modname in file_to_module.items():
            if modname == partial:
                return filepath
    
    # External module
    return None


def get_service_stats(graph: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get statistics about services in the graph.
    
    Args:
        graph: Dependency graph
        config: Configuration
        
    Returns:
        Dictionary with service statistics
    """
    services = {}
    
    for node in graph["nodes"]:
        service = node["service"]
        if service not in services:
            services[service] = {
                "name": service,
                "module_count": 0,
                "imports_from": 0,
                "imports_to": 0
            }
        services[service]["module_count"] += 1
    
    # Count imports
    for edge in graph["edges"]:
        from_node = next((n for n in graph["nodes"] if n["id"] == edge["from"]), None)
        to_node = next((n for n in graph["nodes"] if n["id"] == edge["to"]), None)
        
        if from_node and to_node:
            from_service = from_node["service"]
            to_service = to_node["service"]
            
            if from_service in services:
                services[from_service]["imports_from"] += 1
            if to_service in services:
                services[to_service]["imports_to"] += 1
    
    return services
