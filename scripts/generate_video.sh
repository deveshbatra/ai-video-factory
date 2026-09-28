#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
config_path="${1:-configs/wan-video.yaml}"
if [[ $# -gt 0 ]]; then shift; fi
container_name="svf-wan-${UID}-$$"
image_id="sha256:1c3f366721fb9fc176e0bcb85537776e8a1b1353e26a10fa7ebec893a12719fa"
cleanup() {
  docker stop --time 5 "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
mkdir -p state outputs/wan
# Offline execution uses the existing image and cached checkpoint. No installs.
docker run --rm --init --name "$container_name" --gpus all \
  --network none --shm-size 8g --user "$(id -u):$(id -g)" \
  --entrypoint python \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/workspace/src \
  -v "$project_root:/workspace" -w /workspace \
  "$image_id" -m svf.wan --config "$config_path" "$@"
