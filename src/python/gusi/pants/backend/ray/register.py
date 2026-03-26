"""Registration module for the Ray job plugin."""

from gusi.pants.backend.ray import goal as goal_mod
from gusi.pants.backend.ray import rules as rules_mod
from gusi.pants.backend.ray import target_generator
from gusi.pants.backend.ray.target_types import RayJobTarget, RaySubmitTarget


def target_types():
    """Export target types to Pants."""
    return [
        RayJobTarget,
        RaySubmitTarget,
    ]


def rules():
    """Register build rules with Pants."""
    return [
        *target_generator.rules(),
        *rules_mod.rules(),
        *goal_mod.rules(),
    ]


def required_backends():
    """Declare dependencies on other Pants backends."""
    return ["pants.backend.python"]
