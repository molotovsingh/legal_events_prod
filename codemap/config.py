"""
Configuration loader and validator for CodeMap.
Loads .codemap.yaml files and provides default configuration.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


def find_config(start_path: str = ".") -> Optional[Path]:
    """
    Search for .codemap.yaml config file.
    
    Search order:
    1. .codemap.yaml in start_path
    2. codemap.yaml in start_path
    3. ~/.codemap.yaml (global defaults)
    
    Args:
        start_path: Directory to start searching from
        
    Returns:
        Path to config file, or None if not found
    """
    start = Path(start_path).resolve()
    
    # Check local configs
    for filename in [".codemap.yaml", "codemap.yaml"]:
        config_path = start / filename
        if config_path.exists():
            return config_path
    
    # Check global config
    global_config = Path.home() / ".codemap.yaml"
    if global_config.exists():
        return global_config
    
    return None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. If None, auto-detect.
        
    Returns:
        Configuration dictionary
        
    Raises:
        ConfigError: If config is invalid or not found
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
    else:
        path = find_config()
        if not path:
            return get_default_config()
    
    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {e}")
    except Exception as e:
        raise ConfigError(f"Error reading config file: {e}")
    
    # Validate and merge with defaults
    config = validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate configuration and fill in defaults.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Validated configuration with defaults applied
        
    Raises:
        ConfigError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ConfigError("Config must be a dictionary")
    
    # Ensure required sections exist
    if "project" not in config:
        config["project"] = {}
    if "services" not in config:
        config["services"] = []
    if "rules" not in config:
        config["rules"] = []
    
    # Validate project section
    project = config["project"]
    if "name" not in project:
        project["name"] = "Unnamed Project"
    if "root" not in project:
        project["root"] = "."
    if "exclude" not in project:
        project["exclude"] = ["venv/**", "**/__pycache__/**", "**/*.pyc"]
    
    # Validate services
    for idx, service in enumerate(config["services"]):
        if not isinstance(service, dict):
            raise ConfigError(f"Service {idx} must be a dictionary")
        if "name" not in service:
            raise ConfigError(f"Service {idx} missing 'name' field")
        if "paths" not in service:
            raise ConfigError(f"Service '{service['name']}' missing 'paths' field")
        if not isinstance(service["paths"], list):
            raise ConfigError(f"Service '{service['name']}' paths must be a list")
        if "color" not in service:
            service["color"] = "#808080"  # Default gray
    
    # Validate rules
    for idx, rule in enumerate(config["rules"]):
        if not isinstance(rule, dict):
            raise ConfigError(f"Rule {idx} must be a dictionary")
        if "name" not in rule:
            raise ConfigError(f"Rule {idx} missing 'name' field")
        if "severity" not in rule:
            rule["severity"] = "warning"
        if rule["severity"] not in ["error", "warning", "info"]:
            raise ConfigError(f"Rule '{rule['name']}' has invalid severity: {rule['severity']}")
        
        # Validate rule type
        rule_type = rule.get("type", "cannot_import")
        if rule_type == "cannot_import":
            if "from" not in rule:
                raise ConfigError(f"Rule '{rule['name']}' missing 'from' field")
            if "cannot_import" not in rule:
                raise ConfigError(f"Rule '{rule['name']}' missing 'cannot_import' field")
        elif rule_type == "pattern":
            if "pattern" not in rule:
                raise ConfigError(f"Rule '{rule['name']}' missing 'pattern' field")
        
        if "message" not in rule:
            rule["message"] = f"Violation of rule: {rule['name']}"
    
    # Add default visualization settings
    if "visualization" not in config:
        config["visualization"] = {}
    viz = config["visualization"]
    if "group_by" not in viz:
        viz["group_by"] = "service"
    if "show_violations_only" not in viz:
        viz["show_violations_only"] = False
    if "layout" not in viz:
        viz["layout"] = "hierarchical"
    
    # Add default report settings
    if "report" not in config:
        config["report"] = {}
    report = config["report"]
    if "include_snippets" not in report:
        report["include_snippets"] = True
    if "snippet_context" not in report:
        report["snippet_context"] = 3
    if "fail_on_violations" not in report:
        report["fail_on_violations"] = False
    if "fail_on" not in report:
        report["fail_on"] = ["error"]
    
    return config


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for projects without config files.
    
    Returns:
        Default configuration dictionary
    """
    return {
        "project": {
            "name": "Unnamed Project",
            "root": ".",
            "exclude": ["venv/**", "**/__pycache__/**", "**/*.pyc", ".git/**"]
        },
        "services": [
            {
                "name": "project",
                "paths": ["**/*.py"],
                "color": "#808080"
            }
        ],
        "rules": [],
        "visualization": {
            "group_by": "service",
            "show_violations_only": False,
            "layout": "hierarchical"
        },
        "report": {
            "include_snippets": True,
            "snippet_context": 3,
            "fail_on_violations": False,
            "fail_on": ["error"]
        }
    }


def init_config(path: str = ".codemap.yaml") -> None:
    """
    Create a template configuration file.
    
    Args:
        path: Path where config file should be created
    """
    template = """# CodeMap Configuration

project:
  name: "My Python Project"
  root: "."
  exclude:
    - "venv/**"
    - "**/__pycache__/**"
    - "**/*.pyc"
    - ".git/**"

# Define your architectural components
services:
  - name: main
    description: "Main application code"
    paths:
      - "src/**/*.py"
    color: "#90EE90"
  
  - name: tests
    description: "Test files"
    paths:
      - "tests/**/*.py"
    color: "#87CEEB"

# Define architectural rules
rules:
  - name: example-rule
    severity: warning
    type: cannot_import
    from: "src/**/*.py"
    cannot_import: "tests/**/*.py"
    message: "Main code should not import test code"

visualization:
  group_by: service
  show_violations_only: false
  layout: hierarchical

report:
  include_snippets: true
  snippet_context: 3
  fail_on_violations: false
  fail_on: ["error"]
"""
    
    output_path = Path(path)
    if output_path.exists():
        raise ConfigError(f"Config file already exists: {path}")
    
    with open(output_path, 'w') as f:
        f.write(template)
    
    print(f"✓ Created config template: {path}")
    print("  Edit this file to customize rules for your project")
