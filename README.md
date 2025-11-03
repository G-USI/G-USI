# pants-utils

Reusable Pants build system utilities for Python projects, including custom backend plugins and macros.

## Overview

This repository provides:
- **Pants Backends**: Distributable backends that export macros via `BuildFileAliases`
  - `gusi.pants.backend.alembic` - Exports `alembic_migrations()` macro
  - `gusi.pants.backend.python` - Exports `python_library()` and `python_service()` macros

All backends use the isolated `gusi-pants-plugins` resolve, preventing dependency conflicts with consuming repositories.

## Installation

### Option 1: Git Submodule (Recommended)

Add this repository as a git submodule to your Pants project:

```bash
# In your project root
git submodule add https://github.com/G-USI/G-USI.git 3rdparty/pants/g-usi
git submodule update --init --recursive
```

Configure your `pants.toml`:

```toml
[GLOBAL]
pants_version = "2.29.0"  # Or your Pants version

# Add the submodule to Python path so Pants can import the backends
pythonpath = ["%(buildroot)s/3rdparty/pants/g-usi/src/python"]

# Tell Pants this is a subproject with its own BUILD files
subproject_roots = ["3rdparty/pants/g-usi"]

# Load the backends from the submodule
backend_packages.add = [
  "gusi.pants.backend.alembic",  # Alembic migrations backend
  "gusi.pants.backend.python",   # Python library/service backend
  # Note: pants.backend.python is automatically loaded via required_backends()
]

[python]
# Configure Python settings
enable_resolves = true
interpreter_constraints = [">=3.10,<3.15"]

# Your project's resolves
[python.resolves]
python-default = "3rdparty/python/default.lock"
# Add the submodule's resolve (required for building the plugins)
gusi-pants-plugins = "3rdparty/pants/g-usi/3rdparty/python/gusi-pants-plugins.lock"
# Add any additional resolves you need (e.g., python-cuda, python-rocm)

# Optional: Set specific interpreter versions per resolve
[python.resolves_to_interpreter_constraints]
python-default = ["==3.11.*"]
```

**Setting up your project's Python dependencies:**

```bash
# Create your requirements file
mkdir -p 3rdparty/python
cat > 3rdparty/python/requirements.txt <<EOF
# Your project dependencies
fastapi>=0.100.0
uvicorn>=0.20.0
sqlalchemy>=2.0.0
EOF

# Create a BUILD file for your requirements
cat > 3rdparty/python/BUILD <<EOF
python_requirements(
    name="reqs",
    resolve="python-default",
)
EOF

# Generate lockfile for your project's resolve
pants generate-lockfiles --resolve=python-default
```

**Important Notes:**
- You **must** define the `gusi-pants-plugins` resolve in your parent project's `pants.toml` pointing to the submodule's lockfile - this allows Pants to build the plugin code
- The `gusi-pants-plugins` resolve is completely isolated from your project's resolves (e.g., `python-default`), preventing dependency conflicts
- You don't need to add `pants.backend.plugin_development` to your backends - it's only used internally by the submodule
- The submodule is treated as a separate Pants subproject with independent configuration
- Each resolve has its own lockfile and dependency set

### Option 2: Copy Files (Not Recommended)

You can copy the backend/macro files directly into your repository, but this makes updates harder:

```bash
# Copy backends
mkdir -p src/python/gusi/pants/backend
cp -r pants-utils/src/python/gusi/pants/backend/* src/python/gusi/pants/backend/

# Configure pants.toml
[GLOBAL]
pythonpath = ["%(buildroot)s/src/python"]
backend_packages.add = ["gusi.pants.backend.alembic"]
```

### Option 3: PyPI (Future)

When published to PyPI, you'll be able to install via:

```toml
[GLOBAL]
plugins = ["gusi-pants-plugins==1.0.0"]
backend_packages.add = ["gusi.pants.backend.alembic"]
```

## Usage

### Using the Alembic Backend

Create a BUILD file for your migrations:

```python
# src/python/myapp/migrations/BUILD

# Basic usage (zero config!)
alembic_migrations()

# Or with explicit dependencies
alembic_migrations(
    service_models="//src/python/myapp/models",
    service_src="//src/python/myapp/base",
    resolve="python-default",
)
```

This auto-generates sub-targets: `alembic_dep`, `src`, `resources`, `alembic`, `migrate`, `upgrade`, `downgrade`.

Common operations:

