# Error Log

This document records issues encountered while preparing and running the prototype.

## 1. Running `__main__.py` Directly

### Symptom

Running the package entry file directly caused an import error:

```text
ImportError: attempted relative import with no known parent package
```

Example command that triggered the error:

```bash
/opt/anaconda3/bin/python lc_private_gui/__main__.py
```

### Cause

`lc_private_gui/__main__.py` uses a package-relative import:

```python
from .cli import main
```

When the file is executed directly, Python treats it as a standalone script rather than part of the `lc_private_gui` package. As a result, the relative import has no parent package context.

### Resolution

Use Python's module execution mode from the repository root:

```bash
/opt/anaconda3/bin/python -m lc_private_gui --mode all
```

### Status

Resolved by using the correct command. The source code was intentionally left unchanged.

## 2. Initial Git Repository Setup

### Symptom

The project directory was not a Git repository:

```text
fatal: not a git repository (or any of the parent directories): .git
```

### Cause

The prototype files existed locally, but Git had not been initialized in the project directory.

### Resolution

Initialized a Git repository, added an appropriate `.gitignore`, committed the project files, added the GitHub remote, and pushed the `main` branch.

### Status

Resolved. The repository is now connected to:

```text
https://github.com/Flesdro/Privacy-Preserving-GUI-Agent-Prototype-via-Local-Cloud-LLM-Collaboration.git
```

## 3. Files That Should Not Be Pushed

### Symptom

Generated Python cache files and runtime logs appeared in the project directory:

```text
lc_private_gui/__pycache__/
logs/last_run.json
```

### Cause

Running the prototype creates bytecode cache files and an audit log.

### Resolution

Added `.gitignore` rules to exclude generated files:

```gitignore
__pycache__/
*.py[cod]
logs/
```

### Status

Resolved. Source files, README, and sample data are tracked; caches and runtime logs are ignored.

## 4. README Run Command Mismatch

### Symptom

The original README used a package path that did not match the repository root layout:

```bash
python3 -m prototype.lc_private_gui --mode all
```

### Cause

The package is located directly under the repository root as `lc_private_gui`, not under a parent `prototype` package.

### Resolution

Updated the README command to:

```bash
python3 -m lc_private_gui --mode all
```

### Status

Resolved.

## 5. Expanded Task Set Baseline Failures

### Symptom

After expanding the task set from 3 to 12 tasks, two baseline cases initially failed:

- `cloud_only` selected an existing alarm instead of the add-alarm button.
- `local_only` selected an existing private note instead of the note title field.

### Cause

The heuristic LLM rules were originally written for only three task types. The expanded task set introduced new intent types and denser UI layouts, exposing gaps in the simple keyword matching and block ranking behavior.

### Resolution

Updated the heuristic decision rules in `lc_private_gui/llm.py`:

- add-alarm tasks now prioritize `add`, `new`, and `create` controls.
- new task intents were added for email, messages, maps, shopping, bank transfer, settings, notes, and alarms.

Adjusted the Notes sample UI to include a separate folders/filter panel so layout-aware partitioning can produce clearer blocks.

### Status

Resolved. The expanded task set now runs successfully:

```text
collaborative: 12/12 tasks successful
cloud_only: 12/12 tasks successful
local_only: 12/12 tasks successful
```

