"""Tailor support for automatically generating alembic_migrations targets."""

import os
from dataclasses import dataclass
from pathlib import Path

from pants.core.goals.tailor import (
    AllOwnedSources,
    PutativeTarget,
    PutativeTargets,
    PutativeTargetsRequest,
)
from pants.engine.fs import DigestContents, PathGlobs, Paths
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel

from gusi.pants.backend.alembic.target_types import AlembicMigrationsTarget


@dataclass(frozen=True)
class PutativeAlembicMigrationsTargetsRequest(PutativeTargetsRequest):
    """Request to tailor alembic_migrations targets."""


def _get_buildroot() -> Path:
    """Find the project buildroot by searching for pants.toml."""
    buildroot = os.getenv("BUILD_ROOT")
    if buildroot:
        return Path(buildroot)

    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / "pants.toml").exists():
            return current
        current = current.parent

    raise RuntimeError("Could not find pants.toml - not in a Pants project?")


@rule(
    desc="Determine candidate alembic_migrations targets to create",
    level=LogLevel.DEBUG,
)
async def find_putative_alembic_migrations_targets(
    request: PutativeAlembicMigrationsTargetsRequest,
    all_owned_sources: AllOwnedSources,
) -> PutativeTargets:
    """Find BUILD files with alembic_migrations() and check for missing boilerplate.

    This rule checks BEFORE target generation happens, capturing the initial state.
    """
    # Look for BUILD files that might contain alembic_migrations()
    build_paths = await Get(Paths, PathGlobs(["**/BUILD"]))

    # Also look for existing alembic.ini files to suggest targets for them
    alembic_ini_paths = await Get(Paths, PathGlobs(["**/alembic.ini"]))

    putative_targets = []

    # Check BUILD files for alembic_migrations() calls
    # We need to do this check EARLY, before target generation creates files
    if build_paths.files:
        build_contents = await Get(DigestContents, PathGlobs(["**/BUILD"]))
        buildroot = _get_buildroot()

        for file_content in build_contents:
            content = file_content.content.decode("utf-8")

            # Check if this BUILD file contains alembic_migrations()
            if "alembic_migrations(" in content:
                # Get the directory containing this BUILD file
                dir_name = file_content.path.rsplit("/", 1)[0] if "/" in file_content.path else ""

                # Check if boilerplate files exist BEFORE target generation
                migration_dir = buildroot / dir_name if dir_name else buildroot

                # Snapshot the current state
                missing = []
                if not (migration_dir / "alembic.ini").exists():
                    missing.append("alembic.ini")
                if not (migration_dir / "env.py").exists():
                    missing.append("env.py")
                if not (migration_dir / "script.py.mako").exists():
                    missing.append("script.py.mako")
                if not (migration_dir / "versions").exists():
                    missing.append("versions/")

                # If any files are missing, report them
                # In --check mode, this will cause tailor to fail with exit 1
                # In normal mode, the target generator will create the files
                if missing:
                    print(f"⚠  Alembic boilerplate missing in {dir_name or '.'}: {', '.join(missing)}")
                    print(f"   Run any pants command to auto-generate these files.")

                    # Create a putative target to make --check fail
                    # We use a unique name to avoid conflicts
                    putative_targets.append(
                        PutativeTarget.for_target_type(
                            AlembicMigrationsTarget,
                            path=dir_name if dir_name else ".",
                            name="_missing_boilerplate",
                            triggering_sources=missing,
                            kwargs={"resolve": "python-default"},
                        )
                    )

    # Also check for alembic.ini files without BUILD files (original behavior)
    for path in alembic_ini_paths.files:
        dir_name = path.rsplit("/", 1)[0] if "/" in path else ""

        # If alembic.ini is already owned, skip
        if path in all_owned_sources:
            continue

        # Check if there's a BUILD file in this directory
        build_file_path = f"{dir_name}/BUILD" if dir_name else "BUILD"
        if build_file_path in build_paths.files:
            continue

        env_py_path = f"{dir_name}/env.py" if dir_name else "env.py"
        script_mako_path = f"{dir_name}/script.py.mako" if dir_name else "script.py.mako"

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
                    name=None,
                    triggering_sources=[],
                )
            )

    return PutativeTargets(putative_targets)


def rules():
    """Return all tailor rules for the Alembic backend."""
    return [
        *collect_rules(),
        UnionRule(PutativeTargetsRequest, PutativeAlembicMigrationsTargetsRequest),
    ]
