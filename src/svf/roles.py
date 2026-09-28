"""Typed application roles; no agent framework or concurrent model instances."""

from .schemas import Record, EpisodePlan, EpisodeBrief, SeriesBible
from .planning import validate_plan


class Critique(Record):
    mechanical_pass: bool
    issues: list[str]
    editorial_result: str | None = None
    method: str = "deterministic-state-validator-v1"


def critique(plan: EpisodePlan, brief: EpisodeBrief, bible: SeriesBible) -> Critique:
    try:
        if not set(brief.characters) <= {c.id for c in bible.characters}:
            raise ValueError("character absent from series bible")
        if brief.series_id != bible.series_id or brief.series_version != bible.version:
            raise ValueError("series version mismatch")
        for shot in plan.shots:
            if not {a.kind for a in shot.actions} <= set(bible.allowed_actions):
                raise ValueError("action absent from series bible")
        validate_plan(plan, brief, bible)
    except ValueError as error:
        return Critique(mechanical_pass=False, issues=[str(error)])
    return Critique(mechanical_pass=True, issues=[], editorial_result=None)
