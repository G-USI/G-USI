"""Ray job submission goal and package support.

Usage:
    pants ray-submit src/python/ictl/job/crawl_patents:crawl_patents
    pants package src/python/ictl/job/crawl_patents:crawl_patents

Both goals share a common build step (build_ray_job_outputs) that produces:
1. Job PEX - sources only (uploaded to Ray cluster)
2. Submit PEX - ray client + submit script (runs locally)
3. Pinned requirements.txt - for cluster verification

We never ship 3rd-party deps to the cluster — the Docker image has them pre-installed.
"""

from dataclasses import dataclass
from pathlib import PurePath

from pants.backend.python.target_types import (
    EntryPoint,
    PythonRequirementsField,
    PythonRequirementTarget,
)
from pants.backend.python.util_rules.pex import Pex, PexProcess, create_pex, setup_pex_process
from pants.backend.python.util_rules.pex_from_targets import (
    ChosenPythonResolveRequest,
    PexFromTargetsRequest,
    choose_python_resolve,
    create_pex_from_targets,
)
from pants.backend.python.util_rules.pex_requirements import (
    LoadedLockfileRequest,
    PexRequirements,
    load_lockfile,
)
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact, PackageFieldSet
from pants.engine.addresses import Address
from pants.engine.console import Console
from pants.engine.env_vars import CompleteEnvironmentVars
from pants.engine.fs import CreateDigest, FileContent, MergeDigests
from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.internals.graph import (
    implicitly,
    resolve_targets,
)
from pants.engine.internals.graph import (
    transitive_targets as get_transitive_targets,
)
from pants.engine.intrinsics import (
    create_digest,
    execute_process,
    get_digest_contents,
    merge_digests,
)
from pants.engine.rules import collect_rules, goal_rule, rule
from pants.engine.target import (
    Dependencies,
    DependenciesRequest,
    TransitiveTargetsRequest,
    UnexpandedTargets,
)
from pants.engine.unions import UnionRule
from pants.source.source_root import SourceRootRequest, get_source_root
from pants.util.logging import LogLevel
from gusi.pants.backend.ray.target_types import EntryPointField, RayJobTarget


def _resolve_pinned_requirements(
    unpinned_req_strings: tuple[str, ...],
    lockfile_bytes: bytes,
) -> str:
    """Resolve unpinned requirement strings against a PEX-native lockfile.

    Returns a pinned requirements.txt content with marker-filtered transitive deps.
    """
    import json

    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    if not unpinned_req_strings:
        return ""

    # Strip Pants comments (//) from the JSON lockfile.
    json_bytes = b"\n".join(
        line for line in lockfile_bytes.splitlines() if not line.lstrip().startswith(b"//")
    )
    lockfile_data = json.loads(json_bytes)

    # Build a lookup: canonical_name -> {version, project_name, requires_dists, ...}
    locked_reqs_map: dict[str, dict] = {}
    for resolve in lockfile_data.get("locked_resolves", []):
        for req in resolve.get("locked_requirements", []):
            proj_name = req.get("project_name", "")
            canonical = canonicalize_name(proj_name)
            locked_reqs_map[canonical] = req

    # BFS with marker filtering: lockfile requires_dists include EVERY optional
    # dep for EVERY extra and EVERY platform. We filter on `extra == "X"` markers
    # only — non-extra markers (python_version, sys_platform) are not filtered
    # since the cluster Docker image handles those.
    extras_map: dict[str, set[str]] = {}
    visited: set[str] = set()
    queue: list[str] = []

    for req_str in unpinned_req_strings:
        req = Requirement(req_str)
        canonical = canonicalize_name(req.name)
        extras_map.setdefault(canonical, set()).update(req.extras)
        if canonical not in visited and canonical in locked_reqs_map:
            visited.add(canonical)
            queue.append(canonical)

    while queue:
        parent_canonical = queue.pop(0)
        locked = locked_reqs_map[parent_canonical]
        parent_extras = frozenset(extras_map.get(parent_canonical, set()))

        for dep_str in locked.get("requires_dists", []):
            dep_req = Requirement(dep_str)

            if dep_req.marker:
                marker_text = str(dep_req.marker).lower()
                if "extra" in marker_text:
                    env = default_environment()
                    if not any(
                        (
                            marker_env := dict(env),
                            marker_env.__setitem__("extra", extra),
                            dep_req.marker.evaluate(marker_env),
                        )[-1]
                        for extra in parent_extras
                    ):
                        continue

            dep_canonical = canonicalize_name(dep_req.name)

            if dep_req.extras:
                old_extras = extras_map.get(dep_canonical, set())
                merged = old_extras | set(dep_req.extras)
                if merged != old_extras:
                    extras_map[dep_canonical] = merged

            if dep_canonical not in visited and dep_canonical in locked_reqs_map:
                visited.add(dep_canonical)
                queue.append(dep_canonical)

    lines: list[str] = []
    for canonical in sorted(visited):
        locked = locked_reqs_map[canonical]
        version = locked.get("version", "")
        extras = extras_map.get(canonical, set())
        extras_str = f"[{','.join(sorted(extras))}]" if extras else ""
        proj_name = locked.get("project_name", canonical)
        lines.append(f"{proj_name}{extras_str}=={version}")

    return "\n".join(lines) + "\n" if lines else ""


