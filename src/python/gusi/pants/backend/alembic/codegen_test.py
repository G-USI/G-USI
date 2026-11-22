"""RuleRunner tests for the alembic codegen rules (commands.py / alembic_wrapper.py).

Asserts on the *generated content* (the config-path template output), not on
engine internals, so the suite stays valid across the pants 2.29 -> 2.33 bump
where the intrinsics gain implicit params.
"""

import pytest
from pants.engine.addresses import Address
from pants.engine.fs import Digest, DigestContents
from pants.engine.target import GeneratedSources
from pants.testutil.rule_runner import QueryRule, RuleRunner

from gusi.pants.backend.alembic.codegen import (
    GenerateAlembicCommandsPyRequest,
    GenerateAlembicWrapperPyRequest,
)
from gusi.pants.backend.alembic.codegen import rules as codegen_rules
from gusi.pants.backend.alembic.target_types import (
    AlembicCommandsPyTarget,
    AlembicWrapperPyTarget,
)

SPEC_PATH = "src/python/example/migrations"


@pytest.fixture
def rule_runner() -> RuleRunner:
    return RuleRunner(
        rules=[
            *codegen_rules(),
            QueryRule(GeneratedSources, [GenerateAlembicCommandsPyRequest]),
            QueryRule(GeneratedSources, [GenerateAlembicWrapperPyRequest]),
            QueryRule(DigestContents, [Digest]),
        ],
        target_types=[AlembicCommandsPyTarget, AlembicWrapperPyTarget],
    )


def _single_file_content(rule_runner: RuleRunner, result: GeneratedSources) -> str:
    contents = rule_runner.request(DigestContents, [result.snapshot.digest])
    assert len(contents) == 1
    return contents[0].content.decode("utf-8")


def test_generate_commands_py(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {f"{SPEC_PATH}/BUILD": "_alembic_commands_py(name='commands')\n"}
    )
    target = rule_runner.get_target(Address(SPEC_PATH, target_name="commands"))

    result = rule_runner.request(
        GeneratedSources,
        [
            GenerateAlembicCommandsPyRequest(
                protocol_sources=rule_runner.make_snapshot_of_empty_files(()),
                protocol_target=target,
            )
        ],
    )

    assert result.snapshot.files == (f"{SPEC_PATH}/commands.py",)
    content = _single_file_content(rule_runner, result)
    # The config-path template output is the load-bearing generated behavior.
    assert f'return str(Path(buildroot) / "{SPEC_PATH}/alembic.ini")' in content
    # Distinctive commands.py markers (not present in the wrapper template).
    assert (
        'sys.argv = ["alembic", "-c", _get_config_path(), "revision", '
        '"--autogenerate"] + sys.argv[1:]' in content
    )
    assert "def downgrade() -> NoReturn:" in content


def test_generate_alembic_wrapper_py(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {f"{SPEC_PATH}/BUILD": "_alembic_wrapper_py(name='wrapper')\n"}
    )
    target = rule_runner.get_target(Address(SPEC_PATH, target_name="wrapper"))

    result = rule_runner.request(
        GeneratedSources,
        [
            GenerateAlembicWrapperPyRequest(
                protocol_sources=rule_runner.make_snapshot_of_empty_files(()),
                protocol_target=target,
            )
        ],
    )

    assert result.snapshot.files == (f"{SPEC_PATH}/alembic_wrapper.py",)
    content = _single_file_content(rule_runner, result)
    assert f'return str(Path(buildroot) / "{SPEC_PATH}/alembic.ini")' in content
    # Distinctive alembic_wrapper.py markers (not present in commands.py).
    assert 'if "-c" not in sys.argv and "--config" not in sys.argv:' in content
    assert "sys.argv.insert(2, _get_config_path())" in content
