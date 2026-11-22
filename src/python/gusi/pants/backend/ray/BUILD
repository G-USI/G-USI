python_sources(
    name="ray_plugin_sources",
    sources=[
        "__init__.py",
        "register.py",
        "target_generator.py",
        "target_types.py",
        "rules.py",
    ],
    interpreter_constraints=["==3.14.*"],
)

python_sources(
    name="goal",
    sources=["goal.py"],
    interpreter_constraints=["==3.14.*"],
    skip_pyright=True,
    dependencies=[":ray_plugin_sources"],
)

python_tests(
    name="rules_tests",
    sources=["rules_test.py"],
    interpreter_constraints=["==3.14.*"],
    dependencies=[":ray_plugin_sources"],
)
