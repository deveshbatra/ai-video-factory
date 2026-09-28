"""Offline, config-driven Wan video generation using the preserved checkpoint."""

import argparse
import fcntl
import json
import resource
import shutil
import signal
import time
import uuid
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator
from .config import ROOT, resolve
from .schemas import Record
from .storage import now, write_json, hash_file


class Model(Record):
    id: Literal["Wan-AI/Wan2.1-T2V-1.3B-Diffusers"]
    revision: Literal["0fad780a534b6463e45facd96134c9f345acfa5b"]
    cache: str
    dtype: Literal["bfloat16"] = "bfloat16"
    vae_dtype: Literal["float32"] = "float32"


class Generation(Record):
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    seed: int = Field(ge=0)
    width: int = Field(ge=16)
    height: int = Field(ge=16)
    frames: int = Field(ge=5)
    fps: int = Field(gt=0)
    steps: int = Field(gt=0, le=100)
    guidance_scale: float = Field(ge=0)

    @model_validator(mode="after")
    def shape(self):
        if self.width % 16 or self.height % 16:
            raise ValueError("Wan width and height must be divisible by 16")
        if (self.frames - 1) % 4:
            raise ValueError(
                "This cached Wan VAE requires frames = 4n+1; use 81 for this profile"
            )
        return self


class Output(Record):
    directory: str


class Runtime(Record):
    timeout_seconds: int = Field(default=3600, ge=30, le=10800)
    min_free_disk_gib: float = Field(default=20, ge=0)
    min_available_ram_gib: float = Field(default=20, ge=0)


class WanConfig(Record):
    model: Model
    generation: Generation
    output: Output
    runtime: Runtime = Field(default_factory=Runtime)

    @model_validator(mode="after")
    def paths(self):
        resolve(self.model.cache)
        resolve(self.output.directory)
        return self


def snapshot(config):
    path = (
        resolve(config.model.cache)
        / ("models--" + config.model.id.replace("/", "--"))
        / "snapshots"
        / config.model.revision
    )
    if not path.is_dir():
        raise ValueError(
            "Required Wan revision is not cached; automatic downloads are disabled"
        )
    for relative in [
        "model_index.json",
        "transformer/config.json",
        "vae/config.json",
        "text_encoder/config.json",
        "tokenizer/tokenizer_config.json",
    ]:
        if not (path / relative).is_file():
            raise ValueError("Incomplete checkpoint: " + relative)
    return path


def generate(config):
    path = snapshot(config)
    if shutil.disk_usage(ROOT).free < config.runtime.min_free_disk_gib * 1024**3:
        raise RuntimeError("Insufficient free disk")
    available = (
        int(
            next(
                line.split()[1]
                for line in Path("/proc/meminfo").read_text().splitlines()
                if line.startswith("MemAvailable:")
            )
        )
        * 1024
    )
    if available < config.runtime.min_available_ram_gib * 1024**3:
        raise RuntimeError("Insufficient available system RAM")
    lock_path = ROOT / "state/global-device.lock"
    lock_path.parent.mkdir(exist_ok=True)
    with lock_path.open("a") as lock:
        print("Waiting for exclusive GPU access...", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        attempt = str(uuid.uuid4())
        out = resolve(config.output.directory) / attempt
        out.mkdir(parents=True)
        write_json(out / "config.json", config)
        record = {
            "schema_version": 1,
            "attempt_id": attempt,
            "provider_kind": "local",
            "model": config.model.model_dump(mode="json"),
            "started_at": now(),
            "code_sha256": hash_file(Path(__file__)),
            "config_sha256": hash_file(out / "config.json"),
            "external_generation_spend": 0,
            "energy_kwh": None,
            "timings": {},
            "result": "running",
        }
        write_json(out / "manifest.json", record)

        def timeout(_signal, _frame):
            raise TimeoutError("Configured Wan inference timeout exceeded")

        signal.signal(signal.SIGALRM, timeout)
        signal.signal(signal.SIGTERM, timeout)
        signal.alarm(config.runtime.timeout_seconds)
        start = time.monotonic()
        try:
            import torch
            from diffusers import AutoencoderKLWan, WanPipeline
            from diffusers.utils import export_to_video

            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is unavailable in the inference container")
            print(f"Loading {config.model.id} at {config.model.revision}", flush=True)
            vae = AutoencoderKLWan.from_pretrained(
                path, subfolder="vae", torch_dtype=torch.float32, local_files_only=True
            )
            pipe = WanPipeline.from_pretrained(
                path, vae=vae, torch_dtype=torch.bfloat16, local_files_only=True
            ).to("cuda")
            torch.cuda.synchronize()
            record["timings"]["load_seconds"] = time.monotonic() - start
            g = config.generation
            generated_at = time.monotonic()
            frames = pipe(
                prompt=g.prompt,
                negative_prompt=g.negative_prompt,
                height=g.height,
                width=g.width,
                num_frames=g.frames,
                num_inference_steps=g.steps,
                guidance_scale=g.guidance_scale,
                generator=torch.Generator(device="cuda").manual_seed(g.seed),
            ).frames[0]
            torch.cuda.synchronize()
            record["timings"]["generation_and_decode_seconds"] = (
                time.monotonic() - generated_at
            )
            if len(frames) != g.frames:
                raise RuntimeError(
                    f"Unexpected frame count: {len(frames)} != {g.frames}"
                )
            exported_at = time.monotonic()
            destination = out / "video.mp4"
            export_to_video(frames, str(destination), fps=g.fps, macro_block_size=1)
            record["timings"]["export_seconds"] = time.monotonic() - exported_at
            record.update(
                result="succeeded",
                output_sha256=hash_file(destination),
                output_file="video.mp4",
                delivered_frames=len(frames),
                fps=g.fps,
                duration_seconds=len(frames) / g.fps,
                width=g.width,
                height=g.height,
                cuda_peak_bytes=torch.cuda.max_memory_allocated(),
                rss_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                torch_version=torch.__version__,
                cuda_version=torch.version.cuda,
            )
            print(
                f"\nGenerated video: {destination.relative_to(ROOT)}\nManifest: {(out / 'manifest.json').relative_to(ROOT)}",
                flush=True,
            )
        except BaseException as error:
            record.update(result="failed", error=str(error))
            raise
        finally:
            signal.alarm(0)
            record["timings"]["total_seconds"] = time.monotonic() - start
            record["finished_at"] = now()
            write_json(out / "manifest.json", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config_path = resolve(args.config)
    config = WanConfig.model_validate(yaml.safe_load(config_path.read_text()))
    cached = snapshot(config)
    if args.check:
        print(
            json.dumps(
                {
                    "valid": True,
                    "model": config.model.id,
                    "revision": config.model.revision,
                    "cached_snapshot": str(cached),
                    "clip_seconds": config.generation.frames / config.generation.fps,
                    "output_directory": config.output.directory,
                    "downloads": "disabled",
                },
                indent=2,
            )
        )
    else:
        generate(config)


if __name__ == "__main__":
    main()
