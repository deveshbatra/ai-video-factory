from .schemas import EpisodePlan, SceneState
from .storage import digest, canonical


def apply_actions(state, actions):
    state = state.model_copy(deep=True)
    for a in actions:
        if a.kind in ["cut", "camera_move", "sound_cue"]:
            continue
        if a.actor not in state.objects:
            raise ValueError("unknown actor " + a.actor)
        o = state.objects[a.actor]
        if a.target and a.target not in state.objects:
            raise ValueError("unknown target " + a.target)
        target = state.objects.get(a.target)
        if a.kind in ["move", "carry"]:
            if a.x is None or a.y is None:
                raise ValueError("movement requires x,y")
            if a.kind == "carry" and (target is None or target.owner != a.actor):
                raise ValueError("carry requires ownership")
            o.x = a.x
            o.y = a.y
            for prop in state.objects.values():
                if prop.owner == a.actor:
                    prop.x = o.x
                    prop.y = o.y - 0.1
        elif a.kind == "pick_up":
            if target is None or target.owner is not None:
                raise ValueError("cannot pick up owned/missing prop")
            if abs(o.x - target.x) > 0.3 or abs(o.y - target.y) > 0.3:
                raise ValueError("prop out of reach")
            target.owner = a.actor
            target.supported_by = a.actor
        elif a.kind == "place":
            if target is None or target.owner != a.actor:
                raise ValueError("place requires ownership")
            target.owner = None
            target.supported_by = None
        elif a.kind in ["pose", "look"]:
            o.pose = a.value
        elif a.kind in ["activate_switch", "change_mechanism_state"]:
            if target is None:
                raise ValueError("mechanism target required")
            target.pose = a.value
    return state


def validate_plan(plan, brief, bible=None):
    if plan.brief_id != brief.episode_id or plan.brief_hash != digest(canonical(brief)):
        raise ValueError("brief provenance mismatch")
    if (
        not brief.duration_seconds.min
        <= plan.shots[-1].end
        <= brief.duration_seconds.max
    ):
        raise ValueError("duration outside brief")
    known = set(brief.characters + brief.required_props)
    previous = None
    for s in plan.shots:
        if set(s.opening_state.objects) != known or not set(s.cast) <= set(
            brief.characters
        ):
            raise ValueError("unknown or missing story objects")
        if previous is not None and s.opening_state != previous:
            raise ValueError("continuity changed across cut")
        computed = apply_actions(s.opening_state, s.actions)
        if computed != s.closing_state:
            raise ValueError("closing state does not match action postconditions")
        previous = s.closing_state
    if plan.unresolved_issues:
        raise ValueError("unresolved plan issues require revision")
    return plan


def fixture(brief):
    from .schemas import Action, ShotPlan, ObjectState

    objects = {
        x: ObjectState(x=0.2 + i * 0.12, y=0.65)
        for i, x in enumerate(brief.characters + brief.required_props)
    }
    state = SceneState(objects=objects)
    mystery = brief.content_family == "mystery"
    purposes = [
        "Discover the obstacle",
        "Test the first approach",
        "Notice the clue",
        "Try the complementary approach",
        "Resolve the question",
    ]
    if mystery:
        purposes = [
            "Discover the odd signal",
            "Repeat the experiment",
            "Find the hidden cause",
            "Test the explanation",
            "Reveal the mechanism",
        ]
    shots = []
    duration = brief.duration_seconds.min / 5
    for i, purpose in enumerate(purposes):
        actor = brief.characters[i % len(brief.characters)]
        actions = [
            Action(
                kind="pose",
                actor=actor,
                value=["curious", "strained", "surprised", "determined", "happy"][i],
            ),
            Action(kind="move", actor=actor, x=0.2 + 0.12 * i, y=0.65),
            Action(kind="sound_cue", actor=actor, value="chime"),
        ]
        close = apply_actions(state, actions)
        shots.append(
            ShotPlan(
                id=f"shot{i + 1}",
                start=i * duration,
                end=(i + 1) * duration,
                purpose=purpose,
                cast=brief.characters,
                opening_state=state,
                closing_state=close,
                actions=actions,
                keyframe_prompt=brief.original_brief,
            )
        )
        state = close
    return validate_plan(
        EpisodePlan(
            brief_id=brief.episode_id,
            brief_hash=digest(canonical(brief)),
            provider_kind="mock",
            hook=brief.viewer_question,
            beats=purposes,
            causal_explanation="Fixture timeline tests mechanics only.",
            ending=brief.payoff,
            shots=shots,
        ),
        brief,
    )


def compile_script(draft, brief):
    """Derive repeated timeline/state fields; never invent model actions or story beats."""
    from .schemas import ShotPlan

    state = draft.initial_state
    start = 0
    shots = []
    for shot in draft.shots:
        closing = apply_actions(state, shot.actions)
        shots.append(
            ShotPlan(
                id=shot.id,
                start=start,
                end=start + shot.duration_seconds,
                purpose=shot.purpose,
                cast=brief.characters,
                opening_state=state,
                closing_state=closing,
                camera=shot.camera,
                actions=shot.actions,
                keyframe_prompt=shot.keyframe_prompt,
            )
        )
        state = closing
        start += shot.duration_seconds
    return validate_plan(
        EpisodePlan(
            brief_id=brief.episode_id,
            brief_hash=digest(canonical(brief)),
            provider_kind="local",
            hook=draft.hook,
            beats=[s.purpose for s in draft.shots],
            causal_explanation=draft.causal_explanation,
            ending=draft.ending,
            shots=shots,
        ),
        brief,
    )
