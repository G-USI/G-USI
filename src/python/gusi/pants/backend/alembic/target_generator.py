"""Target generator for Alembic migrations."""

import os
from dataclasses import dataclass
from pathlib import Path, PurePath

from pants.backend.python.target_types import (
    PexBinary,
    PythonRequirementTarget,
    PythonResolveField,
    PythonSourceTarget,
)
from pants.core.target_types import ResourceTarget
from pants.engine.rules import collect_rules, rule, Get
from pants.engine.target import (
    GeneratedTargets,
    GenerateTargetsRequest,
)
from pants.engine.unions import UnionRule
from pants.source.source_root import SourceRoot, SourceRootRequest

from gusi.pants.backend.alembic.target_types import (
    AlembicCommandsPyTarget,
    AlembicMigrationsTarget,
    AlembicWrapperPyTarget,
    DisableBoilerplateGenerationField,
)
from gusi.pants.backend.alembic.templates import (
    ALEMBIC_INI_TEMPLATE,
    ENV_PY_TEMPLATE,
    SCRIPT_MAKO_TEMPLATE,
)


@dataclass(frozen=True)
class GenerateFromAlembicMigrationsRequest(GenerateTargetsRequest):
    """Request to generate targets from an alembic_migrations target."""

    generate_from = AlembicMigrationsTarget


def _get_buildroot() -> Path:
    """Find the project buildroot by searching for pants.toml.

    Returns:
        Absolute path to the buildroot directory

    Raises:
        RuntimeError: If pants.toml cannot be found
    """
    # First try BUILD_ROOT env var (set by Pants)
    buildroot = os.getenv("BUILD_ROOT")
    if buildroot:
        return Path(buildroot)

    # Search upwards for pants.toml
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / "pants.toml").exists():
            return current
        current = current.parent

    raise RuntimeError("Could not find pants.toml - not in a Pants project?")


def _ensure_alembic_boilerplate(spec_path: str) -> None:
    """Generate Alembic boilerplate files if they don't exist.

    Args:
        spec_path: Directory path where the alembic_migrations target is defined
                   (relative to buildroot, e.g., "src/python/myapp/migrations")
    """
    # Check if we should skip auto-generation (e.g., during tailor --check)
    # This env var can be set to prevent auto-generation
    if os.getenv("PANTS_ALEMBIC_NO_AUTO_GENERATE"):
        return

    # Resolve paths relative to buildroot, not cwd
    buildroot = _get_buildroot()
    migration_dir = buildroot / spec_path

    # Generate alembic.ini if missing
    alembic_ini_path = migration_dir / "alembic.ini"
    if not alembic_ini_path.exists():
        alembic_ini_path.write_text(ALEMBIC_INI_TEMPLATE)
        print(f"✓ Generated {alembic_ini_path}")

    # Generate env.py if missing
    env_py_path = migration_dir / "env.py"
    if not env_py_path.exists():
        env_py_path.write_text(ENV_PY_TEMPLATE)
        print(f"✓ Generated {env_py_path}")

    # Generate script.py.mako if missing
    script_mako_path = migration_dir / "script.py.mako"
    if not script_mako_path.exists():
        script_mako_path.write_text(SCRIPT_MAKO_TEMPLATE)
        print(f"✓ Generated {script_mako_path}")

    # Create versions directory if missing
    versions_dir = migration_dir / "versions"
    if not versions_dir.exists():
        versions_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {versions_dir}/")


