"""CLI wrapper entry points for Alembic convenience commands."""

import sys
from alembic.config import main as alembic_main


def migrate_main():
    """Run 'alembic revision --autogenerate' with optional message."""
    # If user didn't provide any arguments, use defaults
    if len(sys.argv) == 1:
        sys.argv.extend(["revision", "--autogenerate"])
    # If user provided arguments but not the command, prepend revision --autogenerate
    elif not any(arg in sys.argv for arg in ["revision", "upgrade", "downgrade", "heads", "current", "history", "show"]):
        sys.argv.insert(1, "revision")
        sys.argv.insert(2, "--autogenerate")

    alembic_main()


def upgrade_main():
    """Run 'alembic upgrade head' by default."""
    # If user didn't provide any arguments, upgrade to head
    if len(sys.argv) == 1:
        sys.argv.extend(["upgrade", "head"])
    # If user provided arguments but not the command, prepend upgrade
    elif not any(arg in sys.argv for arg in ["revision", "upgrade", "downgrade", "heads", "current", "history", "show"]):
        sys.argv.insert(1, "upgrade")
        if "head" not in sys.argv:
            sys.argv.insert(2, "head")

    alembic_main()


def downgrade_main():
    """Run 'alembic downgrade -1' by default."""
    # If user didn't provide any arguments, downgrade one revision
    if len(sys.argv) == 1:
        sys.argv.extend(["downgrade", "-1"])
    # If user provided arguments but not the command, prepend downgrade
    elif not any(arg in sys.argv for arg in ["revision", "upgrade", "downgrade", "heads", "current", "history", "show"]):
        sys.argv.insert(1, "downgrade")
        if "-1" not in sys.argv:
            sys.argv.insert(2, "-1")

    alembic_main()
