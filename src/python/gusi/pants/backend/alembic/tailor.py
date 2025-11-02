"""Tailor support for automatically generating alembic_migrations targets."""

from dataclasses import dataclass

from pants.core.goals.tailor import (
    AllOwnedSources,
    PutativeTarget,
    PutativeTargets,
    PutativeTargetsRequest,
)
from pants.engine.fs import PathGlobs, Paths
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel

from gusi.pants.backend.alembic.target_types import AlembicMigrationsTarget


@dataclass(frozen=True)
class PutativeAlembicMigrationsTargetsRequest(PutativeTargetsRequest):
    """Request to tailor alembic_migrations targets."""


@rule(
    desc="Determine candidate alembic_migrations targets to create",
    level=LogLevel.DEBUG,
)
async def find_putative_alembic_migrations_targets(
    request: PutativeAlembicMigrationsTargetsRequest,
    all_owned_sources: AllOwnedSources,
) -> PutativeTargets:
    """Find directories with alembic.ini and suggest alembic_migrations targets."""
    # Look for alembic.ini files
    alembic_ini_paths = await Get(Paths, PathGlobs(["**/alembic.ini"]))

    putative_targets = []
    for path in alembic_ini_paths.files:
        # Get the directory containing alembic.ini
        dir_name = path.rsplit("/", 1)[0] if "/" in path else ""

        # Check if this directory already has the required files owned
        env_py_path = f"{dir_name}/env.py" if dir_name else "env.py"
        script_mako_path = f"{dir_name}/script.py.mako" if dir_name else "script.py.mako"

        # If alembic.ini is already owned, likely already has a target
        if path in all_owned_sources:
            continue

        # Check that env.py and script.py.mako exist
        required_files = await Get(
            Paths,
            PathGlobs([env_py_path, script_mako_path, path])
        )

        # Only suggest if all required files are present
        if len(required_files.files) == 3:
            putative_targets.append(
                PutativeTarget.for_target_type(
                    AlembicMigrationsTarget,
                    path=dir_name if dir_name else ".",
                    name=None,  # Use default target name
                    triggering_sources=[],  # No sources field for target generators
                )
            )

    return PutativeTargets(putative_targets)


def rules():
    """Return all tailor rules for the Alembic backend."""
    return [
        *collect_rules(),
        UnionRule(PutativeTargetsRequest, PutativeAlembicMigrationsTargetsRequest),
    ]