@rule
async def generate_alembic_targets(
    request: GenerateFromAlembicMigrationsRequest,
) -> GeneratedTargets:
    """Generate all Alembic-related targets from an alembic_migrations target."""
    generator = request.generator

    # Get field values
    resolve = generator[PythonResolveField].value
    disable_generation = generator[DisableBoilerplateGenerationField].value

    # Generate boilerplate files if missing (unless disabled)
    if not disable_generation:
        _ensure_alembic_boilerplate(generator.address.spec_path)

    # Build dependencies for the env.py target
    # Pants automatically infers Python imports from env.py
    # We only need to explicitly include dynamically loaded dependencies
    deps = [
        f":{generator.address.target_name}#alembic_dep",
        # PostgreSQL drivers
        f":{generator.address.target_name}#psycopg2_dep",
        f":{generator.address.target_name}#asyncpg_dep",
        # MySQL/MariaDB drivers
        f":{generator.address.target_name}#pymysql_dep",
        f":{generator.address.target_name}#aiomysql_dep",
        # SQLite drivers
        f":{generator.address.target_name}#aiosqlite_dep",
        # SQL Server drivers
        f":{generator.address.target_name}#pyodbc_dep",
        f":{generator.address.target_name}#aioodbc_dep",
    ]

    # Generate python_requirement for Alembic
    alembic_req = PythonRequirementTarget(
        {
            "requirements": ["alembic>=1.13.0"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("alembic_dep"),
    )

    # PostgreSQL drivers
    psycopg2_req = PythonRequirementTarget(
        {
            "requirements": ["psycopg2-binary"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("psycopg2_dep"),
    )

    asyncpg_req = PythonRequirementTarget(
        {
            "requirements": ["asyncpg"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("asyncpg_dep"),
    )

    # MySQL/MariaDB drivers
    pymysql_req = PythonRequirementTarget(
        {
            "requirements": ["PyMySQL"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("pymysql_dep"),
    )

    aiomysql_req = PythonRequirementTarget(
        {
            "requirements": ["aiomysql"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("aiomysql_dep"),
    )

    # SQLite drivers
    aiosqlite_req = PythonRequirementTarget(
        {
            "requirements": ["aiosqlite"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("aiosqlite_dep"),
    )

    # SQL Server drivers
    pyodbc_req = PythonRequirementTarget(
        {
            "requirements": ["pyodbc"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("pyodbc_dep"),
    )

    aioodbc_req = PythonRequirementTarget(
        {
            "requirements": ["aioodbc"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("aioodbc_dep"),
    )

    # Generate python_source for env.py
    migration_src = PythonSourceTarget(
        {
            "source": "env.py",
            "dependencies": deps,
            "resolve": resolve,
        },
        address=generator.address.create_generated("env.py"),
    )

    # Generate resources for config files
    resources = ResourceTarget(
        {
            "source": "alembic.ini",
        },
        address=generator.address.create_generated("resources"),
    )

    resources2 = ResourceTarget(
        {
            "source": "script.py.mako",
        },
        address=generator.address.create_generated("resources2"),
    )

    # Common dependencies for pex_binary target
    common_deps = [
        f":{generator.address.target_name}#env.py",
        f":{generator.address.target_name}#resources",
        f":{generator.address.target_name}#resources2",
    ]

    # Generate virtual alembic_wrapper.py target (triggers GeneratedSources)
    wrapper_src = AlembicWrapperPyTarget(
        {
            "dependencies": deps,
            "resolve": resolve,
        },
        address=generator.address.create_generated("alembic_wrapper"),
    )

    # Generate virtual commands.py target (triggers GeneratedSources)
    commands_src = AlembicCommandsPyTarget(
        {
            "dependencies": deps,
            "resolve": resolve,
        },
        address=generator.address.create_generated("commands"),
    )

    # Get the source root for this target
    source_root = await Get(
        SourceRoot,
        SourceRootRequest(PurePath(generator.address.spec_path)),
    )

    # Compute module path relative to source root
    # e.g., spec_path="src/python/nslv/mig/poacher", source_root.path="src/python"
    #       -> module_path="nslv/mig/poacher" -> "nslv.mig.poacher.commands"
    spec_path = generator.address.spec_path
    if source_root.path:
        # Remove source root prefix
        module_path = spec_path[len(source_root.path):].lstrip("/")
    else:
        module_path = spec_path

    module_base = module_path.replace("/", ".")
    commands_module = f"{module_base}.commands"
    wrapper_module = f"{module_base}.alembic_wrapper"

    # Generate base Alembic CLI binary with wrapper
    alembic_bin = PexBinary(
        {
            "entry_point": f"{wrapper_module}:main",
            "dependencies": [
                f":{generator.address.target_name}#alembic_wrapper",
                *common_deps,
            ],
            "resolve": resolve,
            "restartable": True,
        },
        address=generator.address.create_generated("alembic"),
    )

    # Generate convenience command binaries
    convenience_binaries = []
    commands = ["generate", "upgrade", "downgrade"]

    for command_name in commands:
        cmd_bin = PexBinary(
            {
                "entry_point": f"{commands_module}:{command_name}",
                "dependencies": [
                    f":{generator.address.target_name}#commands",
                    *common_deps,
                ],
                "resolve": resolve,
                "restartable": True,
            },
            address=generator.address.create_generated(command_name),
        )
        convenience_binaries.append(cmd_bin)

    return GeneratedTargets(
        generator,
        [
            alembic_req,
            psycopg2_req,
            asyncpg_req,
            pymysql_req,
            aiomysql_req,
            aiosqlite_req,
            pyodbc_req,
            aioodbc_req,
            migration_src,
            resources,
            resources2,
            alembic_bin,
            wrapper_src,
            commands_src,
            *convenience_binaries,
        ],
    )


def rules():
    """Return all rules for the Alembic target generator."""
    return [
        *collect_rules(),
        UnionRule(GenerateTargetsRequest, GenerateFromAlembicMigrationsRequest),
    ]
