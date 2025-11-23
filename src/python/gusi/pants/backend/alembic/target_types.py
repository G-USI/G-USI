"""Target types for Alembic migrations."""

from pants.backend.python.target_types import PythonResolveField, PythonRequirementTarget
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    BoolField,
    Dependencies,
    Target,
    TargetGenerator,
)

from gusi.pants.backend.alembic.codegen import (
    AlembicCommandsPySourceField,
    AlembicWrapperPySourceField,
)


class AlembicCommandsPyTarget(Target):
    """Target that generates commands.py for Alembic convenience binaries.

    This is an internal target created by alembic_migrations(). It triggers
    virtual generation of commands.py via GeneratedSources.
    """

    alias = "_alembic_commands_py"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        Dependencies,
        AlembicCommandsPySourceField,
        PythonResolveField,
    )


class AlembicWrapperPyTarget(Target):
    """Target that generates alembic_wrapper.py for the Alembic CLI.

    This is an internal target created by alembic_migrations(). It triggers
    virtual generation of alembic_wrapper.py via GeneratedSources.
    """

    alias = "_alembic_wrapper_py"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        Dependencies,
        AlembicWrapperPySourceField,
        PythonResolveField,
    )


class DisableBoilerplateGenerationField(BoolField):
    """Disable automatic boilerplate file generation.

    If True, alembic.ini, env.py, script.py.mako, and versions/ will NOT be
    auto-generated. You must create these files manually.

    Default: False (auto-generation enabled)
    """
    alias = "disable_boilerplate_generation"
    default = False


class AlembicMigrationsTarget(TargetGenerator):
    """Generates Alembic migration infrastructure targets with automatic boilerplate generation.

    Zero-config database migrations - just create BUILD file, everything else auto-generates.

    ## Quick Start

    1. Create BUILD file:
        # src/python/myapp/migrations/BUILD
        alembic_migrations()

    2. Trigger generation (any pants command works):
        pants list src/python/myapp/migrations::

    3. Files auto-generated:
        ✓ alembic.ini - Configuration with script_location
        ✓ env.py - Migration environment with async/sync driver conversion
        ✓ script.py.mako - Migration template
        ✓ versions/ - Empty directory for migrations

    4. Customize env.py to import your models:
        from myapp.models import Base
        target_metadata = Base.metadata

    ## Usage

    Generate a migration:
        pants run '//src/python/myapp/migrations#alembic' -- \\
            -c src/python/myapp/migrations/alembic.ini \\
            revision --autogenerate -m "add_user_table"

    Apply migrations:
        pants run '//src/python/myapp/migrations#alembic' -- \\
            -c src/python/myapp/migrations/alembic.ini upgrade head

    Rollback:
        pants run '//src/python/myapp/migrations#alembic' -- \\
            -c src/python/myapp/migrations/alembic.ini downgrade -1

    ## Generated Targets

    - #alembic - Alembic CLI with all database drivers
    - #alembic_dep - Alembic package dependency
    - #env.py - Migration environment file
    - #resources - alembic.ini configuration
    - #resources2 - script.py.mako template
    - Database drivers: #psycopg2_dep, #asyncpg_dep, #pymysql_dep, #aiomysql_dep,
      #aiosqlite_dep, #pyodbc_dep, #aioodbc_dep

    ## Key Features

    - Automatic boilerplate generation - no manual file creation
    - Multi-database support - PostgreSQL, MySQL, SQLite, SQL Server drivers
    - Async/sync driver conversion - postgresql+asyncpg:// → postgresql://
    - Automatic dependency inference - import models, Pants handles the rest
    - Zero configuration - just `alembic_migrations()`

    ## Parameters

    - resolve (optional) - Python resolver to use. Defaults to `python-default`.
    - disable_boilerplate_generation (optional) - Disable automatic boilerplate file generation.
      If True, you must create alembic.ini, env.py, script.py.mako, and versions/ manually.
      Defaults to False (auto-generation enabled).
    """

    alias = "alembic_migrations"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        PythonResolveField,
        DisableBoilerplateGenerationField,
    )
    help = """Generates Alembic migration infrastructure with automatic boilerplate generation.

Zero-config database migrations - just create BUILD file, everything else auto-generates!

Setup (copy-paste ready):

1. Create directory:
   ```bash
   mkdir -p src/python/myapp/migrations
   ```

2. BUILD file (src/python/myapp/migrations/BUILD):
   ```python
   alembic_migrations()
   ```

3. Trigger boilerplate generation:
   ```bash
   pants list src/python/myapp/migrations::
   ```

4. Files automatically generated:
   ✓ alembic.ini - Configuration with script_location
   ✓ env.py - Migration environment with async/sync driver conversion
   ✓ script.py.mako - Migration template
   ✓ versions/ - Empty directory for migrations

5. Customize generated env.py to import your models:
   ```python
   # Update these lines in the generated env.py
   from myapp.models import Base
   target_metadata = Base.metadata
   ```

Usage Commands:
  Generate migration:
    ```bash
    pants run '//src/python/myapp/migrations#alembic' -- \\
        -c src/python/myapp/migrations/alembic.ini \\
        revision --autogenerate -m "add_user_table"
    ```

  Apply migrations:
    ```bash
    pants run '//src/python/myapp/migrations#alembic' -- \\
        -c src/python/myapp/migrations/alembic.ini upgrade head
    ```

  Rollback:
    ```bash
    pants run '//src/python/myapp/migrations#alembic' -- \\
        -c src/python/myapp/migrations/alembic.ini downgrade -1
    ```

Generated Targets:
  #alembic    - Alembic CLI with all database drivers
  #alembic_dep, #env.py, #resources, #resources2 - Component targets
  Database drivers: #psycopg2_dep, #asyncpg_dep, #pymysql_dep, #aiomysql_dep,
                    #aiosqlite_dep, #pyodbc_dep, #aioodbc_dep

Key Features:
  ✓ Automatic boilerplate generation - no manual file creation
  ✓ Multi-database support - PostgreSQL, MySQL, SQLite, SQL Server
  ✓ Async/sync driver conversion - postgresql+asyncpg:// → postgresql://
  ✓ Auto dependency inference from imports
  ✓ Zero configuration - just alembic_migrations()

Parameters:
  resolve (optional) - Python resolver (default: python-default)
  disable_boilerplate_generation (optional) - Disable automatic boilerplate file generation
                                               (default: False)
"""

    # TargetGenerator required attributes
    # Since we don't generate from sources like typical generators,
    # we set these to empty/minimal values
    copied_fields = ()
    moved_fields = (PythonResolveField,)
    # We generate multiple target types, but this field requires one concrete type
    generated_target_cls = PythonRequirementTarget
