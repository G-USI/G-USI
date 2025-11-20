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

# Ignore the submodule directory to prevent Pants from scanning its BUILD files
pants_ignore.add = ["3rdparty/pants/g-usi"]

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
- You **must** add the submodule path to `pants_ignore` (e.g., `pants_ignore.add = ["3rdparty/pants/g-usi"]`) to prevent Pants from scanning the plugin's BUILD files during exports
- The plugin loads via `pythonpath` and doesn't need its own resolve or `subproject_roots` configuration
- You don't need to add `pants.backend.plugin_development` to your backends - it's only used internally by the submodule

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

# Zero-config usage - Pants automatically infers everything!
alembic_migrations()
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
- ✅ Zero-config BUILD files - literally just `alembic_migrations()`
- ✅ Clean env.py - no path manipulation code
- ✅ Automatic updates - add/remove models, deps update automatically
- ✅ Works with any project structure - as long as Pants can see your Python files
- ✅ Optional customization - specify `resolve` only if you need a non-default resolver

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

To use the Alembic backend, create these **4 minimal files** in your migrations directory (e.g., `src/python/myapp/migrations/`):

| File | Lines | Purpose |
|------|-------|---------|
| **BUILD** | 1 | `alembic_migrations()` - that's it! |
| **alembic.ini** | 2 | Just `[alembic]` section with `script_location` |
| **env.py** | 37 | Import Base, configure migrations |
| **script.py.mako** | 22 | Template for generated migrations |
| **versions/** | 0 | Empty directory (migrations go here) |

**Total: 62 lines** (vs 150+ in typical Alembic setup with logging config)

**Key differences from standard Alembic:**
- ✅ **No logging configuration** - Alembic has sensible defaults
- ✅ **No database URL in config** - Use environment variable instead
- ✅ **No sys.path manipulation** - Plugin handles it automatically
- ✅ **No type hints required** - Simpler code
- ✅ **No `__init__.py` files** - Not needed
- ✅ **No explicit dependencies** - Pants infers everything

Files you need:
1. **BUILD** - One line: `alembic_migrations()`
2. **alembic.ini** - One config line
3. **env.py** - Import Base, run migrations
4. **script.py.mako** - Migration template
5. **versions/** - Empty directory

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
)
```

**3. Create alembic.ini:**

```ini
# src/python/myapp/migrations/alembic.ini

[alembic]
script_location = %(here)s
```

**That's it!** Just one line:
- `script_location = %(here)s` tells Alembic where to find migration files
- Database URL? Use environment variable in env.py instead
- Logging? Alembic has sensible defaults

**4. Create env.py:**

```python
# src/python/myapp/migrations/env.py

from alembic import context
from sqlalchemy import engine_from_config, pool
import os

# Import your models - adjust to your project structure
from myapp.models import Base

config = context.config
target_metadata = Base.metadata


def get_url():
    return os.getenv("DATABASE_URL", "postgresql://localhost/mydb")


def run_migrations_offline():
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
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

**That's it!** The essentials:
- Import your models' `Base`
- Set `target_metadata = Base.metadata`
- Database URL from environment variable (optional fallback)

**5. Create script.py.mako:**

```mako
# src/python/myapp/migrations/script.py.mako

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
```

**Simplified:**
- No type hints (Alembic doesn't require them)
- Clean and minimal

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

Here's the **absolute minimum** to get started:

```
src/python/myapp/
├── models.py              # Your SQLAlchemy models with Base
├── BUILD                  # python_sources()
├── requirements.txt       # sqlalchemy>=2.0.0, alembic>=1.13.0
└── migrations/
    ├── BUILD              # alembic_migrations() - 1 line!
    ├── alembic.ini        # 2 lines: [alembic] + script_location
    ├── env.py             # 37 lines: import Base, run migrations
    ├── script.py.mako     # 22 lines: migration template
    └── versions/          # Empty directory
```

**No `__init__.py` files needed anywhere!**

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
- `resolve` - (Optional) Python resolver to use. Defaults to `python-default` if not specified.

All dependencies are automatically inferred from imports in env.py. Zero configuration needed!

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
