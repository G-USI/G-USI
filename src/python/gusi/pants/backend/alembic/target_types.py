"""Target types for Alembic migrations."""

from pants.backend.python.target_types import PythonResolveField, PythonRequirementTarget
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    TargetGenerator,
)


class AlembicMigrationsTarget(TargetGenerator):
    """Generates Alembic migration infrastructure targets.

    This target creates multiple sub-targets:
    - alembic_dep: python_requirement for Alembic
    - env.py: python_source for env.py
    - resources, resources2: resource files for alembic.ini and script.py.mako
    - alembic: pex_binary for generic Alembic CLI
    - generate: pex_binary for generating migrations
    - upgrade: pex_binary for applying migrations
    - downgrade: pex_binary for rolling back migrations

    Dependencies are automatically inferred from imports in env.py.
    The CLI wrappers automatically set up sys.path for imports to work.
    """

    alias = "alembic_migrations"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        PythonResolveField,
    )
    help = "Generates Alembic migration infrastructure targets."

    # TargetGenerator required attributes
    # Since we don't generate from sources like typical generators,
    # we set these to empty/minimal values
    copied_fields = ()
    moved_fields = (PythonResolveField,)
    # We generate multiple target types, but this field requires one concrete type
    generated_target_cls = PythonRequirementTarget
