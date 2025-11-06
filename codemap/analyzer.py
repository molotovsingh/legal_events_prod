"""
Architectural rule analyzer.
Checks dependency graph against configured rules and finds violations.
"""

import re
from typing import Dict, List, Any, Optional
from fnmatch import fnmatch


def check_rules(
    graph: Dict[str, Any],
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Check all rules against the dependency graph.
    
    Args:
        graph: Dependency graph from graph.build_graph()
        config: Configuration dictionary
        
    Returns:
        List of violations
    """
    rules = config.get("rules", [])
    all_violations = []
    
    for rule in rules:
        rule_type = rule.get("type", "cannot_import")
        
        if rule_type == "cannot_import":
            violations = check_cannot_import_rule(graph, rule)
            all_violations.extend(violations)
        elif rule_type == "pattern":
            violations = check_pattern_rule(graph, rule)
            all_violations.extend(violations)
        elif rule_type == "must_import":
            violations = check_must_import_rule(graph, rule)
            all_violations.extend(violations)
    
    return all_violations


def check_cannot_import_rule(
    graph: Dict[str, Any],
    rule: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Check a 'cannot_import' rule.
    
    Example rule:
    {
        "name": "no-api-imports-worker",
        "from": "api/**/*.py",
        "cannot_import": "worker/**/*.py",
        "severity": "error",
        "message": "API should not import Worker"
    }
    
    Args:
        graph: Dependency graph
        rule: Rule configuration
        
    Returns:
        List of violations
    """
    violations = []
    from_pattern = rule.get("from", "")
    cannot_import_patterns = rule.get("cannot_import", [])
    
    # Ensure cannot_import is a list
    if isinstance(cannot_import_patterns, str):
        cannot_import_patterns = [cannot_import_patterns]
    
    for edge in graph["edges"]:
        from_file = edge["from_file"]
        to_file = edge["to_file"]
        
        # Check if source file matches the 'from' pattern
        if not match_pattern_any(from_file, from_pattern):
            continue
        
        # Check if target file matches any 'cannot_import' pattern
        if match_pattern_any(to_file, cannot_import_patterns):
            violation = {
                "rule": rule["name"],
                "severity": rule.get("severity", "warning"),
                "type": "cannot_import",
                "file": from_file,
                "imported_file": to_file,
                "from_module": edge["from"],
                "to_module": edge["to"],
                "line": edge.get("line"),
                "message": rule.get("message", f"Violation of rule: {rule['name']}")
            }
            violations.append(violation)
    
    return violations


def check_pattern_rule(
    graph: Dict[str, Any],
    rule: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Check a regex pattern rule (e.g., detect relative imports).
    
    Example rule:
    {
        "name": "no-relative-imports",
        "pattern": "^from \\\\.\\\\.",
        "severity": "warning",
        "message": "Avoid relative imports"
    }
    
    Args:
        graph: Dependency graph
        rule: Rule configuration
        
    Returns:
        List of violations
    """
    violations = []
    pattern = rule.get("pattern", "")
    
    try:
        regex = re.compile(pattern)
    except re.error as e:
        print(f"Warning: Invalid regex pattern in rule '{rule['name']}': {e}")
        return violations
    
    # Check imports for pattern matches
    for edge in graph["edges"]:
        # Reconstruct the import statement to check pattern
        import_type = edge.get("import_type", "import")
        to_module = edge.get("to_module", edge.get("to", ""))
        
        if not to_module:
            continue
        
        if import_type == "from":
            import_statement = f"from {to_module} import"
        else:
            import_statement = f"import {to_module}"
        
        if regex.search(import_statement):
            violation = {
                "rule": rule["name"],
                "severity": rule.get("severity", "warning"),
                "type": "pattern",
                "file": edge["from_file"],
                "line": edge.get("line"),
                "pattern": pattern,
                "matched": import_statement,
                "message": rule.get("message", f"Violation of rule: {rule['name']}")
            }
            violations.append(violation)
    
    return violations


def check_must_import_rule(
    graph: Dict[str, Any],
    rule: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Check a 'must_import' rule (files must import certain modules).
    
    Example rule:
    {
        "name": "tests-must-import-pytest",
        "from": "tests/**/*.py",
        "must_import": "pytest",
        "severity": "warning"
    }
    
    Args:
        graph: Dependency graph
        rule: Rule configuration
        
    Returns:
        List of violations
    """
    violations = []
    from_pattern = rule.get("from", "")
    must_import = rule.get("must_import", "")
    
    # Find all files matching 'from' pattern
    matching_files = set()
    for node in graph["nodes"]:
        if match_pattern_any(node["file"], from_pattern):
            matching_files.add(node["file"])
    
    # Check which files have the required import
    files_with_import = set()
    for edge in graph["edges"]:
        if edge["from_file"] in matching_files:
            if must_import in edge["to_module"]:
                files_with_import.add(edge["from_file"])
    
    # Files without the required import are violations
    for file in matching_files - files_with_import:
        violation = {
            "rule": rule["name"],
            "severity": rule.get("severity", "warning"),
            "type": "must_import",
            "file": file,
            "required_import": must_import,
            "message": rule.get("message", f"File must import {must_import}")
        }
        violations.append(violation)
    
    return violations


def match_pattern_any(filepath: str, patterns: Any) -> bool:
    """
    Check if filepath matches any of the given patterns.
    Supports ** for recursive matching.
    
    Args:
        filepath: File path to check
        patterns: Single pattern string or list of patterns
        
    Returns:
        True if filepath matches any pattern
    """
    from pathlib import PurePath
    
    if isinstance(patterns, str):
        patterns = [patterns]
    
    for pattern in patterns:
        if PurePath(filepath).match(pattern):
            return True
    
    return False


def categorize_violations(violations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize violations by severity.
    
    Args:
        violations: List of violations
        
    Returns:
        Dictionary with keys: error, warning, info
    """
    categorized = {
        "error": [],
        "warning": [],
        "info": []
    }
    
    for violation in violations:
        severity = violation.get("severity", "warning")
        if severity in categorized:
            categorized[severity].append(violation)
    
    return categorized


def format_violation(violation: Dict[str, Any], include_snippet: bool = False) -> str:
    """
    Format a violation for display.
    
    Args:
        violation: Violation dictionary
        include_snippet: Whether to include code snippet
        
    Returns:
        Formatted violation string
    """
    severity = violation.get("severity", "warning").upper()
    rule_name = violation.get("rule", "unknown")
    file = violation.get("file", "")
    line = violation.get("line", "")
    message = violation.get("message", "")
    
    # Build base message
    parts = [f"[{severity}] {rule_name}"]
    
    if file:
        parts.append(f"\n  File: {file}")
    if line:
        parts.append(f" (line {line})")
    
    if violation.get("type") == "cannot_import":
        imported = violation.get("imported_file", "")
        if imported:
            parts.append(f"\n  Imports: {imported}")
    
    parts.append(f"\n  {message}")
    
    return "".join(parts)


def generate_summary(
    violations: List[Dict[str, Any]],
    graph: Dict[str, Any]
) -> str:
    """
    Generate a summary report of violations.
    
    Args:
        violations: List of violations
        graph: Dependency graph
        
    Returns:
        Formatted summary string
    """
    categorized = categorize_violations(violations)
    
    lines = []
    lines.append("=" * 60)
    lines.append("CodeMap Analysis Summary")
    lines.append("=" * 60)
    lines.append("")
    
    # Graph stats
    lines.append(f"Files analyzed: {graph.get('file_count', 0)}")
    lines.append(f"Import relationships: {graph.get('import_count', 0)}")
    lines.append("")
    
    # Violation counts
    error_count = len(categorized["error"])
    warning_count = len(categorized["warning"])
    info_count = len(categorized["info"])
    
    lines.append("Violations found:")
    lines.append(f"  Errors:   {error_count}")
    lines.append(f"  Warnings: {warning_count}")
    lines.append(f"  Info:     {info_count}")
    lines.append("")
    
    if not violations:
        lines.append("✓ No violations found!")
        lines.append("")
        return "\n".join(lines)
    
    # List violations by severity
    for severity in ["error", "warning", "info"]:
        items = categorized[severity]
        if items:
            lines.append(f"\n{severity.upper()}S:")
            lines.append("-" * 60)
            for violation in items:
                lines.append("")
                lines.append(format_violation(violation))
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)
