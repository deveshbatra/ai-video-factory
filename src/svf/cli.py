import argparse
import json
import platform
import shutil
import sys
import os
import subprocess
import uuid
from pathlib import Path
import yaml
from .config import load, ROOT, resolve, Config
from .schemas import EpisodeBrief
from .storage import write_json
from .workflow import create, worker, queue, resume, root_for, IMAGE
from .review import export, costs, select


def doctor(config):
    report = {
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "disk_free_bytes": shutil.disk_usage(ROOT).free,
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "shared_memory_bytes": shutil.disk_usage("/dev/shm").total,
        "cuda": None,
        "gpu_memory_bytes": None,
        "gpu_memory_reason": "GB10 unified memory: NVML metric unsupported",
        "paths": {},
    }
    for field in ["output_root", "model_cache", "asset_root", "database_path"]:
        p = resolve(getattr(config.project, field))
        ancestor = p
        while not ancestor.exists():
            ancestor = ancestor.parent
        report["paths"][field] = {
            "path": str(p),
            "writable": os.access(ancestor, os.W_OK),
        }
    try:
        report["system_meminfo"] = dict(
            line.split(":", 1)
            for line in Path("/proc/meminfo").read_text().splitlines()
        )
    except OSError:
        report["system_meminfo"] = None
    try:
        r = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--gpus",
                "all",
                "--network",
                "none",
                IMAGE,
                "python",
                "-c",
                'import torch,json; x=torch.ones(4,device="cuda"); print(json.dumps(dict(torch=torch.__version__,cuda=torch.version.cuda,device=torch.cuda.get_device_name(),tensor=(x+x).tolist())))',
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        report["cuda"] = (
            json.loads(r.stdout.strip().splitlines()[-1])
            if r.returncode == 0
            else {"unavailable": r.stderr[-1000:]}
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        report["cuda"] = {"unavailable": str(e)}
    return report


def main():
    parser = argparse.ArgumentParser(prog="svf")
    parser.add_argument(
        "command",
        choices=[
            "doctor",
            "validate",
            "plan",
            "enqueue",
            "worker",
            "status",
            "resume",
            "cancel",
            "review",
            "cost",
            "schemas",
        ],
    )
    parser.add_argument("action", nargs="?")
    parser.add_argument(
        "--config",
        default="configs/local.yaml"
        if (ROOT / "configs/local.yaml").exists()
        else "configs/project.example.yaml",
    )
    parser.add_argument("--brief")
    parser.add_argument("--profile")
    parser.add_argument("--episode")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--style")
    parser.add_argument("--reviewer", default="owner")
    parser.add_argument("--stage", default="publish-package")
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    try:
        config = load(args.config)
        if args.command == "doctor":
            result = doctor(config)
        elif args.command == "schemas":
            from . import schemas

            for name, value in vars(schemas).items():
                if isinstance(value, type) and issubclass(value, schemas.Record):
                    write_json(
                        ROOT / "schemas" / (name + ".json"), value.model_json_schema()
                    )
            write_json(ROOT / "schemas/Config.json", Config.model_json_schema())
            result = "schemas exported"
        elif args.command in ["validate", "plan", "enqueue"]:
            if args.brief:
                brief = EpisodeBrief.model_validate(
                    yaml.safe_load(Path(args.brief).read_text())
                )
                if args.command == "validate":
                    result = {"valid": True, "episode": brief.episode_id}
                else:
                    result = str(create(config, brief, args.mock))
                    if args.command == "plan":
                        worker(config, brief.episode_id, stop_after="plan")
            elif args.command == "enqueue" and args.episode:
                result = queue(config).status(args.episode)
            else:
                raise ValueError("--brief required")
        elif args.command == "worker":
            result = {"executed": worker(config, args.episode)}
        elif args.command == "status":
            result = queue(config).status(args.episode)
        elif args.command == "resume":
            result = resume(config, args.episode)
        elif args.command == "cancel":
            queue(config).cancel(args.episode)
            result = "cancel requested"
        elif args.command == "cost":
            result = costs(config, args.episode)
        elif args.command == "review":
            root = root_for(config, args.episode)
            if args.action == "export":
                result = str(export(config, args.episode, root / "review"))
            elif args.action == "revise":
                from .revisions import revise_script

                result = str(
                    revise_script(
                        config, args.episode, args.profile, args.reviewer, args.reason
                    )
                )
            elif args.action == "refine":
                from .schemas import ArtRefinement

                profile = ArtRefinement.model_validate(
                    yaml.safe_load(Path(args.profile).read_text())
                )
                q = queue(config)
                with q.db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if db.execute(
                        "SELECT 1 FROM jobs WHERE episode=? AND stage='images-refinement'",
                        (args.episode,),
                    ).fetchone():
                        raise ValueError(
                            "refinement already registered; resume existing attempt"
                        )
                    db.execute(
                        "UPDATE jobs SET ordinal=ordinal+1 WHERE episode=? AND ordinal>=2",
                        (args.episode,),
                    )
                    db.execute(
                        "INSERT INTO jobs(id,episode,stage,ordinal) VALUES(?,?,?,2)",
                        (
                            args.episode + ":images-refinement",
                            args.episode,
                            "images-refinement",
                        ),
                    )
                write_json(root / "art-refinement.json", profile)
                result = "targeted refinement queued; originals retained"
            elif args.action == "audition":
                from .audition import audition
                from .workflow import stage_dir, latest_images
                from .schemas import EpisodePlan
                from .storage import read_json

                q = queue(config)
                plan = EpisodePlan.model_validate(
                    read_json(stage_dir(q, args.episode, "plan") / "plan.json")
                )
                images = latest_images(q, args.episode)
                target = root / "audition"
                shutil.copytree(images, target, dirs_exist_ok=True)
                audition(
                    plan, target, config.delivery, config=config, episode=args.episode
                )
                result = str(target / "audition.html")
            elif args.action == "select":
                select(config, args.episode, args.style, args.reviewer)
                result = "selection saved"
            elif args.action == "approve":
                bundle = root / "review"
                from .approvals import approve

                if args.stage == "storyboard":
                    from .workflow import stage_dir
                    from .storage import hash_file, now
                    from .schemas import ReviewDecision

                    plan_path = (
                        stage_dir(queue(config), args.episode, "plan") / "plan.json"
                    )
                    decision = ReviewDecision(
                        reviewer=args.reviewer,
                        timestamp=now(),
                        decision="approved",
                        reasons=[args.reason],
                        hashes={"plan.json": hash_file(plan_path)},
                        versions={"plan": 1},
                    )
                    write_json(root / "storyboard-approval.json", decision)
                elif args.stage == "publish-package":
                    decision = approve(bundle, args.reviewer, args.reason)
                else:
                    raise ValueError(
                        "supported approval stages: storyboard, publish-package; use review select for assets"
                    )
                write_json(root / "decisions" / (str(uuid.uuid4()) + ".json"), decision)
                result = "exact hashes approved; nothing published"
            else:
                raise ValueError("review action must be export, select or approve")
        print(json.dumps(result, indent=2, default=str))
    except (ValueError, OSError, RuntimeError, yaml.YAMLError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
