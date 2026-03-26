"""Target types for Ray job submissions."""

from pants.backend.python.target_types import (
    PythonResolveField,
    PythonSourceTarget,
)
from pants.engine.addresses import Address
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    Dependencies,
    FloatField,
    IntField,
    ScalarField,
    SourcesField,
    StringField,
    StringSequenceField,
    Target,
    TargetGenerator,
)
from pants.util.frozendict import FrozenDict


class EnvVarsField(ScalarField[dict[str, str | None]]):
    """Environment variables for the Ray job.

    Accepts a dict where:
    - Key is the env var name
    - Value is either:
      - A string (fixed value)
      - None (required, must be set at runtime)

    Example:
        env_vars={
            "DEBUG": "true",           # Fixed value
            "API_KEY": None,           # Required at runtime
        }
    """

    alias = "env_vars"
    expected_type = dict
    expected_type_description = "a dict of env var name to value (string or None)"
    default = None
    help = """Environment variables for the Ray job.

    Dict where:
    - String value = fixed, hardcoded in generated script
    - None value = required, must be set at runtime

    Example:
        env_vars={
            "DEBUG": "true",     # Fixed
            "API_KEY": None,     # Required
        }
    """

    @classmethod
    def compute_value(
        cls,
        raw_value: dict[str, str | None] | None,
        address: Address,
    ) -> FrozenDict[str, str | None] | None:
        # Pants wraps all target field values in a FrozenDict, so the value
        # itself must be hashable. We can't use ScalarField's type check
        # because it rejects FrozenDict (not a subclass of dict).
        if raw_value is None:
            return None
        if not isinstance(raw_value, (dict, FrozenDict)):
            raise ValueError(
                f"The 'env_vars' field in target {address} must be a dict, "
                f"but was `{raw_value}` with type `{type(raw_value).__name__}`"
            )
        return FrozenDict(raw_value)


class EntryPointField(StringField):
    """Python module entry point for the Ray job.

    This should be a fully qualified module path that can be executed with `python -m`.

    Example: "ictl.job.supsi.crawl_uspto.main"
    """

    alias = "entry_point"
    required = True
    help = """The Python module entry point for the Ray job.

    This is executed as `python -m <entry_point>` on the Ray cluster.

    Example: ray_job(entry_point="ictl.job.supsi.crawl_uspto.main")
    """


class NumCpusField(FloatField):
    """Number of CPU cores to allocate to the Ray job."""

    alias = "num_cpus"
    default = 1.0
    help = "Number of CPU cores to allocate. Can be fractional (e.g., 0.5 for half a core)."


class NumGpusField(FloatField):
    """Number of GPUs to allocate to the Ray job."""

    alias = "num_gpus"
    default = 0.0
    help = "Number of GPUs to allocate. Can be fractional for shared GPU access."


class MemoryField(IntField):
    """Memory allocation in bytes for the Ray job."""

    alias = "memory"
    default = 256 * 1024 * 1024  # 256MB
    help = """Memory allocation in bytes for the Ray job.

    Example: 4 * 1024**3 for 4GB
    """


class RayAddressField(StringField):
    """Ray cluster address for job submission."""

    alias = "ray_address"
    default = "auto"
    help = """Ray cluster address.

    Can be:
    - "auto" (default) - auto-detect from RAY_ADDRESS env var
    - "http://ray.example.com" - explicit cluster URL
    - "local" - for local testing
    """


class SecretsField(StringSequenceField):
    """List of secret names to pass to the Ray job.

    These are read from the environment at submission time.

    Example: secrets=["AWS_ACCESS_KEY", "AWS_SECRET_KEY"]
    """

    alias = "secrets"
    default = ()
    help = "List of secret env var names to pass to the Ray job."


class RayJobTarget(TargetGenerator):
    """Generates a Ray job submission target.

    Creates a #_submit_script generated target that produces a submit script
    with resource allocation, env vars, and PEX upload logic baked in.

    ## Generated Targets

    - #_submit_script - Generated __ray_submit__.py (used by ray-submit and package)

    ## Parameters

    - entry_point (required) - Python module path to execute
    - num_cpus (default: 1.0) - CPU cores to allocate
    - num_gpus (default: 0.0) - GPUs to allocate
    - memory (default: 256MB) - Memory in bytes
    - ray_address (default: "auto") - Ray cluster address for submit script
    - env_vars (optional) - Dict of env vars (string=fixed, None=required)
    - secrets (optional) - List of secret env var names
    - dependencies (optional) - Additional Pants target dependencies
    - resolve (optional) - Python resolver (default: python-default)
    """

    alias = "ray_job"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        Dependencies,
        EntryPointField,
        NumCpusField,
        NumGpusField,
        MemoryField,
        RayAddressField,
        EnvVarsField,
        SecretsField,
        PythonResolveField,
    )
    help = """Generate a reproducible Ray job submission.

    Creates a #_submit_script target that produces a submit script for
    uploading a source-only PEX to a Ray cluster.

    Example:
        ray_job(
            entry_point="myapp.jobs.etl.main",
            num_cpus=4.0,
            memory=8 * 1024**3,  # 8GB
            env_vars={"API_KEY": None, "DEBUG": "false"},
            dependencies=["//src/python/myapp/lib"],
        )
    """

    # TargetGenerator required attributes
    copied_fields = ()
    moved_fields = (PythonResolveField,)
    generated_target_cls = PythonSourceTarget


class RaySubmitSourceField(SourcesField):
    """Source field for generated submit script.

    NOTE: Uses SourcesField (not SingleSourceField) because Pants validates
    SingleSourceField file count BEFORE running codegen. SourcesField has
    no file count validation, allowing codegen to generate the file.
    """

    alias = "source"
    default = ("__ray_submit__.py",)
    expected_file_extensions = (".py",)


class RaySubmitTarget(Target):
    """Target that generates the submit script."""

    alias = "_ray_submit_script"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        Dependencies,
        RaySubmitSourceField,
        PythonResolveField,
    )
