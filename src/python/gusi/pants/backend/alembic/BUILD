python_sources(
    name="pants_plugin_sources",
    sources=["register.py", "tailor.py", "target_generator.py", "target_types.py", "codegen.py", "__init__.py"],
    interpreter_constraints=["==3.14.*"],
    dependencies=[":templates"],
)

python_sources(
    name="cli_wrappers",
    sources=["cli_wrappers.py"],
    interpreter_constraints=["==3.14.*"],
)

python_sources(
    name="templates",
    sources=[
        "templates/__init__.py",
        "templates/alembic_ini.py",
        "templates/alembic_wrapper_py.py",
        "templates/commands_py.py",
        "templates/env_py.py",
        "templates/script_mako.py",
    ],
    interpreter_constraints=["==3.14.*"],
)

python_tests(
    name="codegen_tests",
    sources=["codegen_test.py"],
    interpreter_constraints=["==3.14.*"],
    dependencies=[":pants_plugin_sources"],
)

python_tests(
    name="tailor_tests",
    sources=["tailor_test.py"],
    interpreter_constraints=["==3.14.*"],
    dependencies=[":pants_plugin_sources"],
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
        # Pythons the dist's cli_wrappers supports; plugin code itself runs under Pants' own interpreter (==3.14.*)
        python_requires=">=3.11,<3.15",
    ),
    # Set interpreter constraints for the wheel build
    interpreter_constraints=[">=3.11,<3.15"],
)
