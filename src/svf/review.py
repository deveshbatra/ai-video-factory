import html
import shutil
import json
from pathlib import Path
from .storage import now, hash_file, write_json, read_json
from .schemas import Asset, PublishPackage
from .workflow import queue, root_for, stage_dir, latest_images


def costs(config, episode):
    q = queue(config)
    with q.db() as db:
        rows = [
            dict(r)
            for r in db.execute(
                "SELECT a.* FROM attempts a JOIN jobs j ON a.job=j.id WHERE j.episode=? ORDER BY started",
                (episode,),
            )
        ]
    root = root_for(config, episode)
    generation_records = list((root / "attempts").glob("plan/*/text-attempt-*.json"))
    image_records = list((root / "attempts").glob("images*/*/inference.json"))
    image_count = sum(len(read_json(p).get("candidates", [])) for p in image_records)
    interrupted = sum(
        r["result"] in ["cancelled", "interrupted"]
        for r in rows
        if r["job"].endswith(":plan")
    )
    return {
        "attempts": len(rows),
        "completed_text_responses": len(generation_records),
        "generated_image_candidates": image_count,
        "interrupted_text_attempts": interrupted,
        "stages": rows,
        "external_generation_gbp": "0",
        "energy_kwh": None,
        "electricity_gbp": None,
        "unknown_reason": "no wall meter or tariff supplied",
        "manual_minutes": None,
        "accepted_usable_seconds": None,
        "cost_per_usable_second": None,
    }


def export(config, episode, out):
    q = queue(config)
    root = root_for(config, episode)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rendered = stage_dir(q, episode, "render")
    planned = stage_dir(q, episode, "plan")
    qa = stage_dir(q, episode, "qa")
    for name in ["final.mp4", "cover.png", "audio.wav", "audio.json"]:
        shutil.copy2(rendered / name, out / name)
    shutil.copytree(rendered / "storyboard", out / "storyboard", dirs_exist_ok=True)
    for name in ["brief.json", "resolved-config.json", "run.json"]:
        shutil.copy2(root / name, out / name)
    shutil.copy2(planned / "plan.json", out / "plan.json")
    shutil.copy2(qa / "qa.json", out / "qa.json")
    images = latest_images(q, episode)
    shutil.copytree(images, out / "alternatives", dirs_exist_ok=True)
    history = out / "attempt-history"
    history.mkdir(exist_ok=True)
    for path in (root / "attempts").glob("*/*/attempt.json"):
        shutil.copy2(path, history / (path.parent.name + ".json"))
    for path in (root / "attempts").glob("plan/*/text-attempt-*.json"):
        shutil.copy2(path, history / (path.parent.name + "-" + path.name))
    for name in ["selection.json", "storyboard-approval.json"]:
        if (root / name).exists():
            shutil.copy2(root / name, out / name)
    write_json(out / "costs.json", costs(config, episode))
    package = PublishPackage(
        media_hash=hash_file(out / "final.mp4"),
        caption_hash=None,
        cover_hash=hash_file(out / "cover.png"),
        platform="youtube",
        metadata={
            "title": read_json(root / "brief.json")["viewer_question"],
            "description": read_json(root / "brief.json")["payoff"],
        },
        audience=None,
        disclosure=None,
        rights=[
            "original procedural audio CC0",
            "SDXL OpenRAIL++ artwork"
            if read_json(root / "run.json")["provider_kind"] == "local"
            else "MOCK fixture",
        ],
    )
    write_json(out / "publish-package/package.json", package)
    tag = (
        "MOCK FIXTURE — NOT AI GENERATED"
        if read_json(root / "run.json")["provider_kind"] == "mock"
        else "LOCAL AI — HUMAN REVIEW REQUIRED"
    )
    esc = html.escape
    cards = "".join(
        f'<figure><img src="alternatives/{esc(p.name)}"><figcaption>{esc(p.stem)}</figcaption></figure>'
        for p in sorted((out / "alternatives").glob("*.png"))
    )
    shots = "".join(
        f'<img src="storyboard/{esc(p.name)}">'
        for p in sorted((out / "storyboard").glob("*.png"))
    )
    (out / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><title>{esc(episode)}</title><style>body{{background:#15212b;color:#eee;font:18px system-ui;max-width:1100px;margin:30px auto}}video{{max-height:75vh;max-width:100%}}img{{width:220px}}figure{{display:inline-block}}pre{{white-space:pre-wrap}}</style><h1>{esc(episode)}</h1><p>{tag}</p><video controls src="final.mp4"></video><h2>Storyboard</h2>{shots}<h2>Alternatives</h2>{cards}<h2>QA — editorial assessment pending</h2><pre>{esc(json.dumps(read_json(out / "qa.json"), indent=2))}</pre><h2>Costs and attempts</h2><pre>{esc(json.dumps(costs(config, episode), indent=2))}</pre><p>Nothing has been approved or published.</p>'
    )
    write_json(
        out / "bundle-manifest.json",
        {
            "files": {
                str(p.relative_to(out)): hash_file(p)
                for p in out.rglob("*")
                if p.is_file()
            }
        },
    )
    return out


def select(config, episode, style, reviewer):
    if style not in ["detailed_pixel_art", "illustrated_cutout"]:
        raise ValueError("unsupported style")
    q = queue(config)
    root = root_for(config, episode)
    images = latest_images(q, episode)
    files = [images / (style + "-" + part + ".png") for part in ["hero", "pip", "moss"]]
    hashes = {p.name: hash_file(p) for p in files}
    write_json(
        root / "selection.json",
        {
            "style": style,
            "reviewer": reviewer,
            "timestamp": now(),
            "hashes": hashes,
            "manual_minutes": None,
        },
    )
    (root / "assets").mkdir(exist_ok=True)
    for name in ["pip", "moss"]:
        source = images / (style + "-" + name + ".png")
        path = root / "assets" / (style + "-" + name + ".png")
        from .audition import cutout

        cutout(source, path)
        curation = read_json(path.with_suffix(".json"))
        asset = Asset(
            id=style + "-" + name,
            sha256=hash_file(path),
            file_ref=str(path.relative_to(root)),
            type="rgba_cutout",
            character_ids=[name],
            generation_manifest={
                "source_sha256": hash_file(source),
                "curation": curation,
            },
            licence="OpenRAIL++",
            attribution="SDXL base 1.0 local inference",
            approval_status="approved",
        )
        write_json(path.with_suffix(".json"), asset)
        from .assets import AssetRegistry
        from .config import resolve

        AssetRegistry(
            resolve(config.project.asset_root), resolve(config.project.database_path)
        ).register(asset, path)
