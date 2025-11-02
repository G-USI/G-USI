"""Registration module for the Alembic migrations plugin."""

from gusi.pants.backend.alembic import target_generator
from gusi.pants.backend.alembic.target_types import AlembicMigrationsTarget


def target_types():
    """Export target types to Pants."""
    return [AlembicMigrationsTarget]


def rules():
    """Register build rules with Pants."""
    return target_generator.rules()


def required_backends():
    """Declare dependencies on other Pants backends."""
    return ["pants.backend.python"]
