python_sources(
    name="pants_plugin_sources",
    sources=["register.py", "tailor.py", "target_generator.py", "target_types.py", "__init__.py"],
    # No resolve specified - Pants imports are provided at runtime when the plugin loads
)

python_sources(
    name="cli_wrappers",
    sources=["cli_wrappers.py"],
    # No resolve specified - will use the resolve of the target that depends on it
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
