FROM nvcr.io/nvidia/pytorch:25.09-py3

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir \
    "diffusers>=0.35.0" \
    "transformers>=4.51.0" \
    accelerate \
    sentencepiece \
    safetensors \
    imageio[ffmpeg] \
    pyyaml \
    huggingface_hub

WORKDIR /workspace
ENV HF_HOME=/models/huggingface