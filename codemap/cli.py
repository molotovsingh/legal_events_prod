"""
Command-line interface for CodeMap.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from .config import load_config, init_config, find_config, ConfigError
from .parser import parse_directory
from .graph import build_graph, get_service_stats
from .analyzer import check_rules, categorize_violations, generate_summary


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="codemap",
        description="Universal codebase visualization and architectural rule checking"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan project and check rules")
    scan_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project root directory (default: current directory)"
    )
    scan_parser.add_argument(
        "--config",
        "-c",
        help="Path to config file (default: auto-detect)"
    )
    scan_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    
    # validate command (for CI/CD)
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate architecture (exit 1 if violations found)"
    )
    validate_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project root directory"
    )
    validate_parser.add_argument(
        "--config",
        "-c",
        help="Path to config file"
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings too (not just errors)"
    )
    
    # init command
    init_parser = subparsers.add_parser("init", help="Create config template")
    init_parser.add_argument(
        "--path",
        "-p",
        default=".codemap.yaml",
        help="Config file path (default: .codemap.yaml)"
    )
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show codebase statistics")
    stats_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project root directory"
    )
    stats_parser.add_argument(
        "--config",
        "-c",
        help="Path to config file"
    )
    
    args = parser.parse_args()
    
    # Handle commands
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        if args.command == "init":
            return cmd_init(args)
        elif args.command == "scan":
            return cmd_scan(args)
        elif args.command == "validate":
            return cmd_validate(args)
        elif args.command == "stats":
            return cmd_stats(args)
        else:
            parser.print_help()
            return 1
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.command in ["scan", "validate", "stats"] and getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 1


def cmd_init(args) -> int:
    """Initialize config file."""
    try:
        init_config(args.path)
        return 0
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_scan(args) -> int:
    """Scan project and display violations."""
    # Load config
    config_path = args.config if hasattr(args, "config") else None
    config = load_config(config_path)
    
    if args.verbose:
        config_file = find_config(args.path) if not config_path else Path(config_path)
        if config_file:
            print(f"Using config: {config_file}")
        else:
            print("Using default config (no .codemap.yaml found)")
        print()
    
    # Parse files
    root_path = Path(args.path).resolve()
    if args.verbose:
        print(f"Scanning: {root_path}")
        print()
    
    exclude_patterns = config["project"].get("exclude", [])
    parsed_files = parse_directory(str(root_path), exclude_patterns)
    
    if args.verbose:
        print(f"Parsed {len(parsed_files)} files")
        errors = [p for p in parsed_files if "error" in p]
        if errors:
            print(f"  ({len(errors)} files had parse errors)")
        print()
    
    # Build graph
    graph = build_graph(parsed_files, config, str(root_path))
    
    # Check rules
    violations = check_rules(graph, config)
    
    # Display summary
    print(generate_summary(violations, graph))
    
    # Display service breakdown if verbose
    if args.verbose and graph["nodes"]:
        print("\nService Breakdown:")
        print("-" * 60)
        service_stats = get_service_stats(graph, config)
        for service_name, stats in sorted(service_stats.items()):
            print(f"\n{service_name}:")
            print(f"  Modules: {stats['module_count']}")
            print(f"  Imports from this service: {stats['imports_from']}")
            print(f"  Imports to this service: {stats['imports_to']}")
    
    return 0


def cmd_validate(args) -> int:
    """Validate project (for CI/CD)."""
    # Load config
    config = load_config(args.config if hasattr(args, "config") else None)
    
    # Parse files
    root_path = Path(args.path).resolve()
    exclude_patterns = config["project"].get("exclude", [])
    parsed_files = parse_directory(str(root_path), exclude_patterns)
    
    # Build graph
    graph = build_graph(parsed_files, config, str(root_path))
    
    # Check rules
    violations = check_rules(graph, config)
    
    # Categorize
    categorized = categorize_violations(violations)
    
    # Determine if we should fail
    should_fail = False
    fail_on = config.get("report", {}).get("fail_on", ["error"])
    
    if args.strict:
        # Fail on any violation
        should_fail = len(violations) > 0
    else:
        # Fail only on specified severities
        for severity in fail_on:
            if categorized.get(severity):
                should_fail = True
                break
    
    # Print results
    print(generate_summary(violations, graph))
    
    if should_fail:
        print("\n✗ Validation failed", file=sys.stderr)
        return 1
    else:
        print("\n✓ Validation passed")
        return 0


def cmd_stats(args) -> int:
    """Show codebase statistics."""
    # Load config
    config = load_config(args.config if hasattr(args, "config") else None)
    
    # Parse files
    root_path = Path(args.path).resolve()
    exclude_patterns = config["project"].get("exclude", [])
    parsed_files = parse_directory(str(root_path), exclude_patterns)
    
    # Build graph
    graph = build_graph(parsed_files, config, str(root_path))
    
    # Display stats
    print("=" * 60)
    print(f"CodeMap Statistics: {config['project'].get('name', 'Project')}")
    print("=" * 60)
    print()
    
    print(f"Total Python files: {graph['file_count']}")
    print(f"Total imports: {graph['import_count']}")
    print(f"External dependencies: {len(graph['external'])}")
    print()
    
    # Service stats
    service_stats = get_service_stats(graph, config)
    print("Services:")
    print("-" * 60)
    for service_name, stats in sorted(service_stats.items()):
        print(f"\n{service_name}:")
        print(f"  Modules: {stats['module_count']}")
        print(f"  Outgoing imports: {stats['imports_from']}")
        print(f"  Incoming imports: {stats['imports_to']}")
    
    print()
    
    # Top external dependencies
    if graph["external"]:
        print("\nTop External Dependencies:")
        print("-" * 60)
        for dep in sorted(graph["external"])[:20]:
            print(f"  - {dep}")
        if len(graph["external"]) > 20:
            print(f"  ... and {len(graph['external']) - 20} more")
    
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
