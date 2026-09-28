import os
import shutil
import subprocess
import time
import uuid
import threading
import json
from pathlib import Path
from .config import ROOT, resolve, Config
from .storage import now, digest, hash_file, write_json, read_json, child
from .schemas import EpisodeBrief, EpisodePlan, Attempt
from .planning import fixture
from .jobs import Queue
from .rendering import render
from .qa import inspect

IMAGE = "sha256:1c3f366721fb9fc176e0bcb85537776e8a1b1353e26a10fa7ebec893a12719fa"
STAGES = ["plan", "images", "render", "qa", "review"]


class Blocked(RuntimeError):
    pass


def root_for(config, episode):
    return child(resolve(config.project.output_root), episode)


def queue(config):
    return Queue(resolve(config.project.database_path))


def code_hash():
    return digest(
        b"".join(p.read_bytes() for p in sorted((ROOT / "src/svf").glob("*.py")))
    )


def create(config, brief, mock=False):
    if mock and config.project.mode == "production":
        raise ValueError("production rejects mock providers")
    root = root_for(config, brief.episode_id)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "brief.json").exists():
        if read_json(root / "brief.json") != brief.model_dump(
            mode="json"
        ) or Config.model_validate(read_json(root / "resolved-config.json")).model_dump(
            mode="json"
        ) != config.model_dump(mode="json"):
            raise ValueError(
                "episode exists with different inputs; use a new episode ID"
            )
        if read_json(root / "run.json")["provider_kind"] != (
            "mock" if mock else "local"
        ):
            raise ValueError("cannot change provider kind for existing run")
    else:
        write_json(root / "brief.json", brief)
        write_json(root / "resolved-config.json", config)
        write_json(
            root / "run.json",
            {
                "provider_kind": "mock" if mock else "local",
                "state": "draft",
                "created_at": now(),
                "code_hash": code_hash(),
            },
        )
    queue(config).enqueue(brief.episode_id, STAGES)
    return root


def stage_dir(q, episode, stage):
    row = next(r for r in q.status(episode) if r["stage"] == stage)
    if row["state"] != "succeeded":
        raise Blocked("dependency not complete: " + stage)
    p = Path(row["artifact"])
    if hash_file(p) != row["hash"]:
        raise Blocked("dependency manifest changed: " + stage)
    manifest = read_json(p)
    for name, sha in manifest["outputs"].items():
        if hash_file(child(p.parent, name)) != sha:
            raise Blocked("dependency artifact changed: " + name)
    return p.parent