```bash
# Generate a migration
pants run //src/python/myapp/migrations:migrations -- \
    --config src/python/myapp/migrations/alembic.ini \
    revision --autogenerate -m "add_user_table"

# Apply migrations
pants run //src/python/myapp/migrations:migrations -- \
    --config src/python/myapp/migrations/alembic.ini \
    upgrade head

# Rollback one migration
pants run //src/python/myapp/migrations:migrations -- \
    --config src/python/myapp/migrations/alembic.ini \
    downgrade -1
```

### Using Macros (if enabled)

#### python_service()

```python
# src/python/myapp/service/BUILD

python_service(
    dependencies=[
        "//src/python/myapp/models",
        "//src/python/myapp/handlers",
    ],
    entry_point="main.py",
    resolve="python-default",
)
```

Run or package:
```bash
pants run //src/python/myapp/service:bin
pants package //src/python/myapp/service:bin-split-src
pants package //src/python/myapp/service:bin-split-reqs
```

#### python_library()

```python
# src/python/myapp/lib/utils/BUILD

python_library(
    dependencies=["//src/python/myapp/lib/config"],
    resolve="python-default",
)
```

## Updating the Submodule

To get the latest updates from this repository:

```bash
# Pull latest changes
cd 3rdparty/pants/g-usi
git pull origin main

# Return to your project root
cd ../../..

# Commit the submodule update
git add 3rdparty/pants/g-usi
git commit -m "Update G-USI pants plugins submodule"
```

## Development

If you're contributing to this repository:

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd pants-utils

# Enter Nix development environment (if using Nix)
nix develop

# Or ensure you have Pants installed
curl --proto '=https' --tlsv1.2 -fsSL https://static.pantsbuild.org/setup/get-pants.sh | bash
```

### Managing Dependencies

This repository uses the `gusi-pants-plugins` resolve for all its internal code. This ensures complete isolation from consuming repositories.

```bash
# Edit requirements
vim 3rdparty/python/requirements.txt

# Regenerate lockfile for gusi-pants-plugins resolve
pants generate-lockfiles --resolve=gusi-pants-plugins

# Commit both files
git add 3rdparty/python/requirements.txt 3rdparty/python/gusi-pants-plugins.lock
git commit -m "Update Python dependencies"
```

### Testing Plugin Changes

```bash
# Verify plugin loads
pants help alembic_migrations

# Check for errors
pants --version
```

## Python Version Support

This repository supports Python 3.10 through 3.14.

Configure in your project's `pants.toml`:
```toml
[python]
interpreter_constraints = [">=3.10,<3.15"]
```

## Available Backends

### gusi.pants.backend.alembic

**Status**: ✅ Available

Exports the `alembic_migrations()` macro via `BuildFileAliases`.

**Parameters:**
- `service_models` - (Optional) Target containing SQLAlchemy models
- `service_src` - (Optional) Target containing service base/settings
- `resolve` - Python resolver to use

**Auto-generates targets:**
- `alembic_dep`, `src`, `resources`, `alembic`, `migrate`, `upgrade`, `downgrade`

**Implementation approach:**
- Uses `BuildFileAliases` to export macros through the backend
- Declares `pants.backend.python` as a required backend via `required_backends()`
- Avoids complex Rules API - keeps macro simplicity
- Fully distributable via PyPI or git submodule

### gusi.pants.backend.python

**Status**: ✅ Available

Exports `python_library()` and `python_service()` macros via `BuildFileAliases`.

**python_library() Parameters:**
- `dependencies` - List of dependency targets
- `resolve` - Python resolver to use

**Auto-generates targets:**
- `reqs` - python_requirements from requirements.txt
- `(default)` - python_sources depending on reqs + dependencies

**python_service() Parameters:**
- `dependencies` - List of specs, resources, libraries
- `entry_point` - Entry point file (default: "main.py")
- `resolve` - Python resolver
- `split_layout` - PEX layout mode for split binaries (default: "packed")

**Auto-generates targets:**
- `reqs` - python_requirements
- `src` - python_sources
- `bin` - Main PEX binary in venv execution mode
- `bin-split-src` - PEX with sources only
- `bin-split-reqs` - PEX with requirements only

### Future Backends

- `gusi.pants.backend.service_utils` - Python service utilities (planned)
- `gusi.pants.backend.asyncapi_python` - AsyncAPI code generation (planned)

## License

See [LICENSE](LICENSE) file.

## Support

For issues or questions:
- Review Pants documentation: https://www.pantsbuild.org/
- Open an issue in this repository
