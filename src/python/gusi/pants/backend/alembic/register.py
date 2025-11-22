"""Registration module for the Alembic migrations plugin."""

from pants.engine.rules import collect_rules
from pants.engine.target import GenerateSourcesRequest
from pants.engine.unions import UnionRule

from gusi.pants.backend.alembic import codegen, tailor, target_generator
from gusi.pants.backend.alembic.codegen import GenerateAlembicCommandsPyRequest
from gusi.pants.backend.alembic.target_types import (
    AlembicCommandsPyTarget,
    AlembicMigrationsTarget,
)


def target_types():
    """Export target types to Pants."""
    return [
        AlembicMigrationsTarget,
        AlembicCommandsPyTarget,
    ]


def rules():
    """Register build rules with Pants."""
    return [
        *codegen.rules(),
        *target_generator.rules(),
        *tailor.rules(),
        UnionRule(GenerateSourcesRequest, GenerateAlembicCommandsPyRequest),
    ]


def required_backends():
    """Declare dependencies on other Pants backends."""
    return ["pants.backend.python"]
