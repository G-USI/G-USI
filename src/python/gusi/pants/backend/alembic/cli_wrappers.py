"""CLI wrapper entry points for Alembic convenience commands."""

import sys
import os
from pathlib import Path
from alembic.config import main as alembic_main


def _find_project_root():
    """Find the project root by looking for pants.toml or .git directory."""
    current = Path.cwd()

    # Check current directory and parents
    for parent in [current] + list(current.parents):
        if (parent / "pants.toml").exists() or (parent / ".git").exists():
            return parent

    # If not found, return current directory
    return current


def _find_alembic_ini():
    """Find alembic.ini by checking environment variable or searching from project root.

    The alembic.ini file location can be provided via ALEMBIC_INI_RELPATH environment variable
    (set by the Pants target generator). If not provided, falls back to searching common patterns.
    """
    # Change to project root if not already there
    project_root = _find_project_root()
    if Path.cwd() != project_root:
        os.chdir(project_root)

    # First check if path is provided via environment variable (preferred method)
    if ini_relpath := os.getenv("ALEMBIC_INI_RELPATH"):
        ini_path = project_root / ini_relpath
        if ini_path.exists():
            return ini_relpath
        # If env var is set but file doesn't exist, log and fall through to search
        print(f"Warning: ALEMBIC_INI_RELPATH={ini_relpath} set but file not found, falling back to search", file=sys.stderr)

    # Fallback: check if alembic.ini exists in current directory
    if (project_root / "alembic.ini").exists():
        return "alembic.ini"

    # Fallback: search for alembic.ini in migration directories
    # Pattern: look for any alembic.ini under mig/ directories (Neuroslav pattern)
    for ini_path in project_root.rglob("mig/*/alembic.ini"):
        # Return path relative to project root
        return str(ini_path.relative_to(project_root))

    # Pattern: look for any alembic.ini under srv/*/migrations/ directories (Catalyst pattern)
    for ini_path in project_root.rglob("srv/*/migrations/alembic.ini"):
        # Return path relative to project root
        return str(ini_path.relative_to(project_root))

    # If still not found, try searching anywhere under src/python (avoid finding dependencies in dist/)
    for ini_path in (project_root / "src" / "python").rglob("alembic.ini"):
        return str(ini_path.relative_to(project_root))

    # If not found, return default and let Alembic handle the error
    return "alembic.ini"


def migrate_main():
    """Run 'alembic revision --autogenerate' with optional message."""
    # Ensure -c alembic.ini is present if not already specified
    config_idx = 2  # position after -c and config path
    if "-c" not in sys.argv and "--config" not in sys.argv:
        config_path = _find_alembic_ini()
        sys.argv.insert(1, "-c")
        sys.argv.insert(2, config_path)
        config_idx = 3
    else:
        # Find where the config path ends
        try:
            c_idx = sys.argv.index("-c") if "-c" in sys.argv else sys.argv.index("--config")
            config_idx = c_idx + 2  # skip -c and the path
        except (ValueError, IndexError):
            config_idx = 1

    # If revision command not present, insert it
    if not any(arg in sys.argv for arg in ["revision", "upgrade", "downgrade", "heads", "current", "history", "show"]):
        sys.argv.insert(config_idx, "revision")
        sys.argv.insert(config_idx + 1, "--autogenerate")

    alembic_main()


def upgrade_main():
    """Run 'alembic upgrade head' by default."""
    # Ensure -c alembic.ini is present if not already specified
    if "-c" not in sys.argv and "--config" not in sys.argv:
        config_path = _find_alembic_ini()
        sys.argv.insert(1, "-c")
        sys.argv.insert(2, config_path)

    # If user didn't provide any arguments (besides -c), upgrade to head
    if len(sys.argv) <= 3:  # script name + -c + alembic.ini
        sys.argv.extend(["upgrade", "head"])
    # If user provided arguments but not the command, append upgrade
    elif not any(arg in sys.argv for arg in ["revision", "upgrade", "downgrade", "heads", "current", "history", "show"]):
        sys.argv.append("upgrade")
        if "head" not in sys.argv:
            sys.argv.append("head")

    alembic_main()


def downgrade_main():
    """Run 'alembic downgrade -1' by default."""
    # Ensure -c alembic.ini is present if not already specified
    if "-c" not in sys.argv and "--config" not in sys.argv:
        config_path = _find_alembic_ini()
        sys.argv.insert(1, "-c")
        sys.argv.insert(2, config_path)

    # If user didn't provide any arguments (besides -c), downgrade one revision
    if len(sys.argv) <= 3:  # script name + -c + alembic.ini
        sys.argv.extend(["downgrade", "-1"])
    # If user provided arguments but not the command, append downgrade
    elif not any(arg in sys.argv for arg in ["revision", "upgrade", "downgrade", "heads", "current", "history", "show"]):
        sys.argv.append("downgrade")
        if "-1" not in sys.argv:
            sys.argv.append("-1")

    alembic_main()
