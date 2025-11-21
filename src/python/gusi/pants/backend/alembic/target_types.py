"""Target types for Alembic migrations."""

from pants.backend.python.target_types import PythonResolveField, PythonRequirementTarget
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    TargetGenerator,
)


class AlembicMigrationsTarget(TargetGenerator):
    """Generates Alembic migration infrastructure targets.

    Zero-config database migrations with automatic dependency inference.

    ## Quick Start

    Create a BUILD file in your migrations directory:

        # src/python/myapp/migrations/BUILD
        alembic_migrations()

    ## Required Files

    You need 4 minimal files in your migrations directory:

    1. BUILD - Just `alembic_migrations()`
    2. alembic.ini - Config with `[alembic]` section and `script_location = %(here)s`
    3. env.py - Import your SQLAlchemy Base, configure migrations
    4. script.py.mako - Template for generated migration files
    5. versions/ - Empty directory (migrations go here)

    ## Usage

    Generate a migration:
        pants run '//src/python/myapp/migrations#generate' -- \\
            revision --autogenerate -m "add_user_table"

    Apply migrations:
        pants run '//src/python/myapp/migrations#upgrade' -- upgrade head

    Rollback:
        pants run '//src/python/myapp/migrations#downgrade' -- downgrade -1

    ## Generated Targets

    - #generate - Generate new migrations (auto-detects alembic.ini)
    - #upgrade - Apply migrations to database
    - #downgrade - Rollback migrations
    - #alembic - Raw Alembic CLI for advanced operations
    - #alembic_dep, #asyncpg_dep - Dependency targets
    - #env.py - Python source target
    - #resources, #resources2 - Config file resources

    ## Key Features

    - Zero-config BUILD files - literally just `alembic_migrations()`
    - Automatic dependency inference - import models in env.py, Pants handles the rest
    - Auto-detects alembic.ini - no need to pass --config flag
    - Clean env.py - no sys.path manipulation needed
    - Works with any project structure - as long as Pants can see your Python files

    ## Parameters

    - resolve (optional) - Python resolver to use. Defaults to `python-default`.
    """

    alias = "alembic_migrations"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        PythonResolveField,
    )
    help = """Generates Alembic migration infrastructure targets.

Zero-config database migrations with automatic dependency inference.

Setup (copy-paste ready):

1. Create directory:
   ```bash
   mkdir -p src/python/myapp/migrations/versions
   ```

2. BUILD file (src/python/myapp/migrations/BUILD):
   ```python
   alembic_migrations()
   ```

3. alembic.ini (src/python/myapp/migrations/alembic.ini):
   ```ini
   [alembic]
   script_location = %(here)s
   ```

4. env.py (src/python/myapp/migrations/env.py):
   ```python
   from alembic import context
   from sqlalchemy import engine_from_config, pool
   import os

   from myapp.models import Base  # Replace with your models path

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

5. script.py.mako (src/python/myapp/migrations/script.py.mako):
   ```mako
   \"\"\"${message}

   Revision ID: ${up_revision}
   Revises: ${down_revision | comma,n}
   Create Date: ${create_date}
   \"\"\"
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

Usage Commands:
  Generate migration:
    ```bash
    pants run '//src/python/myapp/migrations#generate' -- revision --autogenerate -m "add_user_table"
    ```

  Apply migrations:
    ```bash
    pants run '//src/python/myapp/migrations#upgrade' -- upgrade head
    ```

  Rollback:
    ```bash
    pants run '//src/python/myapp/migrations#downgrade' -- downgrade -1
    ```

Generated Targets:
  #generate   - Generate migrations (auto-detects alembic.ini)
  #upgrade    - Apply migrations to database
  #downgrade  - Rollback migrations
  #alembic    - Raw Alembic CLI

Key Features:
  ✓ Zero-config - Just alembic_migrations()
  ✓ Auto dependency inference from imports
  ✓ Auto-detects alembic.ini
  ✓ No sys.path hacks needed

Parameters:
  resolve (optional) - Python resolver (default: python-default)
"""

    # TargetGenerator required attributes
    # Since we don't generate from sources like typical generators,
    # we set these to empty/minimal values
    copied_fields = ()
    moved_fields = (PythonResolveField,)
    # We generate multiple target types, but this field requires one concrete type
    generated_target_cls = PythonRequirementTarget
