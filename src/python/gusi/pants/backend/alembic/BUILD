python_sources(
    name="pants_plugin_sources",
    sources=["register.py", "tailor.py", "target_generator.py", "target_types.py", "codegen.py", "__init__.py"],
    interpreter_constraints=["==3.11.*"],
    dependencies=[":templates"],
)

python_sources(
    name="cli_wrappers",
    sources=["cli_wrappers.py"],
    interpreter_constraints=["==3.11.*"],
)

python_sources(
    name="templates",
    sources=["__init__.py"],
    interpreter_constraints=["==3.11.*"],
)

python_distribution(
    name="dist",
    dependencies=[
        ":pants_plugin_sources",
        ":cli_wrappers",
    ],
    provides=python_artifact(
        name="gusi-pants-backend-alembic",
        version="0.1.0",
        # Match Pants 2.29.0 Python requirements
        python_requires=">=3.11,<3.15",
    ),
    # Set interpreter constraints for the wheel build
    interpreter_constraints=[">=3.11,<3.15"],
)
