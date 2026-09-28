"""Preview or explicitly download the pinned official Wan2.2 A14B checkpoint."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "sha256:1c3f366721fb9fc176e0bcb85537776e8a1b1353e26a10fa7ebec893a12719fa"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download", action="store_true", help="Fetch the displayed download set"
    )
    args = parser.parse_args()
    manifest = json.loads((ROOT / "docs/wan22-download.json").read_text())
    size = sum(f["bytes"] for f in manifest["files"])
    if (
        size != manifest["download_bytes"]
        or size > manifest["download_budget_gib"] * 1024**3
    ):
        raise SystemExit("Download manifest exceeds its configured budget")
    cache = (ROOT / manifest["cache"]).resolve()
    if not cache.is_relative_to(ROOT / "models"):
        raise SystemExit("Cache must remain under the project's models directory")
    print(
        f"Model: {manifest['repo']}\nRevision: {manifest['revision']}\n"
        f"Selected files: {len(manifest['files'])}\nDownload: {size / 1024**3:.2f} GiB\n"
        f"Cache: {cache}\nNo GPU execution or host package changes.",
        flush=True,
    )
    if not args.download:
        print(
            "Preview only. Add --download to start; rerun the same command to resume."
        )
        return
    required = size + manifest["free_disk_reserve_gib"] * 1024**3
    if shutil.disk_usage(ROOT).free < required:
        raise SystemExit(
            "Insufficient disk: require full checkpoint size plus 30 GiB reserve"
        )
    cache.mkdir(parents=True, exist_ok=True)
    import os

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--init",
            "--pull",
            "never",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-e",
            "HF_HOME=/cache",
            "-e",
            "HF_HUB_DISABLE_IMPLICIT_TOKEN=1",
            "-e",
            "HF_XET_CHUNK_CACHE_SIZE_BYTES=0",
            "-v",
            f"{cache}:/cache",
            "--entrypoint",
            "hf",
            IMAGE,
            "download",
            manifest["repo"],
            "--revision",
            manifest["revision"],
            "--cache-dir",
            "/cache",
            "--max-workers",
            "2",
            *[arg for f in manifest["files"] for arg in ("--include", f["path"])],
        ],
        check=True,
    )
    snapshot = (
        cache
        / ("models--" + manifest["repo"].replace("/", "--"))
        / "snapshots"
        / manifest["revision"]
    )
    for entry in manifest["files"]:
        path = snapshot / entry["path"]
        if not path.is_file() or path.stat().st_size != entry["bytes"]:
            raise SystemExit(
                f"Missing or incomplete file: {entry['path']}; rerun to resume"
            )
    print(f"Download complete; selected file sizes verified: {snapshot}")
    print("Inference has not run. The existing small-Wan launcher is unchanged.")


if __name__ == "__main__":
    main()
