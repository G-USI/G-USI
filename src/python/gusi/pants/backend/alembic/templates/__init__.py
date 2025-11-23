"""Template files for Alembic boilerplate generation."""

from .alembic_ini import ALEMBIC_INI_TEMPLATE
from .alembic_wrapper_py import get_alembic_wrapper_template
from .commands_py import get_commands_template
from .env_py import ENV_PY_TEMPLATE
from .script_mako import SCRIPT_MAKO_TEMPLATE

__all__ = [
    "ALEMBIC_INI_TEMPLATE",
    "ENV_PY_TEMPLATE",
    "SCRIPT_MAKO_TEMPLATE",
    "get_alembic_wrapper_template",
    "get_commands_template",
]
