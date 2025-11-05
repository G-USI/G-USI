# pants-utils

Reusable Pants build system utilities for Python projects, including custom backend plugins and macros.

## Overview

This repository provides:
- **Pants Backends**: Distributable backends that export macros via `BuildFileAliases`
  - `gusi.pants.backend.alembic` - Exports `alembic_migrations()` macro

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

# Recommended usage - Pants automatically infers dependencies!
alembic_migrations(
    resolve="python-default",
)

# Optional: Explicit dependencies (rarely needed)
# Only use if you have a non-standard project structure
alembic_migrations(
    service_models="//src/python/myapp/models",
    service_src="//src/python/myapp/base",
    resolve="python-default",
)
```

This auto-generates sub-targets: `alembic_dep`, `src`, `resources`, `alembic`, `migrate`, `upgrade`, `downgrade`.

#### How Automatic Dependency Inference Works

The Alembic backend leverages Pants' built-in Python import inference:

1. **You write clean imports in env.py:**
   ```python
   from myapp.models import Base
   from myapp.settings import settings
   ```

2. **Pants automatically discovers dependencies** - No need to specify `service_models` in BUILD!

3. **CLI wrappers set up sys.path** - Automatically detects and adds source roots (`src/python`, `src/py`, `src`, or `lib`)

4. **Everything just works** - No manual sys.path manipulation, no explicit dependency declarations

**Benefits:**
- ✅ Simpler BUILD files - just specify `resolve`
- ✅ Clean env.py - no path manipulation code
- ✅ Automatic updates - add/remove models, deps update automatically
- ✅ Works with any project structure - as long as Pants can see your Python files

Common operations:

```bash
# Generate a migration
pants run '//src/python/myapp/migrations#generate' -- \
    revision --autogenerate -m "add_user_table"

# Apply migrations
pants run '//src/python/myapp/migrations#upgrade' -- \
    upgrade head

# Rollback one migration
pants run '//src/python/myapp/migrations#downgrade' -- \
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

## Documentation

### Alembic Backend - Complete Setup Guide

#### Minimum Required Files

To use the Alembic backend, create these files in your migrations directory (e.g., `src/python/myapp/migrations/`):

1. **BUILD** - Pants build configuration with `alembic_migrations()` macro
2. **alembic.ini** - Alembic configuration file
3. **env.py** - Alembic environment script that imports your models
4. **script.py.mako** - Template for generating migration files
5. **versions/** - Empty directory where migration files will be generated

**Important:** No `__init__.py` files or `.gitkeep` files are needed!

#### Step-by-Step Setup

**1. Create the migrations directory:**

```bash
mkdir -p src/python/myapp/migrations/versions
```

**2. Create BUILD file:**

```python
# src/python/myapp/migrations/BUILD

alembic_migrations(
    name="migrations",
    resolve="python-default",
)

# Note: service_models is optional! Pants automatically infers dependencies
# from imports in env.py. Only specify if you have a non-standard structure.
```

**3. Create alembic.ini:**

```ini
# src/python/myapp/migrations/alembic.ini

[alembic]
# Use %(here)s to make config portable - it resolves to the directory containing this file
script_location = %(here)s

# Database URL (can be overridden via environment variable in env.py)
sqlalchemy.url = postgresql://user:pass@localhost:5432/mydb

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**4. Create env.py:**

```python
# src/python/myapp/migrations/env.py

"""Alembic environment configuration."""

from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your models' Base to enable autogeneration
# Use absolute imports - the CLI wrappers automatically set up sys.path
from myapp.models import Base  # Adjust to your project structure

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata


def get_url():
    """Get database URL from environment or config."""
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Important Notes:**
- **No sys.path manipulation needed!** The CLI wrappers automatically set up source roots
- Use clean absolute imports (e.g., `from myapp.models import Base`)
- Pants will automatically infer the dependency from your import statement

**5. Create script.py.mako:**

```mako
# src/python/myapp/migrations/script.py.mako

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

#### Generated Targets

The `alembic_migrations()` macro automatically generates these targets:

- **`#generate`** - Generate new migrations with auto-config detection (uses `migrate_main` wrapper)
- **`#upgrade`** - Apply migrations to database (uses `upgrade_main` wrapper)
- **`#downgrade`** - Rollback migrations (uses `downgrade_main` wrapper)
- **`#alembic`** - Raw Alembic CLI for advanced operations

The `#generate`, `#upgrade`, and `#downgrade` targets automatically find your `alembic.ini` file, so you don't need to specify `--config` manually.

#### Usage Commands

```bash
# Generate a new migration (auto-detects alembic.ini)
pants run '//src/python/myapp/migrations#generate' -- \
    revision --autogenerate -m "add_user_table"

# Apply all pending migrations
pants run '//src/python/myapp/migrations#upgrade' -- \
    upgrade head

# Rollback the last migration
pants run '//src/python/myapp/migrations#downgrade' -- \
    downgrade -1

# Advanced: Use raw alembic CLI (requires --config flag)
pants run '//src/python/myapp/migrations#alembic' -- \
    --config src/python/myapp/migrations/alembic.ini \
    current
```

#### Complete Working Example

Here's a minimal working example showing all required files:

```
src/python/myapp/
├── __init__.py
├── models.py              # Your SQLAlchemy models
├── BUILD
├── requirements.txt       # Include: sqlalchemy>=2.0.0, alembic>=1.13.0
└── migrations/
    ├── BUILD              # alembic_migrations() macro
    ├── alembic.ini        # script_location = %(here)s
    ├── env.py             # Imports models.Base
    ├── script.py.mako     # Migration template
    └── versions/          # Empty directory (no files needed)
```

**models.py example:**

```python
from sqlalchemy import String, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
```

**requirements.txt:**

```
sqlalchemy>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0  # For PostgreSQL async support
```

#### Common Issues

**1. "Can't find Python file env.py"**
- Solution: Ensure `script_location = %(here)s` in `alembic.ini` (not an absolute path)

**2. "script.py.mako not found"**
- Solution: Create the `script.py.mako` template file in your migrations directory

**3. "Target database is not up to date"**
- Solution: Run `pants run '//src/python/myapp/migrations#upgrade'` before generating new migrations

**4. "Can't locate revision"**
- Solution: Ensure all migration files are in the `versions/` directory and the database is in sync

**5. Import errors in env.py**
- Solution: Use clean absolute imports (e.g., `from myproject.myapp.models import Base`)
- The CLI wrappers automatically set up source roots in sys.path
- Pants will infer dependencies from your imports - no need to specify `service_models`
- Ensure your models are in a target that Pants can discover (use `python_sources()` in BUILD files)

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
- `resolve` - (Required) Python resolver to use
- `service_models` - (Optional, rarely needed) Target containing SQLAlchemy models. Pants automatically infers this from imports in env.py
- `service_src` - (Optional, rarely needed) Target containing service base/settings. Only needed for non-standard project structures

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
