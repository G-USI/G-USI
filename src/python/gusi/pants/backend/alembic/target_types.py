"""Target types for Alembic migrations."""

from pants.backend.python.target_types import PythonResolveField, PythonRequirementTarget
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    StringField,
    TargetGenerator,
)


class AlembicServiceModelsField(StringField):
    """Target address for service models."""

    alias = "service_models"
    help = "Target address for service models (optional, usually inferred)."


class AlembicServiceSrcField(StringField):
    """Target address for service base/settings."""

    alias = "service_src"
    help = "Target address for service base/settings (optional, usually inferred)."


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
    """

    alias = "alembic_migrations"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        AlembicServiceModelsField,
        AlembicServiceSrcField,
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
