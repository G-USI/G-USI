# Ray Job Plugin for Pants

A Pants build system plugin that provides Ray cluster job submission with reproducible dependency management.

## Quick Start

Create a BUILD file with a `ray_job()` target:

```python
# src/python/ictl/job/hello/BUILD
python_sources(name="src")

ray_job(
    entry_point="ictl.job.hello.main",
    dependencies=[":src"],
)
```

Submit the job to your Ray cluster:

```bash
RAY_ADDRESS=http://localhost:8265 pants ray-submit src/python/ictl/job/hello:hello
```

Package for deployment:

```bash
pants package src/python/ictl/job/hello:hello
```

## How It Works

The plugin creates a sources-only PEX that is uploaded to the Ray cluster. Dependencies are managed through a pinned requirements.txt file derived from the Pants lockfile. The Ray cluster's Docker image contains all third-party dependencies, so they are never shipped to the cluster.

1. `ray_job()` generates a submit script target that produces `__ray_submit__.py`
2. The submit script uploads the job PEX to Ray and submits it
3. Job PEX is built with `include_requirements=False` + `--inherit-path=prefer`
4. Submit PEX includes the submit script + ray client dependency
5. Requirements.txt is pinned from the Pants lockfile with marker filtering
6. At submit time, requirements.txt path is passed to Ray as `runtime_env["pip"]`
7. Ray pip-installs requirements into a runtime env virtualenv
8. Job PEX runs inside that virtualenv and sees the pip-installed packages via `--inherit-path=prefer`

## Commands

### `pants ray-submit <target>`
Builds and submits the Ray job to the cluster. The job is immediately executed on the specified Ray cluster.

### `pants package <target>`
Builds and packages the Ray job artifacts into the `dist/` directory for later deployment.

## Reference: `ray_job()` Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| entry_point | str | required | Python module path (e.g., "ictl.job.hello.main") |
| num_cpus | float | 1.0 | CPU cores to allocate. Fractional OK (e.g., 0.5) |
| num_gpus | float | 0.0 | GPUs to allocate. Fractional OK |
| memory | int | 268435456 (256MB) | Memory in bytes |
| ray_address | str | "auto" | Cluster address. "auto" reads RAY_ADDRESS env var; explicit URL gets baked into submit script |
| env_vars | dict | None | {"KEY": "val"} (fixed) or {"KEY": None} (required from env) |
| secrets | list[str] | () | Secret env var names (optional, forwarded from local env at submit time) |
| resolve | str | inferred | Python resolve (moved field from PythonResolveField) |
| dependencies | list[str] | () | Pants target deps |
| tags | list[str] | () | Target tags |
| description | str | None | Target description |

## Environment Variables

The plugin supports a three-tier environment variable system:

### Fixed Variables
Always sent to the cluster with the specified value:

```python
ray_job(
    entry_point="my_job.main",
    env_vars={"DEBUG": "false", "LOG_LEVEL": "info"},
)
```

### Required Variables
Must be set at submit time, fails fast if missing:

```python
ray_job(
    entry_point="my_job.main",
    env_vars={"API_KEY": None},  # Must be set in local env
)
```

### Secrets
Optional secret variables forwarded from local environment:

```python
ray_job(
    entry_point="my_job.main",
    secrets=["DATABASE_PASSWORD"],  # Optional, silently omitted if not in local env
)
```

### Variable Ordering
Fixed variables are applied first, then required variables overwrite them, then secrets fill in missing values (secrets never overwrite existing values).

## Ray Cluster Address

The `ray_address` field controls where jobs are submitted:

- `"auto"` (default): Reads the `RAY_ADDRESS` environment variable at submit time
- Explicit URL (e.g., `"http://localhost:8265"`): Baked into the submit script

Example:

```python
# Uses RAY_ADDRESS env var at submit time
ray_job(entry_point="job.main", ray_address="auto")

# Always submits to this specific address
ray_job(entry_point="job.main", ray_address="http://ray-cluster:8265")
```

## Build Outputs

Running `pants package <target>` produces three files in the `dist/` directory:

1. `ray_job.pex` - Sources only with `--inherit-path=prefer`
2. `ray_submit.pex` - Submit script + ray client dependency (~98MB)
3. `requirements.txt` - Pinned transitive dependencies from the Pants lockfile

## Real Examples

### Hello World Job
```python
# src/python/ictl/job/hello/BUILD
python_sources(name="src")

ray_job(
    entry_point="ictl.job.hello.main",
    dependencies=[":src"],
)
```

### Patent Crawling Job with Memory Allocation
```python
# src/python/ictl/job/crawl_patents/BUILD
python_sources(name="src")

ray_job(
    entry_point="ictl.job.crawl_patents.main",
    memory=2 * 1024 * 1024 * 1024,  # 2GB for driver
    dependencies=[":src"],
)
```

### USPTO Crawling Job with External Dependencies
```python
# src/python/ictl/job/supsi/crawl_uspto/BUILD
ray_job(
    entry_point="ictl.job.supsi.crawl_uspto.main",
    memory=2 * 1024 * 1024 * 1024,  # 2GB for driver
    dependencies=[
        "//3rdparty/python:reqs#pydantic-ai",
        "//3rdparty/python:reqs#pydantic-settings",
        "//3rdparty/python:reqs#playwright",
    ],
)
```

## Plugin Internals

### File Structure
- `__init__.py` - Plugin initialization
- `target_types.py` - RayJobTarget, RaySubmitTarget, field types (EntryPointField, EnvVarsField, NumCpusField, etc.)
- `target_generator.py` - GenerateFromRayJobRequest: generates #_submit_script target from ray_job
- `rules.py` - GenerateRaySubmitScriptRequest: codegen for __ray_submit__.py submit script
- `templates/__init__.py` - get_submit_script_template(): generates the actual submit script content
- `goal.py` - ray-submit goal, package goal, shared build_ray_job_outputs rule, requirements pinning logic
- `register.py` - Plugin registration (target_types, rules, required_backends)

### Key Components
1. **Target Types**: Define the `ray_job()` target generator and the internal submit script target
2. **Target Generator**: Creates the submit script target from each ray_job target
3. **Rules**: Generate the actual submit script content using templates
4. **Goals**: Provide the `ray-submit` and `package` commands
5. **Registration**: Connects all components to the Pants plugin system