#!/usr/bin/env python3
"""One-command local episode runner. Reads YAML, resumes work, never publishes."""

import argparse
import json
import sys
from pathlib import Path
import yaml
from svf.config import load
from svf.schemas import EpisodeBrief, EpisodePlan, ReviewDecision
from svf.storage import read_json, write_json, hash_file, now
from svf.workflow import create, resume, worker, queue, stage_dir
from svf.review import select, export, costs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/local.yaml")
    parser.add_argument("--brief", default="examples/episode-brief.yaml")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Explicit CPU fixture run; rejected in production mode",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Stop with remaining review commands instead of prompting",
    )
    args = parser.parse_args()
    config = load(args.config)
    brief = EpisodeBrief.model_validate(yaml.safe_load(Path(args.brief).read_text()))
    root = create(config, brief, args.mock)
    resume(config, brief.episode_id)
    q = queue(config)
    rows = q.status(brief.episode_id)
    needs_review = not args.mock and any(
        row["stage"] == "render" and row["state"] != "succeeded" for row in rows
    )
    # Avoid consuming an attempt merely to rediscover a known human review gate.
    if (
        needs_review
        and (root / "storyboard-approval.json").exists()
        and (root / "selection.json").exists()
    ):
        try:
            approved = read_json(root / "storyboard-approval.json")["hashes"].get(
                "plan.json"
            )
            needs_review = approved != hash_file(
                stage_dir(q, brief.episode_id, "plan") / "plan.json"
            )
        except (OSError, ValueError, RuntimeError):
            pass
    if needs_review and all(
        any(row["stage"] == stage and row["state"] == "succeeded" for row in rows)
        for stage in ["plan", "images"]
    ):
        with q.db() as db:
            db.execute(
                "UPDATE jobs SET state='blocked',error='HUMAN_REVIEW_REQUIRED' WHERE episode=? AND stage='render' AND state='queued'",
                (brief.episode_id,),
            )
    worker(config, brief.episode_id)
    rows = q.status(brief.episode_id)
    errors = [
        r
        for r in rows
        if r["state"] == "failed"
        or (r["state"] == "blocked" and r["stage"] != "render")
    ]
    if errors:
        print(json.dumps(errors, indent=2))
        return 1
    if not args.mock and any(
        r["stage"] == "render" and r["state"] == "blocked" for r in rows
    ):
        plan_path = stage_dir(q, brief.episode_id, "plan") / "plan.json"
        plan = EpisodePlan.model_validate(read_json(plan_path))
        print("\nStoryboard:")
        for shot in plan.shots:
            print(f"  {shot.start:5.1f}–{shot.end:5.1f}s  {shot.purpose}")
        print(f"\nVisual audition: {root / 'audition/audition.html'}")
        print(f"Generated assets: {root / 'attempts'}")
        if args.non_interactive or not sys.stdin.isatty():
            print(
                "Review is pending. Run this command in an interactive terminal to choose a style and approve the storyboard."
            )
            return 2
        style = input(
            "\nChoose illustrated_cutout or detailed_pixel_art (Enter to stop): "
        ).strip()
        if style not in ["illustrated_cutout", "detailed_pixel_art"]:
            print("Progress saved.")
            return 2
        if (
            input("Approve the displayed storyboard for this prototype? [y/N] ")
            .strip()
            .lower()
            != "y"
        ):
            print(
                "Progress saved. Edit the brief or apply a review revision before continuing."
            )
            return 2
        select(config, brief.episode_id, style, "terminal operator")
        decision = ReviewDecision(
            reviewer="terminal operator",
            timestamp=now(),
            decision="approved",
            reasons=["Explicit terminal approval after storyboard and asset review"],
            hashes={"plan.json": hash_file(plan_path)},
            versions={"plan": 1},
        )
        write_json(root / "storyboard-approval.json", decision)
        resume(config, brief.episode_id)
        worker(config, brief.episode_id)
    rows = q.status(brief.episode_id)
    if any(r["state"] != "succeeded" for r in rows):
        print(json.dumps(rows, indent=2))
        return 2
    bundle = export(config, brief.episode_id, root / "review")
    print(f"\nVideo:  {bundle / 'final.mp4'}\nReview: {bundle / 'index.html'}")
    print(json.dumps(costs(config, brief.episode_id), indent=2))
    print("Nothing has been published.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, yaml.YAMLError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