def inference(config, q, job, request, out):
    if shutil.disk_usage(ROOT).free < config.resources.min_free_disk_gib * 1024**3:
        raise Blocked("DISK_RESERVE")
    mem = (
        int(
            next(
                line.split()[1]
                for line in Path("/proc/meminfo").read_text().splitlines()
                if line.startswith("MemAvailable:")
            )
        )
        * 1024
    )
    if mem < config.resources.min_available_system_ram_gib * 1024**3:
        raise Blocked("MEMORY_RESERVE")
    with q.db() as db:
        used = db.execute(
            "SELECT COALESCE(SUM(seconds),0) FROM attempts a JOIN jobs j ON a.job=j.id WHERE j.stage IN ('plan','images')"
        ).fetchone()[0]
    timeout = min(config.resources.gpu_job_timeout_minutes * 60, 10800 - used)
    if timeout <= 0:
        raise Blocked("GPU_BUDGET_EXHAUSTED")
    from .providers import REVISIONS

    expected = REVISIONS[request["kind"]]
    selected = getattr(config.providers, request["kind"])
    if (selected.model_id, selected.revision) != expected:
        raise Blocked("MODEL_REGISTRY_MISMATCH")
    request["gpu_lock"] = str(ROOT / "state/global-device.lock")
    request["cache"] = str(resolve(config.project.model_cache))
    request["seed"] = config.production.default_seed
    request["generation"] = getattr(config.inference, request["kind"]).model_dump(
        mode="json"
    )
    frozen_source = out / "runtime-source"
    shutil.copytree(
        ROOT / "src/svf",
        frozen_source / "svf",
        ignore=shutil.ignore_patterns("__pycache__"),
        dirs_exist_ok=True,
    )
    if "prompt" in request:
        shutil.copy2(request["prompt"], out / "prompt.txt")
        request["prompt"] = str(out / "prompt.txt")
    request_path = out / "request.json"
    write_json(request_path, request)
    name = "svf-" + job["attempt_id"]
    cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--gpus",
        "all",
        "--network",
        "none",
        "--shm-size",
        "8g",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "HF_HUB_OFFLINE=1",
        "-e",
        "TRANSFORMERS_OFFLINE=1",
        "-e",
        "PYTHONPATH=" + str(frozen_source),
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-v",
        f"{ROOT}:{ROOT}",
        "-w",
        str(ROOT),
        IMAGE,
        "python",
        "-m",
        "svf.providers",
        str(request_path),
        str(out),
    ]
    with q.gpu(job, config.resources.lease_seconds, wait=True) as lock:
        from .budgets import Budget

        budget = Budget(ROOT / "state/authorised-gpu-budget.sqlite3")
        reservation, timeout = budget.reserve(timeout, job["id"])
        timeout -= 10
        if timeout <= 0:
            budget.finish(reservation, 0)
            raise Blocked("GPU_BUDGET_EXHAUSTED: insufficient cleanup reserve")
        started = time.monotonic()
        with open(out / "runtime.log", "w") as log:
            p = subprocess.Popen(
                cmd, stdout=log, stderr=subprocess.STDOUT, pass_fds=(lock,)
            )
            try:
                while p.poll() is None:
                    q.heartbeat(job, config.resources.lease_seconds)
                    if time.monotonic() - started > timeout:
                        raise Blocked("GPU_TIMEOUT")
                    time.sleep(1)
                if p.returncode:
                    raise RuntimeError(
                        "inference failed; see " + str(out / "runtime.log")
                    )
            finally:
                if p.poll() is None:
                    subprocess.run(
                        ["docker", "stop", "--time", "5", name],
                        capture_output=True,
                        timeout=20,
                    )
                    p.wait(timeout=30)
                budget.finish(reservation, time.monotonic() - started)


def image_requests(plan, brief):
    images = []
    for style in ["detailed_pixel_art", "illustrated_cutout"]:
        look = (
            "rich detailed pixel art, nuanced lighting, expressive silhouettes, beautiful indie adventure game"
            if style == "detailed_pixel_art"
            else "stylised illustrated paper cutout, gouache texture, expressive silhouettes, handcrafted theatrical lighting"
        )
        images.append(
            {
                "id": style + "-hero",
                "prompt": look
                + ". A beautifully staged theatrical background for this original story, no characters, no lettering. Keep props clearly separated and readable. "
                + brief.original_brief,
            }
        )
        for name, color in [
            (
                "pip",
                "warm amber, small slender curious brass automaton, long articulated arms",
            ),
            ("moss", "teal, short broad sturdy practical automaton, strong arms"),
        ]:
            images.append(
                {
                    "id": style + "-" + name,
                    "prompt": look
                    + ". One single full body original character: "
                    + color
                    + ". Expressive kind face, three quarter front view, standing, feet visible, centered, isolated on pure white background, no ground shadow, no props, character design illustration.",
                }
            )
    return images


def latest_images(q, episode):
    rows = q.status(episode)
    stage = (
        "images-refinement"
        if any(
            r["stage"] == "images-refinement" and r["state"] == "succeeded"
            for r in rows
        )
        else "images"
    )
    return stage_dir(q, episode, stage)


def selected_assets(root, images):
    if not (root / "selection.json").exists():
        raise Blocked(
            "ASSET_SELECTION_REQUIRED: inspect candidates then run svf review select --episode ID --style STYLE --reviewer NAME"
        )
    selection = read_json(root / "selection.json")
    style = selection["style"]
    for filename, sha in selection["hashes"].items():
        if hash_file(child(images, filename)) != sha:
            raise Blocked("selected asset hash changed")
    for name in ["pip", "moss"]:
        derived = root / "assets" / f"{style}-{name}.png"
        metadata = read_json(derived.with_suffix(".json"))
        if hash_file(derived) != metadata["sha256"]:
            raise Blocked("DERIVED_ASSET_HASH_CHANGED")
    return {
        "background": images / (style + "-hero.png"),
        "pip": root / "assets" / f"{style}-pip.png",
        "moss": root / "assets" / f"{style}-moss.png",
    }


