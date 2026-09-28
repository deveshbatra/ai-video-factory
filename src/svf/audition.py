"""Draft both looks without recording owner approval."""

from pathlib import Path
from PIL import Image
from .rendering import render
from .storage import write_json, hash_file, read_json


def cutout(source, dest):
    from collections import deque
    import yaml
    from .config import ROOT

    settings = yaml.safe_load((ROOT / "configs/asset-curation.yaml").read_text())[
        "assets"
    ].get(source.stem, {"crop": [0, 0, 1, 1], "review_note": "uncurated"})
    original = Image.open(source).convert("RGB")
    box = settings["crop"]
    if (
        len(box) != 4
        or not all(0 <= v <= 1 for v in box)
        or box[0] >= box[2]
        or box[1] >= box[3]
    ):
        raise ValueError("invalid normalized crop")
    im = original.crop(
        (
            int(box[0] * original.width),
            int(box[1] * original.height),
            int(box[2] * original.width),
            int(box[3] * original.height),
        )
    ).convert("RGBA")
    w, h = im.size
    pixels = im.load()
    seen = bytearray(w * h)
    pending = deque()
    for x in range(w):
        pending.extend([(x, 0), (x, h - 1)])
    for y in range(h):
        pending.extend([(0, y), (w - 1, y)])
    while pending:
        x, y = pending.popleft()
        index = y * w + x
        if seen[index]:
            continue
        seen[index] = 1
        r, g, b, a = pixels[x, y]
        if max(r, g, b) - min(r, g, b) > 45 or max(r, g, b) < 85:
            continue
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                pending.append((nx, ny))
    # Keep the foreground connected to the central subject, removing sheet fragments.
    foreground = bytearray(w * h)
    seed = settings.get("seed", [0.5, 0.5])
    pending = deque([(int(w * seed[0]), int(h * seed[1]))])
    while pending:
        x, y = pending.popleft()
        index = y * w + x
        if foreground[index] or pixels[x, y][3] == 0:
            continue
        foreground[index] = 1
        for nx, ny in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if 0 <= nx < w and 0 <= ny < h and not foreground[ny * w + nx]:
                pending.append((nx, ny))
    if settings.get("keep_all_foreground"):
        foreground = bytearray(
            1 if pixels[x, y][3] else 0 for y in range(h) for x in range(w)
        )
    if sum(foreground) < w * h * 0.02:
        raise ValueError("foreground extraction failed; requires curated mask")
    for y in range(h):
        for x in range(w):
            if not foreground[y * w + x]:
                r, g, b, a = pixels[x, y]
                pixels[x, y] = (r, g, b, 0)
    im.save(dest)
    write_json(
        dest.with_suffix(".json"),
        {
            "source_sha256": hash_file(source),
            "output_sha256": hash_file(dest),
            "operation": "explicit normalized crop, edge-connected neutral-background removal, central connected subject",
            "curation": settings,
            "approval": "pending",
        },
    )


def audition(plan, images, delivery, heartbeat=lambda: None, config=None, episode=None):
    import time
    import uuid
    import json
    import html
    from .qa import inspect
    from .storage import canonical, digest, now

    images = Path(images)
    version = str(uuid.uuid4())
    version_root = images / "versions" / version
    version_root.mkdir(parents=True)
    reports = []
    for style in ["detailed_pixel_art", "illustrated_cutout"]:
        started = time.monotonic()
        directory = version_root / style
        directory.mkdir()
        assets = {"background": images / (style + "-hero.png")}
        for name in ["pip", "moss"]:
            dest = directory / (name + ".png")
            cutout(images / (style + "-" + name + ".png"), dest)
            assets[name] = dest
        preview = directory / "preview"
        render(plan, preview, delivery, assets, heartbeat)
        qa = inspect(
            preview / "final.mp4", plan, delivery.width, delivery.height, delivery.fps
        )
        write_json(preview / "qa.json", qa)
        elapsed = time.monotonic() - started
        record = {
            "id": str(uuid.uuid4()),
            "provider_kind": "local",
            "stage": "audition-" + style,
            "timestamp": now(),
            "wall_seconds": elapsed,
            "plan_hash": digest(canonical(plan)),
            "final_hash": hash_file(preview / "final.mp4"),
            "qa": qa.model_dump(mode="json"),
            "approval": "pending",
            "development_previews_before_this_version": "not fully timed; see progress notes",
        }
        write_json(directory / "attempt.json", record)
        reports.append(record)
        write_json(
            directory / "manifest.json",
            {
                "attempt_id": record["id"],
                "outputs": {
                    str(p.relative_to(directory)): hash_file(p)
                    for p in directory.rglob("*")
                    if p.is_file()
                },
            },
        )
        if config and episode:
            from .workflow import queue

            q = queue(config)
            job_id = episode + ":audition-" + style
            with q.db() as db:
                db.execute(
                    "INSERT OR IGNORE INTO jobs(id,episode,stage,ordinal,state) VALUES(?,?,?,99,'succeeded')",
                    (job_id, episode, "audition-" + style),
                )
                db.execute(
                    "UPDATE jobs SET attempts=attempts+1,artifact=?,hash=? WHERE id=?",
                    (
                        str(directory / "manifest.json"),
                        hash_file(directory / "manifest.json"),
                        job_id,
                    ),
                )
                db.execute(
                    "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?)",
                    (
                        record["id"],
                        job_id,
                        0,
                        time.time() - elapsed,
                        time.time(),
                        "succeeded",
                        elapsed,
                        None,
                    ),
                )
    write_json(images / "plan.json", plan)
    write_json(images / "audition-measurements.json", reports)
    if config and episode:
        from .review import costs

        write_json(images / "costs.json", costs(config, episode))
    (images / "audition.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Visual direction audition</title><style>body{background:#15212b;color:white;font:18px system-ui;max-width:1100px;margin:30px auto}video{max-height:80vh;max-width:100%}pre{white-space:pre-wrap}</style><h1>26-second local-AI draft — owner review required</h1><p>Real Qwen script plus explicitly recorded editorial action revisions; real SDXL artwork. Original procedural sound. Neither style is approved. Pixel candidate fails robot identity; illustrated amber feet remain clipped in the source. Watch with sound and muted.</p>'
        + "".join(
            f'<h2>{style}</h2><video controls src="versions/{version}/{style}/preview/final.mp4"></video><p><a href="versions/{version}/{style}/preview/qa.json">Technical QA</a></p>'
            for style in ["detailed_pixel_art", "illustrated_cutout"]
        )
        + "<h2>Measured attempts and costs</h2><pre>"
        + html.escape(
            json.dumps(
                read_json(images / "costs.json")
                if (images / "costs.json").exists()
                else reports,
                indent=2,
            )
        )
        + "</pre>"
    )
    write_json(images / "latest.json", {"version": version, "reports": reports})
