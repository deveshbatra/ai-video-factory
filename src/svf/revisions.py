"""Explicit data-only editorial revisions; original model outputs remain immutable."""

import uuid
import time
from pathlib import Path
import yaml
from .schemas import ScriptDraft, EpisodeBrief, Attempt
from .planning import compile_script
from .storage import read_json, write_json, hash_file, now
from .workflow import queue, root_for, stage_dir, code_hash


def revise_script(config, episode, path, reviewer, reason):
    started = time.monotonic()
    if not reason:
        raise ValueError("revision reason is required")
    q = queue(config)
    root = root_for(config, episode)
    original = stage_dir(q, episode, "plan")
    draft = ScriptDraft.model_validate(yaml.safe_load(Path(path).read_text()))
    brief = EpisodeBrief.model_validate(read_json(root / "brief.json"))
    plan = compile_script(draft, brief)
    plan.plan_critique = [
        f"Explicit editorial action revision by {reviewer}: {reason}. Original Qwen plan retained; revised actions are not represented as raw model output."
    ]
    key = str(uuid.uuid4())
    out = root / "attempts/plan" / key
    out.mkdir(parents=True)
    write_json(out / "script.json", draft)
    write_json(out / "plan.json", plan)
    write_json(
        out / "editorial-revision.json",
        {
            "reviewer": reviewer,
            "reason": reason,
            "original_plan_hash": hash_file(original / "plan.json"),
            "source_file_hash": hash_file(path),
            "asset_reuse_reason": "same human brief, characters, props and visual references; only staging/actions changed",
            "operator_minutes": None,
            "agent_authored_revision": reviewer == "Codex",
        },
    )
    attempt = Attempt(
        id=key,
        job_id=episode + ":plan",
        stage="plan",
        started_at=now(),
        finished_at=now(),
        input_hash=hash_file(original / "plan.json"),
        config_hash=hash_file(root / "resolved-config.json"),
        code_hash=code_hash(),
        seed=config.production.default_seed,
        requested={"revision": str(path)},
        effective={"provider_kind": "local", "editorial_revision": True},
        timings={"wall_seconds": time.monotonic() - started},
        cost={"external_generation_gbp": "0", "operator_minutes": None},
        result="succeeded",
        output_hashes={"plan.json": hash_file(out / "plan.json")},
    )
    write_json(out / "attempt.json", attempt)
    write_json(
        out / "manifest.json",
        {
            "attempt_id": key,
            "outputs": {p.name: hash_file(p) for p in out.iterdir() if p.is_file()},
        },
    )
    with q.db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM jobs WHERE episode=? AND state='running' AND stage IN ('plan','render','qa','review')",
            (episode,),
        ).fetchone():
            raise ValueError("cannot revise an actively executing dependent stage")
        db.execute(
            "UPDATE jobs SET artifact=?,hash=?,state='succeeded',attempts=attempts+1,fence=fence+1 WHERE episode=? AND stage='plan'",
            (str(out / "manifest.json"), hash_file(out / "manifest.json"), episode),
        )
        db.execute(
            "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?)",
            (
                key,
                episode + ":plan",
                0,
                time.time(),
                time.time(),
                "succeeded",
                time.monotonic() - started,
                reason,
            ),
        )
        db.execute(
            "UPDATE jobs SET state='queued',fence=fence+1,error=NULL WHERE episode=? AND stage IN ('render','qa','review')",
            (episode,),
        )
    return out
