# CodeMap - Universal Codebase Visualization Tool

## Overview

A lightweight, **project-agnostic** tool to visualize code structure and dependencies in any Python codebase.

## Purpose

- **Understand architecture**: Visualize module relationships and service boundaries
- **Validate guardrails**: Detect custom architectural violations (configurable rules)
- **Onboarding**: Help new developers understand any codebase structure
- **Technical debt**: Identify architectural anti-patterns across projects

## Design Goals

1. **Universal**: Works on ANY Python project, not just this one
2. **Configurable**: Define custom rules via `.codemap.yaml` config files
3. **Simple**: No heavy dependencies, Python stdlib where possible
4. **Fast**: Parse and visualize in seconds
5. **Actionable**: Focus on architectural insights, not just pretty diagrams
6. **Portable**: Can be used as a CLI tool or imported as a library

## Features (MVP)

### Phase 1: Static Analysis
- [ ] Parse Python files using AST
- [ ] Extract imports, classes, functions
- [ ] Build dependency graph (who imports what)
- [ ] Detect cross-service imports (API ↔ Worker violations)

### Phase 2: Visualization
- [ ] Generate Mermaid diagrams
- [ ] HTML report with interactive graph
- [ ] Highlight guardrails violations in red

### Phase 3: Advanced (Future)
- [ ] Data flow tracing (API → Redis → Worker)
- [ ] Database access patterns (who reads/writes what)
- [ ] Call graph analysis (function call chains)

## Architecture

```
codemap/
├── README.md              # This file
├── design.md              # Detailed design doc
├── parser.py              # AST-based code parser
├── graph.py               # Graph builder and analyzer
├── visualizer.py          # Mermaid/HTML generator
├── analyzer.py            # Guardrails violation detector
├── main.py                # CLI entry point
└── output/                # Generated reports
```

## Usage (Planned)

```bash
# Analyze any project
python codemap/main.py scan /path/to/any/project

# Use config file for custom rules
python codemap/main.py scan . --config .codemap.yaml

# Generate visualizations
python codemap/main.py visualize --format html --open
python codemap/main.py visualize --format mermaid --output diagram.md

# Validate architectural rules (CI/CD)
python codemap/main.py validate --strict --config .codemap.yaml

# Interactive exploration
python codemap/main.py serve --port 8080  # Web UI
```

## Configuration Example

Create `.codemap.yaml` in your project root:

```yaml
# Define your project structure
services:
  - name: api
    paths: ["api/**/*.py"]
    color: "#90EE90"
  
  - name: worker
    paths: ["worker/**/*.py"]
    color: "#87CEEB"
  
  - name: shared
    paths: ["core/**/*.py", "utils/**/*.py"]
    color: "#FFD700"

# Define architectural rules
rules:
  - name: no-api-imports-worker
    severity: error
    from: "api/**/*.py"
    cannot_import: "worker/**/*.py"
    message: "API should not import Worker directly. Use RQ queues."
  
  - name: no-worker-imports-api
    severity: error
    from: "worker/**/*.py"
    cannot_import: "api/**/*.py"
    message: "Worker should not import API directly."
  
  - name: prefer-absolute-imports
    severity: warning
    pattern: "^from \\.\\."
    message: "Prefer absolute imports over relative imports."
```

## Inspiration

Inspired by Windsurf Codemaps but simplified for our specific use case.