# ---------------------------------------------------------------------------
# Shared build step — both ray-submit and package delegate here.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RayJobBuildRequest:
    """Request to build all artifacts for a ray_job target."""

    address: Address
    job_pex_filename: str = "ray_job.pex"
    submit_pex_filename: str = "ray_submit.pex"


@dataclass(frozen=True)
class RayJobBuildOutputs:
    """Intermediate build outputs shared between ray-submit and package goals."""

    job_pex: Pex
    submit_pex: Pex
    requirements_content: str


@rule(desc="Build ray_job artifacts (job PEX, submit PEX, requirements)")
async def build_ray_job_outputs(request: RayJobBuildRequest) -> RayJobBuildOutputs:
    address = request.address

    # Look up the RayJobTarget generator.
    tt = await get_transitive_targets(TransitiveTargetsRequest((address,)), **implicitly())
    ray_job: RayJobTarget | None = None
    for root in tt.roots:
        if isinstance(root, RayJobTarget):
            ray_job = root
            break
    if ray_job is None:
        raise ValueError(f"Expected RayJobTarget at {address}")

    # Compute entry points.
    source_root = await get_source_root(
        SourceRootRequest(PurePath(address.spec_path)), **implicitly()
    )
    spec_path = address.spec_path
    relative = spec_path[len(source_root.path) :].lstrip("/") if source_root.path else spec_path
    safe_name = relative.replace("/", "_")

    submit_main = EntryPoint.parse(f"_ray_submit.{safe_name}.__ray_submit__:main")

    job_entry_point_str = ray_job[EntryPointField].value
    if not job_entry_point_str:
        job_entry_point_str = relative.replace("/", ".")
    job_main = EntryPoint.parse(job_entry_point_str)

    # Resolve dependency targets first — used for job PEX and requirements.
    submit_script_addr = address.create_generated("_submit_script")

    dep_targets = await resolve_targets(
        **implicitly(DependenciesRequest(ray_job[Dependencies])),
    )
    dep_addrs = tuple(tgt.address for tgt in dep_targets if tgt.address != submit_script_addr)

    # 1. Build job PEX (sources only, no 3rd-party deps shipped to cluster).
    #    Uses dep_addrs which naturally excludes the _submit_script generated target.
    job_pex = await create_pex(
        await create_pex_from_targets(
            PexFromTargetsRequest(
                addresses=dep_addrs,
                output_filename=request.job_pex_filename,
                internal_only=False,
                include_source_files=True,
                include_requirements=False,
                main=job_main,
                additional_args=("--inherit-path=prefer",),
                description=f"Build job PEX for {address}",
            ),
            **implicitly(),
        ),
        **implicitly(),
    )

    # 2. Build submit PEX (submit script + ray client dependency).
    submit_pex = await create_pex(
        await create_pex_from_targets(
            PexFromTargetsRequest(
                addresses=(submit_script_addr,),
                output_filename=request.submit_pex_filename,
                internal_only=False,
                include_source_files=True,
                include_requirements=True,
                main=submit_main,
                description=f"Build submit PEX for {address}",
            ),
            **implicitly(),
        ),
        **implicitly(),
    )

    # 3. Generate pinned requirements.txt from lockfile.
    unpinned_req_strings: tuple[str, ...] = ()
    if dep_addrs:
        job_tt = await get_transitive_targets(TransitiveTargetsRequest(dep_addrs), **implicitly())
        unpinned_req_strings = tuple(
            PexRequirements.req_strings_from_requirement_fields(
                tgt[PythonRequirementsField]
                for tgt in job_tt.closure
                if isinstance(tgt, PythonRequirementTarget)
            )
        )
    pinned_reqs_content = ""
    if unpinned_req_strings:
        chosen_resolve = await choose_python_resolve(
            ChosenPythonResolveRequest((address,)), **implicitly()
        )
        loaded_lockfile = await load_lockfile(
            LoadedLockfileRequest(chosen_resolve.lockfile), **implicitly()
        )
        lockfile_contents = await get_digest_contents(loaded_lockfile.lockfile_digest)
        pinned_reqs_content = _resolve_pinned_requirements(
            tuple(unpinned_req_strings), lockfile_contents[0].content
        )

    return RayJobBuildOutputs(
        job_pex=job_pex,
        submit_pex=submit_pex,
        requirements_content=pinned_reqs_content,
    )


