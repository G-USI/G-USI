"""Code generation for Alembic commands.py file."""

from dataclasses import dataclass

from pants.backend.python.target_types import PythonSourceField
from pants.engine.fs import CreateDigest, Digest, FileContent, Snapshot
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.target import (
    GenerateSourcesRequest,
    GeneratedSources,
    SourcesField,
)

from gusi.pants.backend.alembic.templates import (
    get_alembic_wrapper_template,
    get_commands_template,
)


class AlembicCommandsPySourceField(SourcesField):
    """Marker field indicating that commands.py should be generated.

    This field doesn't point to actual source files - it's used to trigger
    the commands.py generation rule.
    """

    alias = "source"
    default = ("commands.py",)
    expected_file_extensions = (".py",)


@dataclass(frozen=True)
class GenerateAlembicCommandsPyRequest(GenerateSourcesRequest):
    """Request to generate commands.py for Alembic migrations."""

    input = AlembicCommandsPySourceField
    output = PythonSourceField


@rule
async def generate_alembic_commands_py(
    request: GenerateAlembicCommandsPyRequest,
) -> GeneratedSources:
    """Generate commands.py file with Alembic convenience commands.

    This creates a virtual Python file that only exists in the Pants sandbox.
    The file contains wrapper functions for common Alembic operations.
    """
    # Get the config path and file path from the target's spec_path
    spec_path = request.protocol_target.address.spec_path
    config_path = f"{spec_path}/alembic.ini"
    file_path = f"{spec_path}/commands.py"

    # Generate the commands.py content from template
    content = get_commands_template(config_path)

    # Create file digest with full path
    digest = await Get(
        Digest,
        CreateDigest(
            [
                FileContent(
                    path=file_path,
                    content=content.encode("utf-8"),
                    is_executable=False,
                )
            ]
        ),
    )

    # Convert to snapshot
    snapshot = await Get(Snapshot, Digest, digest)

    return GeneratedSources(snapshot)


class AlembicWrapperPySourceField(SourcesField):
    """Marker field indicating that alembic_wrapper.py should be generated.

    This field doesn't point to actual source files - it's used to trigger
    the alembic_wrapper.py generation rule.
    """

    alias = "source"
    default = ("alembic_wrapper.py",)
    expected_file_extensions = (".py",)


@dataclass(frozen=True)
class GenerateAlembicWrapperPyRequest(GenerateSourcesRequest):
    """Request to generate alembic_wrapper.py for Alembic CLI."""

    input = AlembicWrapperPySourceField
    output = PythonSourceField


@rule
async def generate_alembic_wrapper_py(
    request: GenerateAlembicWrapperPyRequest,
) -> GeneratedSources:
    """Generate alembic_wrapper.py file with config path auto-detection.

    This creates a virtual Python file that only exists in the Pants sandbox.
    The file wraps the Alembic CLI to auto-detect the config path.
    """
    # Get the config path and file path from the target's spec_path
    spec_path = request.protocol_target.address.spec_path
    config_path = f"{spec_path}/alembic.ini"
    file_path = f"{spec_path}/alembic_wrapper.py"

    # Generate the alembic_wrapper.py content from template
    content = get_alembic_wrapper_template(config_path)

    # Create file digest with full path
    digest = await Get(
        Digest,
        CreateDigest(
            [
                FileContent(
                    path=file_path,
                    content=content.encode("utf-8"),
                    is_executable=False,
                )
            ]
        ),
    )

    # Convert to snapshot
    snapshot = await Get(Snapshot, Digest, digest)

    return GeneratedSources(snapshot)


def rules():
    """Return all rules for Alembic code generation."""
    return collect_rules()
