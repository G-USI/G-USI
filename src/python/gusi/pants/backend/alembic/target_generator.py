"""Target generator for Alembic migrations."""

from dataclasses import dataclass

from pants.backend.python.target_types import (
    PexBinary,
    PythonRequirementTarget,
    PythonResolveField,
    PythonSourceTarget,
)
from pants.core.target_types import ResourceTarget
from pants.engine.rules import collect_rules, rule
from pants.engine.target import (
    GeneratedTargets,
    GenerateTargetsRequest,
)
from pants.engine.unions import UnionRule

from gusi.pants.backend.alembic.target_types import (
    AlembicMigrationsTarget,
    AlembicServiceModelsField,
    AlembicServiceSrcField,
)


@dataclass(frozen=True)
class GenerateFromAlembicMigrationsRequest(GenerateTargetsRequest):
    """Request to generate targets from an alembic_migrations target."""

    generate_from = AlembicMigrationsTarget


@rule
async def generate_alembic_targets(
    request: GenerateFromAlembicMigrationsRequest,
) -> GeneratedTargets:
    """Generate all Alembic-related targets from an alembic_migrations target."""
    generator = request.generator

    # Get field values
    service_models = generator[AlembicServiceModelsField].value
    service_src = generator[AlembicServiceSrcField].value
    resolve = generator[PythonResolveField].value

    # Auto-infer service paths if not specified
    # Pattern: src/python/nslv/mig/SERVICE -> src/python/nslv/srv/SERVICE
    if not service_models or not service_src:
        path_parts = generator.address.spec_path.split("/")
        if "mig" in path_parts:
            # Find the service name (directory after 'mig')
            mig_idx = path_parts.index("mig")
            if mig_idx + 1 < len(path_parts):
                service_name = path_parts[mig_idx + 1]
                # Construct service path by replacing 'mig' with 'srv'
                service_parts = path_parts[:mig_idx] + ["srv", service_name]
                service_path = "/".join(service_parts)

                if not service_models:
                    service_models = f"{service_path}:models"
                if not service_src:
                    service_src = f"{service_path}:src"

    # Build dependencies for the src target
    # Note: Most Python imports are automatically inferred by Pants
    # However, database drivers (like asyncpg) are loaded dynamically by SQLAlchemy
    # and must be explicitly included
    deps = [
        f":{generator.address.target_name}#alembic_dep",
        f":{generator.address.target_name}#asyncpg_dep",  # Database driver for PostgreSQL
    ]
    if service_models:
        deps.append(service_models)
    if service_src:
        deps.append(service_src)

    # Generate python_requirement for Alembic
    alembic_req = PythonRequirementTarget(
        {
            "requirements": ["alembic>=1.13.0"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("alembic_dep"),
    )

    # Generate python_requirement for asyncpg (dynamically loaded by SQLAlchemy)
    asyncpg_req = PythonRequirementTarget(
        {
            "requirements": ["asyncpg"],
            "resolve": resolve,
        },
        address=generator.address.create_generated("asyncpg_dep"),
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

    # Common dependencies for all pex_binary targets
    common_deps = [
        f":{generator.address.target_name}#env.py",
        f":{generator.address.target_name}#resources",
        f":{generator.address.target_name}#resources2",
    ]

    # Dependencies for binaries that use gusi CLI wrappers
    gusi_cli_deps = common_deps + ["3rdparty/pants/g-usi/src/python/gusi/pants/backend/alembic:cli_wrappers"]

    # Environment variable with alembic.ini location (relative to project root)
    alembic_ini_path = f"{generator.address.spec_path}/alembic.ini"
    cli_env = {"ALEMBIC_INI_RELPATH": alembic_ini_path}

    # Generate pex_binary targets
    # Generic Alembic CLI (no defaults)
    alembic_bin = PexBinary(
        {
            "entry_point": "alembic.config:main",
            "dependencies": common_deps,
            "resolve": resolve,
            "restartable": True,
            "env": cli_env,
        },
        address=generator.address.create_generated("alembic"),
    )

    # Convenience binaries with sensible defaults
    generate_bin = PexBinary(
        {
            "entry_point": "gusi.pants.backend.alembic.cli_wrappers:migrate_main",
            "dependencies": gusi_cli_deps,
            "resolve": resolve,
            "restartable": True,
            "env": cli_env,
        },
        address=generator.address.create_generated("generate"),
    )

    upgrade_bin = PexBinary(
        {
            "entry_point": "gusi.pants.backend.alembic.cli_wrappers:upgrade_main",
            "dependencies": gusi_cli_deps,
            "resolve": resolve,
            "restartable": True,
            "env": cli_env,
        },
        address=generator.address.create_generated("upgrade"),
    )

    downgrade_bin = PexBinary(
        {
            "entry_point": "gusi.pants.backend.alembic.cli_wrappers:downgrade_main",
            "dependencies": gusi_cli_deps,
            "resolve": resolve,
            "restartable": True,
            "env": cli_env,
        },
        address=generator.address.create_generated("downgrade"),
    )

    return GeneratedTargets(
        generator,
        [
            alembic_req,
            asyncpg_req,
            migration_src,
            resources,
            resources2,
            alembic_bin,
            generate_bin,
            upgrade_bin,
            downgrade_bin,
        ],
    )


def rules():
    """Return all rules for the Alembic target generator."""
    return [
        *collect_rules(),
        UnionRule(GenerateTargetsRequest, GenerateFromAlembicMigrationsRequest),
    ]
