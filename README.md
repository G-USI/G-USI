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

**Zero-config setup** - Just create a BUILD file:

```python
# src/python/myapp/migrations/BUILD

alembic_migrations()
```

**That's it!** When Pants processes this target, it automatically:
- ✅ Generates `alembic.ini` with sensible defaults
- ✅ Generates `env.py` with async/sync driver conversion
- ✅ Generates `script.py.mako` migration template
- ✅ Creates `versions/` directory for migrations
- ✅ Infers all dependencies from your imports

Auto-generated targets: `#alembic_dep`, `#env.py`, `#resources`, `#resources2`, `#alembic`, plus database driver dependencies.

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
- ✅ Automatic boilerplate generation - no manual setup needed
- ✅ Clean env.py - async/sync driver conversion built-in
- ✅ Automatic dependency inference - add/remove models, deps update automatically
- ✅ Multi-database support - PostgreSQL, MySQL, SQLite, SQL Server drivers included
- ✅ Optional customization - specify `resolve` only if you need a non-default resolver

Common operations:

```bash
# Generate a migration
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
    revision --autogenerate -m "add_user_table"

# Apply migrations
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
    upgrade head

# Rollback one migration
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
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

#### Zero-Config Setup

To use the Alembic backend, you only need to create **1 file**:

| File | Lines | Purpose |
|------|-------|---------|
| **BUILD** | 1 | `alembic_migrations()` - that's it! |

**All other files are auto-generated** when Pants processes the target:
- ✅ **alembic.ini** - Generated with your migration path
- ✅ **env.py** - Generated with async/sync driver conversion
- ✅ **script.py.mako** - Standard Alembic migration template
- ✅ **versions/** - Empty directory created automatically

**Key features:**
- ✅ **Automatic boilerplate generation** - No manual file creation
- ✅ **Multi-database support** - PostgreSQL, MySQL, SQLite, SQL Server drivers included
- ✅ **Async/sync driver conversion** - Works with asyncpg, aiomysql, etc.
- ✅ **Zero configuration** - Sensible defaults for everything
- ✅ **No `__init__.py` files** - Not needed
- ✅ **No explicit dependencies** - Pants infers everything from imports

#### Step-by-Step Setup

**1. Create the migrations directory:**

```bash
mkdir -p src/python/myapp/migrations
```

**2. Create BUILD file:**

```python
# src/python/myapp/migrations/BUILD

alembic_migrations()
```

**3. Trigger boilerplate generation:**

```bash
# Any pants command that processes the target will generate boilerplate
pants list src/python/myapp/migrations::
```

**That's it!** The plugin automatically generates:
- `alembic.ini` - with `script_location` pointing to your migrations directory
- `env.py` - with database URL from environment variable and async/sync driver conversion
- `script.py.mako` - standard Alembic migration template
- `versions/` - empty directory for migration files

**4. Customize the generated `env.py` (optional):**

Edit the auto-generated `env.py` to import your models:

```python
# Update this line in the generated env.py
from myapp.models import Base

# And this line
target_metadata = Base.metadata
```

**5. Set your database URL:**

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"
# or
export DATABASE_URL="postgresql://user:pass@localhost/db"
```

The plugin automatically converts async drivers to sync for Alembic compatibility.

#### Generated Targets

The `alembic_migrations()` macro automatically generates these targets:

- **`#alembic`** - Alembic CLI with all database drivers included
- **`#alembic_dep`** - Alembic package dependency
- **`#env.py`** - Migration environment file
- **`#resources`** - alembic.ini configuration
- **`#resources2`** - script.py.mako template
- **Database driver dependencies** - psycopg2, asyncpg, PyMySQL, aiomysql, aiosqlite, pyodbc, aioodbc

#### Usage Commands

```bash
# Generate a new migration
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
    revision --autogenerate -m "add_user_table"

# Apply all pending migrations
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
    upgrade head

# Rollback the last migration
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
    downgrade -1

# Check current migration version
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
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
    └── BUILD              # alembic_migrations() - 1 line!
```

**After running any pants command, auto-generated files appear:**

```
src/python/myapp/migrations/
├── BUILD                  # Your 1-line file
├── alembic.ini           # ✓ Auto-generated
├── env.py                 # ✓ Auto-generated (customize imports)
├── script.py.mako        # ✓ Auto-generated
└── versions/              # ✓ Auto-created directory
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

Exports the `alembic_migrations()` macro via target generator.

**Parameters:**
- `resolve` - (Optional) Python resolver to use. Defaults to `python-default` if not specified.

**Features:**
- ✅ **Automatic boilerplate generation** - Creates `alembic.ini`, `env.py`, `script.py.mako`, `versions/` on first run
- ✅ **Multi-database support** - Includes drivers for PostgreSQL, MySQL, SQLite, SQL Server (both sync and async)
- ✅ **Async/sync driver conversion** - Automatically converts `postgresql+asyncpg://` → `postgresql://` for Alembic
- ✅ **Zero configuration** - Just create `BUILD` file with `alembic_migrations()`
- ✅ **Automatic dependency inference** - Pants infers all dependencies from imports in env.py

**Auto-generates targets:**
- `#alembic` - Main Alembic CLI binary
- `#alembic_dep`, `#env.py`, `#resources`, `#resources2` - Component targets
- Database driver dependencies: `#psycopg2_dep`, `#asyncpg_dep`, `#pymysql_dep`, `#aiomysql_dep`, `#aiosqlite_dep`, `#pyodbc_dep`, `#aioodbc_dep`

**Implementation:**
- Uses target generator pattern for dynamic file generation
- Fully self-contained - no external dependencies on plugin source
- Distributable via PyPI or git submodule

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
