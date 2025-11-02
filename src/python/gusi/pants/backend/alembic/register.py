"""Registration module for the Alembic migrations plugin."""

from pants.build_graph.build_file_aliases import BuildFileAliases
from gusi.pants.backend.alembic.macros import alembic_migrations


def build_file_aliases() -> BuildFileAliases:
    """Export macros to BUILD files."""
    return BuildFileAliases(
        objects={
            "alembic_migrations": alembic_migrations,
        }
    )


def rules():
    """Register build rules with Pants."""
    return []


def required_backends():
    """Declare dependencies on other Pants backends."""
    return ["pants.backend.python"]
