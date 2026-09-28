# Preserved inference runtime

The first local trial uses existing immutable local image ID:

`sha256:1c3f366721fb9fc176e0bcb85537776e8a1b1353e26a10fa7ebec893a12719fa`

The image is the user's existing `ai-video-factory:wan`, based on NVIDIA PyTorch 25.09. No image rebuild, pip upgrade, driver change, host dependency replacement or cache pruning is needed for this trial. The Python adapter is mounted from the checkout. Runtime networking is disabled, model loading is local-files-only, and remote code execution is disabled. Downloading uses a separate CPU container before inference.

Versions measured in this image are recorded in `docs/ENVIRONMENT.md`. This local image ID is machine-specific; reproduce it on this Spark. Portability to another host requires a separately built and validated image from the baseline digest. The original unpinned Dockerfile is preserved as user work, not misrepresented as a reproducible new build.

One subprocess/container per heavy stage releases model memory on completion. Both the queue and inference process take locks. The inference lock is under the shared project model root, so a parent crash cannot permit overlapping model execution while its container still lives.