# ---------------------------------------------------------------------------
# ray-submit goal
# ---------------------------------------------------------------------------


class RaySubmitSubsystem(GoalSubsystem):
    """Submit a Ray job to a Ray cluster."""

    name = "ray-submit"
    help = (
        "Build and submit a Ray job to a Ray cluster. "
        "Set RAY_ADDRESS env var to specify the cluster."
    )


class RaySubmit(Goal):
    subsystem_cls = RaySubmitSubsystem
    environment_behavior = Goal.EnvironmentBehavior.LOCAL_ONLY


@goal_rule
async def ray_submit(
    console: Console,
    ray_submit_subsystem: RaySubmitSubsystem,
    complete_env: CompleteEnvironmentVars,
    unexpanded_targets: UnexpandedTargets,
) -> RaySubmit:
    ray_job_target = None
    for target in unexpanded_targets:
        if isinstance(target, RayJobTarget):
            ray_job_target = target
            break

    if ray_job_target is None:
        console.print_stderr("No ray_job target found. Specify one on the command line.")
        return RaySubmit(exit_code=1)

    address = ray_job_target.address

    console.print_stdout(f"Building artifacts for {address}...")
    outputs = await build_ray_job_outputs(RayJobBuildRequest(address), **implicitly())

    console.print_stdout(f"Submitting Ray job {address}...")

    # Create requirements.txt in sandbox alongside the job PEX.
    reqs_digest = await create_digest(
        CreateDigest([FileContent("requirements.txt", outputs.requirements_content.encode())]),
        **implicitly(),
    )
    input_digest = await merge_digests(
        MergeDigests([outputs.job_pex.digest, reqs_digest]),
        **implicitly(),
    )

    extra_env = dict(complete_env)
    extra_env["RAY_JOB_PEX"] = outputs.job_pex.name
    if outputs.requirements_content:
        extra_env["RAY_JOB_REQUIREMENTS"] = "requirements.txt"

    pex_process = PexProcess(
        pex=outputs.submit_pex,
        description=f"Submit Ray job {address}",
        level=LogLevel.INFO,
        input_digest=input_digest,
        extra_env=extra_env,
    )
    process = await setup_pex_process(pex_process, **implicitly())
    result = await execute_process(process, **implicitly())

    if result.stdout:
        console.print_stdout(result.stdout.decode())
    if result.stderr:
        console.print_stderr(result.stderr.decode())

    return RaySubmit(exit_code=result.exit_code)


# ---------------------------------------------------------------------------
# package goal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RayJobPackageFieldSet(PackageFieldSet):
    required_fields = ()


@rule(desc="Build ray_job package")
async def package_ray_job(field_set: RayJobPackageFieldSet) -> BuiltPackage:
    """Build two PEXes and a requirements.txt, output to dist/.

    1. ray_job.pex    — sources only (uploaded to cluster)
    2. ray_submit.pex — submit script + ray client (runs locally)
    3. requirements.txt — pinned transitive deps (cluster verification)
    """
    address = field_set.address.maybe_convert_to_target_generator()

    output_relpath = ".".join(address.spec_path.split("/"))
    job_pex_filename = f"{output_relpath}/ray_job.pex"
    submit_pex_filename = f"{output_relpath}/ray_submit.pex"
    reqs_filename = f"{output_relpath}/requirements.txt"

    outputs = await build_ray_job_outputs(
        RayJobBuildRequest(
            address,
            job_pex_filename=job_pex_filename,
            submit_pex_filename=submit_pex_filename,
        ),
        **implicitly(),
    )

    reqs_digest = await create_digest(
        CreateDigest([FileContent(reqs_filename, outputs.requirements_content.encode())]),
        **implicitly(),
    )

    merged_digest = await merge_digests(
        MergeDigests([outputs.job_pex.digest, outputs.submit_pex.digest, reqs_digest]),
        **implicitly(),
    )

    return BuiltPackage(
        merged_digest,
        (
            BuiltPackageArtifact(job_pex_filename),
            BuiltPackageArtifact(submit_pex_filename),
            BuiltPackageArtifact(reqs_filename),
        ),
    )


def rules():
    return [
        *collect_rules(),
        UnionRule(PackageFieldSet, RayJobPackageFieldSet),
    ]
