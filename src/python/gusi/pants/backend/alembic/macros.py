"""Alembic migrations macro for BUILD files."""

from pants.engine.internals.parser import ParseContext


def alembic_migrations(
    *,
    service_models: str | None = None,
    service_src: str | None = None,
    resolve: str | None = None,
) -> None:
    """
    Creates standard Alembic migration targets for a service.

    This macro sets up Alembic migrations that depend on service models by creating:
    1. A python_requirements target for Alembic dependency
    2. A python_sources target for env.py (depends on service models)
    3. A resources target for alembic.ini and script.py.mako
    4. Multiple pex_binary targets for common migration operations

    Dependency chain:
        service models + service src + alembic reqs → migration src → migration binaries

    Args:
        service_models: (Optional) Pants target for the service models.
            Usually inferred automatically.

        service_src: (Optional) Pants target for service base/settings.
            Usually inferred automatically.

        resolve: Python resolver to use.

    Returns:
        None

    Example:
        # Basic migrations setup (zero config!)
        alembic_migrations()

    Generated Targets:
        - alembic_dep: python_requirement for Alembic (hardcoded)
        - src: python_sources for env.py (depends on service)
        - resources: resources for alembic.ini, script.py.mako
        - alembic: pex_binary for generic Alembic CLI
        - migrate: pex_binary for generating migrations
        - upgrade: pex_binary for applying migrations
        - downgrade: pex_binary for rolling back migrations

    Usage:
        To generate a migration:
        $ pants run src/python/nslv/mig/my_service:migrate -- \\
            --config src/python/nslv/mig/my_service/alembic.ini \\
            revision --autogenerate -m "migration_name"

        To apply migrations:
        $ pants run src/python/nslv/mig/my_service:upgrade -- \\
            --config src/python/nslv/mig/my_service/alembic.ini \\
            upgrade head

        To use generic Alembic CLI:
        $ pants run src/python/nslv/mig/my_service:alembic -- \\
            --config src/python/nslv/mig/my_service/alembic.ini \\
            <alembic commands>
    """
    # Get BUILD file context to access BUILD file symbols
    context = ParseContext.get()
    python_requirement = context.parse_globals["python_requirement"]
    python_sources = context.parse_globals["python_sources"]
    resources = context.parse_globals["resources"]
    pex_binary = context.parse_globals["pex_binary"]

    # Build kwargs for resolve parameter
    kwargs = {}
    if resolve:
        kwargs["resolve"] = resolve

    # Create inline requirement for Alembic (hardcoded, no requirements.txt needed)
    python_requirement(
        name="alembic_dep",
        requirements=["alembic>=1.13.0"],
        **kwargs,
    )

    # Create python_sources target for migration scripts
    # Depends on: service models, service src (base/settings), and alembic
    deps = [":alembic_dep"]
    if service_models:
        deps.append(service_models)
    if service_src:
        deps.append(service_src)

    python_sources(
        name="src",
        sources=["env.py"],
        dependencies=deps,
        **kwargs,
    )

    # Create resources target for Alembic config files
    resources(
        name="resources",
        sources=["alembic.ini", "script.py.mako"],
    )

    # Generic Alembic CLI tool
    pex_binary(
        name="alembic",
        entry_point="alembic.config:main",
        dependencies=[
            ":src",
            ":resources",
        ],
        restartable=True,
        **kwargs,
    )

    # Convenience target: Generate new migration
    pex_binary(
        name="migrate",
        entry_point="alembic.config:main",
        dependencies=[
            ":src",
            ":resources",
        ],
        restartable=True,
        **kwargs,
    )

    # Convenience target: Apply migrations
    pex_binary(
        name="upgrade",
        entry_point="alembic.config:main",
        dependencies=[
            ":src",
            ":resources",
        ],
        restartable=True,
        **kwargs,
    )

    # Convenience target: Rollback migrations
    pex_binary(
        name="downgrade",
        entry_point="alembic.config:main",
        dependencies=[
            ":src",
            ":resources",
        ],
        restartable=True,
        **kwargs,
    )
