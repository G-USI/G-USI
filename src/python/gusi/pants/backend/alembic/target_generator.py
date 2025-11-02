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

    # Build dependencies for the src target
    deps = [f":{generator.address.target_name}#alembic_dep"]
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

    # Generate python_source for env.py
    migration_src = PythonSourceTarget(
        {
            "source": "env.py",
            "dependencies": deps,
            "resolve": resolve,
        },
        address=generator.address.create_generated("src"),
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

    # Common fields for all pex_binary targets
    common_pex_fields = {
        "entry_point": "alembic.config:main",
        "dependencies": [
            f":{generator.address.target_name}#src",
            f":{generator.address.target_name}#resources",
            f":{generator.address.target_name}#resources2",
        ],
        "resolve": resolve,
        "restartable": True,
    }

    # Generate pex_binary targets
    alembic_bin = PexBinary(
        common_pex_fields,
        address=generator.address.create_generated("alembic"),
    )

    migrate_bin = PexBinary(
        common_pex_fields,
        address=generator.address.create_generated("migrate"),
    )

    upgrade_bin = PexBinary(
        common_pex_fields,
        address=generator.address.create_generated("upgrade"),
    )

    downgrade_bin = PexBinary(
        common_pex_fields,
        address=generator.address.create_generated("downgrade"),
    )

    return GeneratedTargets(
        generator,
        [
            alembic_req,
            migration_src,
            resources,
            resources2,
            alembic_bin,
            migrate_bin,
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