def execute(config, q, job, out):
    root = root_for(config, job["episode"])
    if Config.model_validate(read_json(root / "resolved-config.json")).model_dump(
        mode="json"
    ) != config.model_dump(mode="json"):
        raise Blocked("CONFIG_CHANGED: create a new episode version")
    brief = EpisodeBrief.model_validate(read_json(root / "brief.json"))
    run = read_json(root / "run.json")
    mock = run["provider_kind"] == "mock"
    if config.project.mode == "production" and mock:
        raise ValueError("production rejects mocks")
    stage = job["stage"]
    if stage == "plan":
        if mock:
            write_json(out / "plan.json", fixture(brief))
        else:
            if not config.providers.text.enabled:
                raise Blocked("TEXT_PROVIDER_DISABLED")
            inference(
                config,
                q,
                job,
                {
                    "kind": "text",
                    "brief": brief.model_dump(mode="json"),
                    "repairs": config.production.max_schema_repairs,
                    "prompt": str(ROOT / "prompts/writer-v2.txt"),
                    "contract": "script-v2",
                    "change_reason": "Full-state EpisodePlan v1 produced invalid durations and repeated state inconsistencies; v2 compiles states from model actions",
                },
                out,
            )
    elif stage == "images":
        plan = EpisodePlan.model_validate(
            read_json(stage_dir(q, job["episode"], "plan") / "plan.json")
        )
        if mock:
            write_json(
                out / "mock.json",
                {"provider_kind": "mock", "assets": "procedural preview primitives"},
            )
        else:
            if not config.providers.image.enabled:
                raise Blocked("IMAGE_PROVIDER_DISABLED")
            inference(
                config,
                q,
                job,
                {"kind": "image", "images": image_requests(plan, brief)},
                out,
            )
    elif stage == "images-refinement":
        from .schemas import ArtRefinement

        profile = ArtRefinement.model_validate(read_json(root / "art-refinement.json"))
        original = stage_dir(q, job["episode"], "images")
        shutil.copytree(original, out / "prior-candidates")
        for path in original.glob("*.png"):
            shutil.copy2(path, out / path.name)
        inference(
            config,
            q,
            job,
            {
                "kind": "image",
                "images": [image.model_dump(mode="json") for image in profile.images],
                "change_reason": profile.reason,
            },
            out,
        )
    elif stage == "render":
        plan = EpisodePlan.model_validate(
            read_json(stage_dir(q, job["episode"], "plan") / "plan.json")
        )
        if not mock and config.production.storyboard_review_required:
            approval = root / "storyboard-approval.json"
            plan_file = stage_dir(q, job["episode"], "plan") / "plan.json"
            if not approval.exists() or read_json(approval)["hashes"].get(
                "plan.json"
            ) != hash_file(plan_file):
                raise Blocked(
                    "STORYBOARD_REVIEW_REQUIRED: svf review approve --stage storyboard --episode "
                    + job["episode"]
                )
        assets = (
            None if mock else selected_assets(root, latest_images(q, job["episode"]))
        )
        render(
            plan,
            out,
            config.delivery,
            assets,
            lambda: q.heartbeat(job, config.resources.lease_seconds),
        )
    elif stage == "qa":
        rendered = stage_dir(q, job["episode"], "render")
        plan = EpisodePlan.model_validate(
            read_json(stage_dir(q, job["episode"], "plan") / "plan.json")
        )
        qa = inspect(
            rendered / "final.mp4",
            plan,
            config.delivery.width,
            config.delivery.height,
            config.delivery.fps,
        )
        write_json(out / "qa.json", qa)
        if any(c.status == "fail" for c in qa.checks):
            raise RuntimeError("technical QA failed")
    elif stage == "review":
        from .review import export

        export(config, job["episode"], out)
    else:
        raise ValueError("unknown stage")


