"""Compare explicitly verified skill applicability with saved task annotations."""

from logbook_cli.format import skill_chain
from logbook_cli.models import Field


def missing_skills(task, applicable):
    marked = {
        name
        for annotation in task.annotations
        if annotation.kind is Field.SKILLS
        for name in skill_chain(annotation.value).names
    }
    return sorted(set(applicable) - marked)


def summarize(observations):
    """Keep unresolved observations and their attributed recovery information."""
    return [
        observation
        for observation in observations
        if observation.get("status") != "ready"
        and not (
            observation.get("status") == "not_applicable"
            and isinstance(observation.get("reason"), str)
            and observation["reason"].strip()
        )
    ]
