"""Download only the owner-authorised M2 files with the supported hf CLI."""

import json, subprocess, urllib.request, fnmatch, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = [
    (
        "Qwen/Qwen3-8B",
        "b968826d9c46dd6066d109eabc6255188de91218",
        ["*.json", "*.txt", "*.safetensors"],
        "Apache-2.0",
        "bfloat16",
    ),
    (
        "stabilityai/stable-diffusion-xl-base-1.0",
        "462165984030d82259a11f4367a4eed129e94a7b",
        [
            "model_index.json",
            "scheduler/*.json",
            "tokenizer/*",
            "tokenizer_2/*",
            "text_encoder/config.json",
            "text_encoder/model.fp16.safetensors",
            "text_encoder_2/config.json",
            "text_encoder_2/model.fp16.safetensors",
            "unet/config.json",
            "unet/diffusion_pytorch_model.fp16.safetensors",
            "vae/config.json",
            "vae/diffusion_pytorch_model.fp16.safetensors",
        ],
        "OpenRAIL++",
        "float16",
    ),
]
entries = []
for repo, revision, patterns, licence, dtype in MODELS:
    data = json.load(
        urllib.request.urlopen(
            f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true"
        )
    )
    files = [
        {"path": s["rfilename"], "bytes": s["size"], "lfs": s.get("lfs")}
        for s in data["siblings"]
        if any(fnmatch.fnmatch(s["rfilename"], p) for p in patterns)
    ]
    entries.append(
        dict(
            repo=repo,
            revision=revision,
            files=files,
            download_bytes=sum(f["bytes"] for f in files),
            licence=licence,
            dtype=dtype,
            cache="models/svf",
            runtime="ai-video-factory:wan@sha256:pending-local-inspect",
            verified="2026-09-11",
            benchmark_status="not_run",
            usage_review="Qwen Apache-2.0; SDXL OpenRAIL++ restrictions apply; original non-personal fictional artwork only",
            patterns=patterns,
        )
    )
assert sum(e["download_bytes"] for e in entries) < 30 * 1024**3
assert shutil.disk_usage(ROOT).free > 100 * 1024**3
registry = ROOT / "docs/model-registry-m2.json"
if not registry.exists():
    registry.write_text(json.dumps(entries, indent=2))
cache = ROOT / "models/svf"
cache.mkdir(parents=True, exist_ok=True)
for e in entries:
    args = [
        "hf",
        "download",
        e["repo"],
        "--revision",
        e["revision"],
        "--cache-dir",
        str(cache),
        "--max-workers",
        "3",
        *[arg for pattern in e["patterns"] for arg in ["--include", pattern]],
    ]
    subprocess.run(args, check=True)
