# Spark inspection — 2026-09-11

Branch: `codex/m0-m2`. Repository had no commits; all supplied files were untracked. Existing files and model cache retained. No host drivers/packages modified.

- Host `spark-e487`, ARM64/aarch64, Ubuntu kernel `6.17.0-1032-nvidia`.
- Python 3.12.3. RAM 121 GiB visible, 117 GiB available at inspection. Disk 3.4 TiB available.
- NVIDIA GB10, driver 580.173.02, CUDA 13.0. NVML device memory is unsupported, not zero.
- Baseline `nvcr.io/nvidia/pytorch:25.09-py3` digest `sha256:f3b4a33fd60d5e0358287bb44d57e91eda45e8f1681fef1bfd6c969371417130`.
- Actual baseline CUDA tensor smoke test: PyTorch `2.9.0a0+50eac811a6.nv25.09`, CUDA 13.0, NVIDIA GB10, `[2.0, 2.0, 2.0, 2.0]`.
- Preserved Wan image ID `sha256:1c3f366721fb9fc176e0bcb85537776e8a1b1353e26a10fa7ebec893a12719fa`, 18.7 GB. This is the isolated inference runtime for the first trial, built on the working NVIDIA baseline.
- Its installed packages: Transformers 5.17.0, Diffusers 0.40.0, Accelerate 1.15.0, huggingface_hub 1.31.0, Pydantic 2.11.9, Pillow 11.3.0. These are observed versions, not yet proof of model compatibility.
- Existing `models/` occupied 27 GiB. Existing user HF cache approximately 356 KiB. New models go under `models/svf/`; no cache pruning.
- Host FFmpeg/ffprobe were absent. CPU rendering uses the isolated imageio-ffmpeg 0.6.0 executable. Inference image includes FFmpeg and ffprobe.
- Sandbox fails before commands with `bwrap: loopback: Failed RTM_NEWADDR`. Execution uses the reviewed escalation path. A usage-limit rejection temporarily blocked a write; user requested continuation and subsequent execution succeeded.

## Source inventory

`src/generate_wan.py` remains untouched. It loads `WanPipeline` directly from a YAML model ID, without an exact revision or attempt provenance. It is retained as an M3 integration reference; it is not used as the M2 image adapter. Existing root Dockerfile remains untouched.

Supplied normative documents read: PLAN, ARCHITECTURE, CONTRACTS, ROLES, MODELS_AND_BENCHMARKS, EXPERIMENTS, RUNBOOK, PRODUCT and PROGRESS.

## Authorised resources

Owner explicitly authorised Qwen3-8B revision `b968826d9c46dd6066d109eabc6255188de91218` and SDXL base revision `462165984030d82259a11f4367a4eed129e94a7b`, selected files only, 30 GiB downloads and three hours total GPU execution. Single GPU stage, 60-minute per-stage timeout, zero paid generation. No additional approval for this same set within those limits.

`docs/model-registry-m2.json` records selected filenames and upstream sizes. Qwen BF16; SDXL FP16 Diffusers components, no refiner, LoRA, duplicated standalone checkpoint or Wan downloads.

CPU `.venv` and `requirements-cpu.lock` are separate from inference. `configs/local.yaml` selects the authorised revisions and 576×1024 at 24 fps for the first measured episode; this is an explicit delivery profile, not a hidden downgrade from the 1080×1920 example. SDXL source images remain 1024×1024 with a recorded contain/composite operation.