def worker(config, episode=None, stop_after=None):
    q = queue(config)
    from .recovery import reconcile

    reconcile(q, resolve(config.project.output_root))
    owner = str(uuid.uuid4())
    completed = 0
    while job := q.claim(
        owner,
        config.resources.lease_seconds,
        1 + config.production.max_infrastructure_retries,
        episode,
    ):
        root = root_for(config, job["episode"])
        out = root / "attempts" / job["stage"] / job["attempt_id"]
        out.mkdir(parents=True)
        source_hash = code_hash()
        write_json(
            out / "source-provenance.json",
            {
                "files": {
                    str(p.relative_to(ROOT)): hash_file(p)
                    for p in sorted((ROOT / "src/svf").glob("*.py"))
                },
                "runtime_image": IMAGE,
                "prompt_files": {
                    str(p.relative_to(ROOT)): hash_file(p)
                    for p in sorted((ROOT / "prompts").glob("*.txt"))
                },
            },
        )
        started = time.monotonic()
        started_at = now()
        stop = threading.Event()

        def heartbeat():
            while not stop.wait(config.resources.heartbeat_seconds):
                try:
                    q.heartbeat(job, config.resources.lease_seconds)
                except RuntimeError:
                    return

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        state = "succeeded"
        error = None
        try:
            execute(config, q, job, out)
        except Blocked as e:
            state = "blocked"
            error = str(e)
        except Exception as e:
            state = "failed"
            error = str(e)
        finally:
            stop.set()
            thread.join()
        outputs = {
            str(p.relative_to(out)): hash_file(p) for p in out.rglob("*") if p.is_file()
        }
        attempt = Attempt(
            id=job["attempt_id"],
            job_id=job["id"],
            stage=job["stage"],
            started_at=started_at,
            finished_at=now(),
            input_hash=hash_file(root / "brief.json"),
            config_hash=hash_file(root / "resolved-config.json"),
            code_hash=source_hash,
            model_hash=digest((out / "inference.json").read_bytes())
            if (out / "inference.json").exists()
            else None,
            prompt_hash=hash_file(out / "request.json")
            if (out / "request.json").exists()
            else None,
            seed=config.production.default_seed,
            requested={"stage": job["stage"]},
            effective={"provider_kind": read_json(root / "run.json")["provider_kind"]},
            timings={"wall_seconds": time.monotonic() - started},
            cost={
                "external_generation_gbp": "0",
                "energy_kwh": None,
                "reason": "no wall meter",
            },
            result=state,
            error=error,
            output_hashes=outputs,
        )
        write_json(out / "attempt.json", attempt)
        outputs["attempt.json"] = hash_file(out / "attempt.json")
        write_json(
            out / "manifest.json",
            {"schema_version": 1, "attempt_id": job["attempt_id"], "outputs": outputs},
        )
        try:
            q.finish(
                job,
                state,
                str(out / "manifest.json"),
                hash_file(out / "manifest.json"),
                error,
            )
        except RuntimeError:
            print(
                json.dumps(
                    {"stage": job["stage"], "state": "stale_completion_rejected"}
                ),
                flush=True,
            )
            continue
        print(
            json.dumps(
                {
                    "stage": job["stage"],
                    "state": state,
                    "seconds": round(time.monotonic() - started, 2),
                    "error": error,
                }
            ),
            flush=True,
        )
        if state == "succeeded":
            run = read_json(root / "run.json")
            run["state"] = {
                "plan": "planned",
                "images": "producing",
                "render": "producing",
                "qa": "producing",
                "review": "ready_for_review",
            }.get(job["stage"], "producing")
            write_json(root / "run.json", run)
        completed += 1
        if job["stage"] == stop_after:
            break
    return completed


def resume(config, episode):
    q = queue(config)
    invalid = False
    for row in q.status(episode):
        if row["state"] == "running":
            continue
        if row["state"] == "succeeded" and not invalid:
            try:
                stage_dir(q, episode, row["stage"])
            except (OSError, ValueError, Blocked):
                invalid = True
        if invalid or row["state"] in ["blocked", "failed", "cancelled"]:
            with q.db() as db:
                db.execute(
                    "UPDATE jobs SET state='queued',error=NULL WHERE id=?", (row["id"],)
                )
    return q.status(episode)
