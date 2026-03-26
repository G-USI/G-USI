"""Rules for generating Ray job submit scripts.

Generates __ray_submit__.py in a unique subdirectory under _ray_submit/:
- Entry point configuration
- Resource allocation settings
- Environment variable handling
- PEX upload logic (job PEX is provided via RAY_JOB_PEX env var)

Directory structure (e.g., for src/python/ictl/job/crawl_patents):
    src/python/_ray_submit/__init__.py
    src/python/_ray_submit/ictl_job_crawl_patents/__init__.py
    src/python/_ray_submit/ictl_job_crawl_patents/__ray_submit__.py
"""

from pathlib import PurePath

from pants.backend.python.target_types import PythonSourceField
from pants.engine.fs import CreateDigest, FileContent
from pants.engine.internals.graph import implicitly
from pants.engine.internals.graph import transitive_targets as get_transitive_targets
from pants.engine.intrinsics import create_digest, digest_to_snapshot
from pants.engine.rules import collect_rules, rule
from pants.engine.target import (
    GeneratedSources,
    GenerateSourcesRequest,
    TransitiveTargetsRequest,
)
from pants.engine.unions import UnionRule
from pants.source.source_root import SourceRootRequest, get_source_root
from gusi.pants.backend.ray.target_types import (
    EntryPointField,
    EnvVarsField,
    MemoryField,
    NumCpusField,
    NumGpusField,
    RayAddressField,
    RayJobTarget,
    RaySubmitSourceField,
    SecretsField,
)
from gusi.pants.backend.ray.templates import get_submit_script_template


class GenerateRaySubmitScriptRequest(GenerateSourcesRequest):
    input = RaySubmitSourceField
    output = PythonSourceField


@rule(desc="Generate __ray_submit__.py from ray_job config")
async def generate_submit_script(
    request: GenerateRaySubmitScriptRequest,
) -> GeneratedSources:
    submit_target = request.protocol_target
    ray_job_address = submit_target.address.maybe_convert_to_target_generator()

    tt_result = await get_transitive_targets(
        TransitiveTargetsRequest((ray_job_address,)), **implicitly()
    )

    ray_job = None
    for root in tt_result.roots:
        if isinstance(root, RayJobTarget):
            ray_job = root
            break
    if ray_job is None:
        raise ValueError(
            f"Expected RayJobTarget at {ray_job_address}, "
            f"but got {type(tt_result.roots[0]) if tt_result.roots else 'no targets'}"
        )

    source_root = await get_source_root(
        SourceRootRequest(PurePath(ray_job.address.spec_path)), **implicitly()
    )

    spec_path = ray_job.address.spec_path
    if source_root.path:
        module_path = spec_path[len(source_root.path) :].lstrip("/")
    else:
        module_path = spec_path
    module_base = module_path.replace("/", ".")
    safe_name = module_path.replace("/", "_")

    source_root_path = source_root.path or "."

    # Compute file paths for the _ray_submit package structure
    pkg_dir = f"{source_root_path}/_ray_submit"
    target_dir = f"{pkg_dir}/{safe_name}"
    script_path = f"{target_dir}/__ray_submit__.py"

    entry_point = ray_job[EntryPointField].value or module_base
    num_cpus = ray_job[NumCpusField].value or 1.0
    num_gpus = ray_job[NumGpusField].value or 0.0
    memory = ray_job[MemoryField].value or 256 * 1024 * 1024
    ray_address = ray_job[RayAddressField].value or "auto"
    env_vars = ray_job[EnvVarsField].value or {}
    secret_values = ray_job[SecretsField].value or ()
    secrets = [s for s in secret_values] if secret_values else []

    content = get_submit_script_template(
        entry_point=entry_point,
        num_cpus=num_cpus,
        num_gpus=num_gpus,
        memory=memory,
        ray_address=ray_address,
        env_vars=env_vars,
        secrets=secrets,
    )

    # Generate package __init__.py files + the submit script
    files = [
        FileContent(f"{pkg_dir}/__init__.py", b""),
        FileContent(f"{target_dir}/__init__.py", b""),
        FileContent(script_path, content.encode()),
    ]

    digest = await create_digest(CreateDigest(files))
    snapshot = await digest_to_snapshot(digest, **implicitly())

    return GeneratedSources(snapshot)


def rules():
    return [
        *collect_rules(),
        UnionRule(GenerateSourcesRequest, GenerateRaySubmitScriptRequest),
    ]
