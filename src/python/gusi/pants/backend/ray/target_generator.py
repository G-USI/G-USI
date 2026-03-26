"""Target generator for Ray jobs.

Generates the following targets from a ray_job() definition:
- #_submit_script - Generated __ray_submit__.py with submission config

Note: Python sources are handled by generated_target_cls=PythonSourceTarget on
RayJobTarget, which auto-generates per-file PythonSourceTargets. The goal rule
uses the generator address directly for PexFromTargetsRequest, which expands to
all generated PythonSourceTargets + their transitive deps.

No PexBinary is generated — both ray-submit and package build PEXes via rules.
"""

from dataclasses import dataclass

from pants.engine.rules import collect_rules, rule
from pants.engine.target import GeneratedTargets, GenerateTargetsRequest
from pants.engine.unions import UnionRule
from gusi.pants.backend.ray.target_types import RayJobTarget, RaySubmitTarget


@dataclass(frozen=True)
class GenerateFromRayJobRequest(GenerateTargetsRequest):
    generate_from = RayJobTarget


@rule
async def generate_ray_job_targets(
    request: GenerateFromRayJobRequest,
) -> GeneratedTargets:
    generator = request.generator

    submit_script_target = RaySubmitTarget(
        {
            "source": ("__ray_submit__.py",),
            "dependencies": ("//3rdparty/python:reqs#ray",),
        },
        address=generator.address.create_generated("_submit_script"),
    )

    return GeneratedTargets(
        generator,
        [submit_script_target],
    )


def rules():
    return [
        *collect_rules(),
        UnionRule(GenerateTargetsRequest, GenerateFromRayJobRequest),
    ]
