# g-usi

A nix monorepo with two roles in one repo:

1. **Pants packaging** - run the [Pants](https://www.pantsbuild.org/) build
   system from Nix, natively on any Linux machine, NixOS included. Every
   stable Pants release from **2.21.0 through 2.33.1** is packaged, dual-arch
   (x86_64-linux + aarch64-linux), NixOS-native.
2. **gusi pants plugins** - the reusable Pants backend plugins/macros
   (`gusi.pants.backend.*`), developed in this same repo and consumed by
   other repositories via git submodule.

## Compatibility contract & releases

g-usi is consumed through release pins, not branches: annotated `vX.Y.Z`
tags cut from `dev`. The rule that makes the two consumption modes
coherent: **the flake input pin and the plugins submodule pin must
resolve to the SAME tag** - one revision, two pins, bumped together.
The full contract (consumption modes, bump procedure, additive
parameter surface, runtime ownership boundary, support policy) lives in
[docs/COMPAT.md](docs/COMPAT.md).

Releases are prepared with `scripts/release.sh vX.Y.Z` (runs
`nix flake check`, creates the annotated tag) and pushed by the human.
The pre-monorepo FHS-era flake (at or before `31bb99f`) is retired -
see [FHS retirement](docs/COMPAT.md#fhs-retirement).

## Layout

```
.
|-- flake.nix                  # Flake entry: packages, lib, pinned builders, devshells
|-- flake.lock
|-- nix/                       # Nix infrastructure
|   `-- pants/                 # Pants packaging
|       |-- default.nix        # mkPants builder
|       |-- versions.nix       # Version registry (auto-aggregates versions/)
|       |-- versions/          # Per-release version data (generated)
|       |-- patch-caches.sh    # pants-patch-caches runtime sweep
|       `-- scripts/           # generate.py, gen-versions.sh, list-versions.sh
|-- pants.toml                 # Pants config for the plugins (pins the devshell Pants version)
|-- 3rdparty/python/           # Lockfiles for the gusi-pants-plugins resolve
`-- src/python/gusi/           # The pants plugins themselves
```

## Pants from Nix

> URL examples use the current repo name; update on rename.

Ad-hoc run of a specific packaged release (dots become underscores):

```console
$ nix run github:G-USI/G-USI#pants-2_31_0 -- --version
2.31.0
```

A specific-version shell:

```console
$ nix shell github:G-USI/G-USI#pants-2_31_0 --command pants --version
2.31.0
```

### Using it in your repo

Add the input - **pinned to a release tag, never a branch** (the
github-mirror equivalent is `github:G-USI/G-USI/vX.Y.Z`):

```nix
inputs.gusi.url = "git+https://codefloe.com/G-USI/g-usi.git?ref=vX.Y.Z";
```

If you also consume the plugins, the submodule must resolve to the same
tag - see [docs/COMPAT.md](docs/COMPAT.md) for the bump procedure and
pin cross-check.

devenv works the same way as with any flake input: add the input, then put
the built package into `devenv.nix`'s `packages` list. Point
`pinned.fromPantsToml` at your `pants.toml` to bind Pants to the version
your repo pins - bumping `[GLOBAL].pants_version` re-resolves the package
on the next eval. Note the file must be **tracked by git** - untracked
files are invisible to flake source and eval fails with a missing-file
error:

```nix
devShells.x86_64-linux.default =
  let
    pkgs = nixpkgs.legacyPackages.x86_64-linux;
  in
  pkgs.mkShell {
    packages = [
      (gusi.pinned.x86_64-linux.fromPantsToml ./pants.toml)
      pkgs.python314   # interpreters your resolves need
      pkgs.cargo       # toolchains sandboxed processes need
      pkgs.rustc
    ];
  };
```

The pinned builders build against this flake's nixpkgs, giving store paths
identical across machines - the precondition for a shared binary cache. To
build against **your** nixpkgs instead, use the lib builders:

```nix
packages = [ (gusi.lib.fromPantsToml pkgs pkgs39 ./pants.toml) ];
# or pick a version explicitly:
packages = [ (gusi.lib.mkPants pkgs pkgs39 { version = "2.31.0"; }) ];
```

where `pkgs39 = gusi.inputs.nixpkgs-py39.legacyPackages.x86_64-linux`
(needed for Pants 2.21-2.24, which ride python 3.9). If your `pants.toml`
lives outside a git-tracked path (e.g. a bare repo without commits), pin
explicitly with `pinned.mkPantsPinned { version = "..."; }`.

### Runtime behavior

- Pants boots on a Nix interpreter and executes the release wheel's
  native engine, patchelf'd against Nix libraries at build time.
- On launch (synchronously, before Pants starts), `pants-patch-caches`
  rewrites generic-Linux binaries Pants downloads into its caches
  (rustup toolchains, interpreters reused by PEX venvs): the
  interpreter becomes the Nix glibc loader and the Nix lib dir is
  **appended** to existing rpaths; shared objects are touched only
  when `ldd` proves unresolvable needs. Atomic, stamp-guarded,
  single-flight - a warm run is a no-op, so the synchronous launch
  costs nothing once caches are patched. Disable with
  `PANTS_NIX_AUTOPATCH=0`. Run it by hand any time with
  `$(nix build --print-out-paths <flake>#pkg)/bin/pants-patch-caches`;
  it reports how many binaries and shared objects it patched.
- Expose the interpreters your resolves need via `extraPythons`
  (`extraPythons = [ pkgs.python314 ];`).
- **Point every downloaded-tool plugin at PATH binaries.** Any Pants
  plugin that downloads an external tool (nodejs, terraform, helm,
  rustup-init, ...) will otherwise fetch a generic-Linux binary that
  cannot run on NixOS. Note the exec happens mid-run from a process
  sandbox, so the cache sweep cannot rescue these - the binary must
  come from the invoking shell's PATH (or the plugin must be configured
  to skip its own download).
  The standard pattern works per subsystem: set its version to one
  **outside** the plugin's `known_versions` (e.g.
  `PANTS_NODEJS_VERSION=24.14.0` - only `v24.10.0` is known for nodejs
  in 2.31) and provide the real binary via the PATH of whatever shell
  invokes Pants (e.g. nix `nodejs` in your devenv). Pants then searches PATH, version-tests the binary, and
  runs it Nix-native. Expect to do this for each downloaded-tool plugin
  your repo enables - leaving any of them on the download path is the
  likely source of `Could not start dynamically linked executable`
  errors on NixOS.
- Tool venvs are cached per constraints - invoke Pants with a
  consistent interpreter set to avoid re-materialization.

### Requirements & limitations

- **Consumption floor**: the first release tag (`v0.1.0`) is the minimum
  supported pin. The pre-monorepo FHS-era flake (at or before `31bb99f`)
  is retired with no upgrade path - the patchelf-native surface replaces
  it outright ([FHS retirement](docs/COMPAT.md#fhs-retirement)).
- x86_64-linux and aarch64-linux (native wheels for both; CI currently
  verifies x86_64 only - arm64 runner coverage is deferred until a
  Codefloe arm label exists). macOS is not supported.
- One interpreter per Pants version (the release wheel's CPython tag):
  2.21-2.24 -> python3.9 (built via the `nixpkgs-py39` input),
  2.25-2.31 -> python3.11, 2.32+ -> python3.14.
- On aarch64, releases 2.27.0-2.32.1 are not packaged: their
  dependency `hdrhistogram` ships no aarch64 wheels at all (upstream
  dropped it in 2.33). Those versions are absent from
  `packages.aarch64-linux` rather than half-broken.
- The devshell for THIS repo's plugins is x86_64-only (it pins
  pants 2.29.0, whose `hdrhistogram` gap applies - see above).
- A `pants` launcher already on PATH shadows this package's binary -
  in shells where both exist, check `which pants`.
- Pants still downloads your resolves at runtime (as upstream); they
  live in Pants' caches, not the Nix store. Downloaded-tool plugins
  (see Runtime behavior) must be re-pointed at PATH binaries - on
  NixOS the download-and-exec path fails out of the box.

## Pants plugins

Reusable Pants build system utilities for Python projects, including custom backend plugins and macros.

### Overview

This repository provides:
- **Pants Backends**: Distributable backends that export macros via `BuildFileAliases`
  - `gusi.pants.backend.alembic` - Exports `alembic_migrations()` macro

All backends use the isolated `gusi-pants-plugins` resolve, preventing dependency conflicts with consuming repositories.

### Installation

#### Option 1: Git Submodule at the Same Tag (Supported)

Add this repository as a git submodule to your Pants project. If you
also use the flake input for the nix environment, the submodule and the
flake input MUST resolve to the same `vX.Y.Z` tag - they are one
dependency, never two ([docs/COMPAT.md](docs/COMPAT.md)):

```bash
# In your project root (checkout the tag your flake input pins)
git submodule add https://codefloe.com/G-USI/g-usi.git 3rdparty/pants/g-usi
git -C 3rdparty/pants/g-usi checkout vX.Y.Z
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

#### Option 2: Copy Files (Outside the Compat Contract)

Copying the backend/macro files directly into your repository is
vendoring: updates can no longer ride a tag bump, the copies drift from
the packaged/tested surface, and it violates the compat contract's
"downstream never patches g-usi" rule
([docs/COMPAT.md](docs/COMPAT.md)). It is kept only as a historical
escape hatch and carries no support. If you must, copy from a
submodule checkout at your pinned tag:

```bash
# Copy backends (from the submodule checked out at your tag)
mkdir -p src/python/gusi/pants/backend
cp -r 3rdparty/pants/g-usi/src/python/gusi/pants/backend/* src/python/gusi/pants/backend/

# Configure pants.toml
[GLOBAL]
pythonpath = ["%(buildroot)s/src/python"]
backend_packages.add = ["gusi.pants.backend.alembic"]
```

#### Option 3: PyPI (Future)

When published to PyPI, you'll be able to install via:

```toml
[GLOBAL]
plugins = ["gusi-pants-plugins==1.0.0"]
backend_packages.add = ["gusi.pants.backend.alembic"]
```

PyPI distribution would be a third consumption mode with its own
version pin; until it exists and the contract is amended to govern it
(same-tag discipline cannot apply to a PyPI version), this option is
out of contract.

### Usage

#### Using the Alembic Backend

**Zero-config setup** - Just create a BUILD file:

```python
# src/python/myapp/migrations/BUILD

alembic_migrations()
```

**That's it!** When Pants processes this target, it automatically:
- Generates `alembic.ini` with sensible defaults
- Generates `env.py` with async/sync driver conversion
- Generates `script.py.mako` migration template
- Creates `versions/` directory for migrations
- Infers all dependencies from your imports

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
- Zero-config BUILD files - literally just `alembic_migrations()`
- Automatic boilerplate generation - no manual setup needed
- Clean env.py - async/sync driver conversion built-in
- Automatic dependency inference - add/remove models, deps update automatically
- Multi-database support - PostgreSQL, MySQL, SQLite, SQL Server drivers included
- Optional customization - specify `resolve` only if you need a non-default resolver

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

#### Using Macros (if enabled)

##### python_service()

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

##### python_library()

```python
# src/python/myapp/lib/utils/BUILD

python_library(
    dependencies=["//src/python/myapp/lib/config"],
    resolve="python-default",
)
```

### Documentation

#### Alembic Backend - Complete Setup Guide

##### Zero-Config Setup

To use the Alembic backend, you only need to create **1 file**:

| File | Lines | Purpose |
|------|-------|---------|
| **BUILD** | 1 | `alembic_migrations()` - that's it! |

**All other files are auto-generated** when Pants processes the target:
- **alembic.ini** - Generated with your migration path
- **env.py** - Generated with async/sync driver conversion
- **script.py.mako** - Standard Alembic migration template
- **versions/** - Empty directory created automatically

**Key features:**
- **Automatic boilerplate generation** - No manual file creation
- **Multi-database support** - PostgreSQL, MySQL, SQLite, SQL Server drivers included
- **Async/sync driver conversion** - Works with asyncpg, aiomysql, etc.
- **Zero configuration** - Sensible defaults for everything
- **No `__init__.py` files** - Not needed
- **No explicit dependencies** - Pants infers everything from imports

##### Step-by-Step Setup

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

##### Generated Targets

The `alembic_migrations()` macro automatically generates these targets:

- **`#alembic`** - Alembic CLI with all database drivers included
- **`#generate`** - Convenience command for `alembic revision --autogenerate`
- **`#upgrade`** - Convenience command for `alembic upgrade head`
- **`#downgrade`** - Convenience command for `alembic downgrade -1`
- **`#alembic_dep`** - Alembic package dependency
- **`#env.py`** - Migration environment file
- **`#resources`** - alembic.ini configuration
- **`#resources2`** - script.py.mako template
- **`#commands`** - Virtual commands.py file (generated dynamically)
- **Database driver dependencies** - #psycopg2_dep, #asyncpg_dep, #pymysql_dep, #aiomysql_dep, #aiosqlite_dep, #pyodbc_dep, #aioodbc_dep

##### Convenience Commands

For common operations, use the convenience command shortcuts:

```bash
# Generate a new migration (autogenerate)
pants run '//src/python/myapp/migrations#generate' -- -m "add_user_table"

# Apply all pending migrations
pants run '//src/python/myapp/migrations#upgrade'

# Rollback the last migration
pants run '//src/python/myapp/migrations#downgrade'
```

These commands automatically handle the config path and common options.

##### Advanced Usage (Full Alembic CLI)

The `#alembic` target automatically detects the config path, so `-c` is optional:

```bash
# Generate a new migration (config path auto-detected)
pants run '//src/python/myapp/migrations#alembic' -- \
    revision --autogenerate -m "add_user_table"

# Apply all pending migrations
pants run '//src/python/myapp/migrations#alembic' -- upgrade head

# Rollback the last migration
pants run '//src/python/myapp/migrations#alembic' -- downgrade -1

# Check current migration version
pants run '//src/python/myapp/migrations#alembic' -- current

# You can still specify -c explicitly if needed
pants run '//src/python/myapp/migrations#alembic' -- \
    -c src/python/myapp/migrations/alembic.ini \
    current
```

##### Complete Working Example

Here's the **absolute minimum** to get started:

```
src/python/myapp/
|-- models.py              # Your SQLAlchemy models with Base
|-- BUILD                  # python_sources()
|-- requirements.txt       # sqlalchemy>=2.0.0, alembic>=1.13.0
`-- migrations/
    `-- BUILD              # alembic_migrations() - 1 line!
```

**After running any pants command, auto-generated files appear:**

```
src/python/myapp/migrations/
|-- BUILD                  # Your 1-line file
|-- alembic.ini           # Auto-generated
|-- env.py                 # Auto-generated (customize imports)
|-- script.py.mako        # Auto-generated
`-- versions/              # Auto-created directory
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

##### Common Issues

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

### Updating the Submodule

Submodule updates are tag bumps, never branch pulls - and if you
consume the flake input too, both pins move to the same tag in one
commit (full procedure and cross-checks:
[docs/COMPAT.md](docs/COMPAT.md)):

```bash
# Move the submodule to a release tag
git -C 3rdparty/pants/g-usi fetch --tags origin
git -C 3rdparty/pants/g-usi checkout vX.Y.Z

# Return to your project root and commit the pin
cd ../../..
git add 3rdparty/pants/g-usi
git commit -m "bump g-usi -> vX.Y.Z"
```

### Convergence Target (Experimental)

The end state retires the submodule: the plugins ride the flake input's
store path, leaving ONE pin. In nix-generated config:

```nix
pythonpath = [ "${inputs.gusi}/src/python" ]
```

or, for a static `pants.toml`, via Pants env interpolation with the
consumer's devenv exporting `GUSI_SRC = "${inputs.gusi}"`:

```toml
[GLOBAL]
pythonpath = ["%(env.GUSI_SRC)s/src/python"]
```

This mode is experimental until proven end to end on a real consumer;
until promoted, dual-pin-same-tag is the contract.

### Development

If you're contributing to this repository:

#### Setup

Prerequisite: devenv must be installed (https://devenv.sh - one-line
install), or use `nix develop` for the pure-flake shell.

```bash
# Enter the development environment (devenv - https://devenv.sh)
devenv shell

# Verify Pants (self-hosted from this repo's own nix/pants packaging)
pants --version

# Plugins import check
pants list src/python/gusi::
```

Pure-flake consumers can use `nix develop` instead - the flake's
`devShells.default` provides the same Pants. Both build against the same
nixpkgs rev, so the derivations are identical and share store paths.

#### Managing Dependencies

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

#### Testing Plugin Changes

```bash
# Verify plugin loads
pants help alembic_migrations

# Check for errors
pants --version
```

### Python Version Support

This repository supports Python 3.10 through 3.14.

Configure in your project's `pants.toml`:
```toml
[python]
interpreter_constraints = [">=3.10,<3.15"]
```

### Available Backends

#### gusi.pants.backend.alembic

**Status**: Available

Exports the `alembic_migrations()` macro via target generator.

**Parameters:**
- `resolve` - (Optional) Python resolver to use. Defaults to `python-default` if not specified.

**Features:**
- **Automatic boilerplate generation** - Creates `alembic.ini`, `env.py`, `script.py.mako`, `versions/` on first run
- **Multi-database support** - Includes drivers for PostgreSQL, MySQL, SQLite, SQL Server (both sync and async)
- **Async/sync driver conversion** - Automatically converts `postgresql+asyncpg://` -> `postgresql://` for Alembic
- **Zero configuration** - Just create `BUILD` file with `alembic_migrations()`
- **Automatic dependency inference** - Pants infers all dependencies from imports in env.py

**Auto-generates targets:**
- `#alembic` - Main Alembic CLI binary
- `#alembic_dep`, `#env.py`, `#resources`, `#resources2` - Component targets
- Database driver dependencies: `#psycopg2_dep`, `#asyncpg_dep`, `#pymysql_dep`, `#aiomysql_dep`, `#aiosqlite_dep`, `#pyodbc_dep`, `#aioodbc_dep`

**Implementation:**
- Uses target generator pattern for dynamic file generation
- Fully self-contained - no external dependencies on plugin source
- Distributable via PyPI or git submodule

#### gusi.pants.backend.python

**Status**: Available

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

#### Future Backends

- `gusi.pants.backend.service_utils` - Python service utilities (planned)
- `gusi.pants.backend.asyncapi_python` - AsyncAPI code generation (planned)

## New Pants releases

Regenerate the version data and commit it:

```console
$ nix/pants/scripts/list-versions.sh > /tmp/versions.txt
$ nix/pants/scripts/gen-versions.sh /tmp/versions.txt
$ git add nix/pants/versions/
```

Unknown versions then fail loudly if not generated.

## Post-merge user actions

After the monorepo merge is finalized, the operator (user) should:

1. **Archive the standalone pants-nix repo** - `github:G-USI/pants-nix` is
   superseded by this repo's packaging.
2. **Rename this repo** - pick the final name; URL examples in this README
   then need updating (see the note under *Pants from Nix*).
3. **Update consumer pins** - repositories using
   `inputs.pants-nix.url = "github:G-USI/pants-nix"` should switch to this
   repo's flake; submodule consumers update their submodule remote to
   `https://codefloe.com/G-USI/g-usi.git`.
4. **Sync Codeberg/GitHub mirrors** - ensure both mirrors carry the merged
   `dev` history.
5. **Cut the first release tag** - once the compat contract has landed,
   run `scripts/release.sh v0.1.0` and push the tag it prepares (the
   script prints the command; the push is the human's). Both downstream
   pins then have a revision to agree on.

## License

See [LICENSE](LICENSE) file.

## Support

For issues or questions:
- Review Pants documentation: https://www.pantsbuild.org/
- Open an issue in this repository
