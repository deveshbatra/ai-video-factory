import pytest
import yaml
from svf.config import Config, ROOT
from svf.schemas import EpisodeBrief, Action
from svf.planning import fixture, validate_plan, apply_actions
from svf.storage import child


def config():
    return yaml.safe_load((ROOT / "configs/project.example.yaml").read_text())


def brief():
    return EpisodeBrief.model_validate(
        yaml.safe_load((ROOT / "examples/episode-brief.yaml").read_text())
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(typo=True),
        lambda c: c["costs"].update(max_external_generation_spend_per_run=1),
        lambda c: c["project"].update(output_root="/tmp/escape"),
        lambda c: c["resources"].update(gpu_concurrency=2),
        lambda c: c["production"].update(max_schema_repairs=3),
        lambda c: c["delivery"].update(width=101),
        lambda c: c["resources"]["downloads"].update(max_total_gib=-1),
    ],
)
def test_invalid_config(change):
    c = config()
    change(c)
    with pytest.raises(ValueError):
        Config.model_validate(c)


def test_path_traversal_and_symlink(tmp_path):
    with pytest.raises(ValueError):
        child(tmp_path, "../escape")
    (tmp_path / "link").symlink_to("/etc")
    with pytest.raises(ValueError):
        child(tmp_path, "link/passwd")


def test_plan_continuity():
    b = brief()
    p = fixture(b)
    p.shots[1].opening_state = p.shots[1].opening_state.model_copy(deep=True)
    p.shots[1].opening_state.objects["pip"].x = 0.99
    with pytest.raises(ValueError, match="continuity"):
        validate_plan(p, b)


def test_unintroduced_target():
    s = fixture(brief()).shots[0].opening_state
    with pytest.raises(ValueError, match="unknown target"):
        apply_actions(s, [Action(kind="pick_up", actor="pip", target="magic_ladder")])


def test_ownership():
    s = fixture(brief()).shots[0].opening_state
    with pytest.raises(ValueError, match="ownership"):
        apply_actions(
            s, [Action(kind="carry", actor="pip", target="oversized_key", x=0.2, y=0.5)]
        )


def test_timeline_gap():
    p = fixture(brief()).model_dump()
    p["shots"][1]["start"] += 1
    from svf.schemas import EpisodePlan

    with pytest.raises(ValueError, match="timeline"):
        EpisodePlan.model_validate(p)


def test_renderer_executes_actions_in_order():
    from svf.rendering import sampled_state
    from svf.schemas import ShotPlan, SceneState, ObjectState

    state = SceneState(
        objects={"pip": ObjectState(x=0.2, y=0.6), "key": ObjectState(x=0.3, y=0.6)}
    )
    actions = [
        Action(kind="pick_up", actor="pip", target="key"),
        Action(kind="carry", actor="pip", target="key", x=0.7, y=0.6),
    ]
    shot = ShotPlan(
        id="one",
        start=0,
        end=5,
        purpose="carry key",
        cast=["pip"],
        opening_state=state,
        closing_state=apply_actions(state, actions),
        actions=actions,
        keyframe_prompt="carry",
    )
    first = sampled_state(shot, 0.3)
    last = sampled_state(shot, 0.99)
    assert first.objects["key"].owner == "pip"
    assert first.objects["pip"].x == 0.2
    assert last.objects["pip"].x > 0.69
    assert abs(last.objects["key"].x - last.objects["pip"].x) < 0.001


def test_cpu_cli_does_not_import_cuda():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import svf.cli,sys; assert 'torch' not in sys.modules and 'diffusers' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_review_contract_requires_utc_and_sha256():
    from svf.schemas import ReviewDecision

    with pytest.raises(ValueError):
        ReviewDecision(
            reviewer="owner",
            timestamp="2026-09-12T01:00:00",
            decision="approved",
            reasons=[],
            hashes={"media": "not-a-hash"},
            versions={"package": 1},
        )
