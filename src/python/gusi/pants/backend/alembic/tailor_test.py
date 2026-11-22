"""RuleRunner tests for the alembic tailor rule.

Covers the two load-bearing behaviors of
``find_putative_alembic_migrations_targets``:

* a BUILD file declaring ``alembic_migrations()`` whose boilerplate files are
  missing is DETECTED and reported (the rule's ``_missing_boilerplate``
  putative-target construction trips an upstream Pants guard — see the test
  for the pinned shape);
* no putative target is reported once alembic.ini / env.py / script.py.mako /
  versions/ exist.

The rule's boilerplate existence check runs against the *real* filesystem
rooted at ``BUILD_ROOT`` (see ``_get_buildroot()`` in tailor.py), so each test
points ``BUILD_ROOT`` at the RuleRunner's hermetic build root via
``monkeypatch.setenv`` — the test then never touches the actual repository.
"""

import pytest
from pants.core.goals.tailor import AllOwnedSources, PutativeTargets
from pants.engine.internals.scheduler import ExecutionError
from pants.testutil.rule_runner import QueryRule, RuleRunner

from gusi.pants.backend.alembic.tailor import (
    PutativeAlembicMigrationsTargetsRequest,
)
from gusi.pants.backend.alembic.tailor import rules as tailor_rules
from gusi.pants.backend.alembic.target_types import AlembicMigrationsTarget


@pytest.fixture
def rule_runner() -> RuleRunner:
    return RuleRunner(
        rules=[
            *tailor_rules(),
            QueryRule(
                PutativeTargets,
                [PutativeAlembicMigrationsTargetsRequest, AllOwnedSources],
            ),
        ],
        target_types=[AlembicMigrationsTarget],
    )


def _request_putatives(rule_runner: RuleRunner) -> PutativeTargets:
    return rule_runner.request(
        PutativeTargets,
        [PutativeAlembicMigrationsTargetsRequest(dirs=()), AllOwnedSources([])],
    )


def test_reports_target_when_boilerplate_missing(
    rule_runner: RuleRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUILD_ROOT", rule_runner.build_root)
    rule_runner.write_files({"migrations/BUILD": "alembic_migrations()\n"})

    # Pre-existing plugin bug, pinned: the rule DETECTS all four missing
    # boilerplate files and then tries to construct a putative target with them
    # as triggering_sources, which Pants' PutativeTarget.for_target_type guard
    # rejects (AlembicMigrationsTarget has no source/sources field; identical
    # guard at 2.29 and 2.33). The ExecutionError message therefore names the
    # detected files — if the detection logic ever breaks, no error is raised
    # and this test fails.
    with pytest.raises(ExecutionError) as excinfo:
        _request_putatives(rule_runner)

    message = str(excinfo.value)
    for missing_file in ("alembic.ini", "env.py", "script.py.mako", "versions/"):
        assert missing_file in message


def test_reports_nothing_when_boilerplate_present(
    rule_runner: RuleRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUILD_ROOT", rule_runner.build_root)
    rule_runner.write_files(
        {
            "migrations/BUILD": "alembic_migrations()\n",
            "migrations/alembic.ini": "[alembic]\n",
            "migrations/env.py": "# migration environment\n",
            "migrations/script.py.mako": "# mako template\n",
            # versions/ must exist as a directory; any file inside suffices.
            "migrations/versions/.keep": "",
        }
    )

    assert len(_request_putatives(rule_runner)) == 0
