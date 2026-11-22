"""RuleRunner tests for the ray submit-script codegen rule.

``test_generate_submit_script_content`` exercises ``generate_submit_script``
through the real target-generator flow (``ray_job`` BUILD declaration ->
generated ``#_submit_script`` target -> ``GenerateRaySubmitScriptRequest``) and
asserts on the generated ``__ray_submit__.py`` *content*: the entry point, the
CPU/GPU/memory values, the secrets tier, and the default ``ray_address``
auto-detect behavior. Content assertions (not engine internals) keep the suite
valid across the pants 2.29 -> 2.33 bump.

``test_submit_script_env_var_tiers`` pins the fixed/required env-var tiers by
calling ``get_submit_script_template`` — the exact pure function the rule
invokes. Going through a ``ray_job`` target is impossible for these tiers: the
plugin's ``EnvVarsField.compute_value`` returns a plain ``dict``, which fails
Pants' field-hashability guard at target-construction time (identical
``Field.__hash__`` at 2.29 and 2.33), so ``ray_job(env_vars={...})`` cannot be
declared in a BUILD file at all. That pre-existing bug is recorded in the plan
notepads; this split keeps the tier rendering guarded without touching
production code.
"""

from textwrap import dedent

import pytest
from pants.backend.python.macros.python_requirements import (
    PythonRequirementsTargetGenerator,
)
from pants.backend.python.macros.python_requirements import (
    rules as python_requirements_rules,
)
from pants.backend.python.target_types import PythonRequirementTarget
from pants.engine.addresses import Address
from pants.engine.fs import Digest, DigestContents
from pants.engine.target import GeneratedSources
from pants.testutil.rule_runner import QueryRule, RuleRunner

from gusi.pants.backend.ray.rules import (
    GenerateRaySubmitScriptRequest,
    get_submit_script_template,
)
from gusi.pants.backend.ray.rules import rules as ray_rules
from gusi.pants.backend.ray.target_generator import (
    rules as ray_target_generator_rules,
)
from gusi.pants.backend.ray.target_types import RayJobTarget, RaySubmitTarget

SPEC_PATH = "src/python/ictl/job/hello"
SCRIPT_PATH = "src/python/_ray_submit/ictl_job_hello/__ray_submit__.py"


@pytest.fixture
def rule_runner() -> RuleRunner:
    return RuleRunner(
        rules=[
            *ray_rules(),
            *ray_target_generator_rules(),
            *python_requirements_rules(),
            QueryRule(GeneratedSources, [GenerateRaySubmitScriptRequest]),
            QueryRule(DigestContents, [Digest]),
        ],
        target_types=[
            RayJobTarget,
            RaySubmitTarget,
            PythonRequirementsTargetGenerator,
            PythonRequirementTarget,
        ],
    )


def test_generate_submit_script_content(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {
            # The generated #_submit_script target hardcodes a dependency on
            # //3rdparty/python:reqs#ray (target_generator.py); satisfy that
            # address with a real python_requirements generator.
            "3rdparty/python/requirements.txt": "ray==2.9.3\n",
            "3rdparty/python/BUILD": 'python_requirements(name="reqs")\n',
            f"{SPEC_PATH}/BUILD": dedent(
                """\
                ray_job(
                    entry_point="ictl.job.hello.main",
                    num_cpus=2.0,
                    num_gpus=0.5,
                    memory=5368709120,
                    secrets=["DB_PASSWORD"],
                )
                """
            ),
        }
    )
    submit_target = rule_runner.get_target(
        Address(SPEC_PATH, generated_name="_submit_script")
    )

    result = rule_runner.request(
        GeneratedSources,
        [
            GenerateRaySubmitScriptRequest(
                protocol_sources=rule_runner.make_snapshot_of_empty_files(()),
                protocol_target=submit_target,
            )
        ],
    )

    assert result.snapshot.files == (
        "src/python/_ray_submit/__init__.py",
        "src/python/_ray_submit/ictl_job_hello/__init__.py",
        SCRIPT_PATH,
    )
    contents = rule_runner.request(DigestContents, [result.snapshot.digest])
    script = next(
        fc.content.decode("utf-8") for fc in contents if fc.path == SCRIPT_PATH
    )
    # Entry point and resource allocation.
    assert 'entrypoint="python -m ictl.job.hello.main",' in script
    assert "entrypoint_num_cpus=2.0," in script
    assert "entrypoint_num_gpus=0.5," in script
    assert "entrypoint_memory=5368709120," in script
    # Default ray_address="auto" reads the cluster address from the env.
    assert '_ray_address = os.getenv("RAY_ADDRESS", "auto")' in script
    # Secrets tier is reachable from the BUILD file.
    assert "_SECRET_ENV_VARS = ['DB_PASSWORD']" in script
    # No env_vars declared -> the fixed/required tiers are not rendered.
    assert "_FIXED_ENV_VARS" not in script
    assert "_REQUIRED_ENV_VARS" not in script


def test_submit_script_env_var_tiers() -> None:
    script = get_submit_script_template(
        entry_point="ictl.job.hello.main",
        num_cpus=1.0,
        num_gpus=0.0,
        memory=256 * 1024 * 1024,
        ray_address="auto",
        env_vars={"DEBUG": "true", "API_KEY": None},
        secrets=[],
    )
    # Fixed tier: string values are hardcoded.
    assert "_FIXED_ENV_VARS = {'DEBUG': 'true'}" in script
    assert "_env_vars.update(_FIXED_ENV_VARS)" in script
    # Required tier: None values fail fast at submit time if unset.
    assert "_REQUIRED_ENV_VARS = ['API_KEY']" in script
    assert "for k in _REQUIRED_ENV_VARS:" in script
