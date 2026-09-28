"""Local adapters. Imported only inside an isolated inference process."""

import json
import time
import resource
from pathlib import Path
from .storage import write_json, read_json, hash_file, canonical, digest
from .schemas import EpisodeBrief, EpisodePlan, ScriptDraft
from .planning import validate_plan, compile_script

REVISIONS = {
    "text": ("Qwen/Qwen3-8B", "b968826d9c46dd6066d109eabc6255188de91218"),
    "image": (
        "stabilityai/stable-diffusion-xl-base-1.0",
        "462165984030d82259a11f4367a4eed129e94a7b",
    ),
}


def local_path(cache, kind):
    repo, rev = REVISIONS[kind]
    p = Path(cache) / ("models--" + repo.replace("/", "--")) / "snapshots" / rev
    if not p.exists():
        raise RuntimeError("MODEL_NOT_DOWNLOADED: " + repo)
    return p


def text_generate(request, out):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    start = time.monotonic()
    path = local_path(request["cache"], "text")
    tokenizer = AutoTokenizer.from_pretrained(
        path, local_files_only=True, trust_remote_code=False
    )
    model = AutoModelForCausalLM.from_pretrained(
        path,
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    ).to("cuda")
    loaded = time.monotonic()
    brief = EpisodeBrief.model_validate(request["brief"])
    prompt = Path(request["prompt"]).read_text()
    compact = request.get("contract") == "script-v2"
    output_schema = ScriptDraft if compact else EpisodePlan
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "brief": request["brief"],
                    "schema": output_schema.model_json_schema(),
                    "required_brief_hash": digest(canonical(brief)),
                    "provider_kind": "local",
                }
            ),
        },
    ]
    errors = []
    for attempt in range(request["repairs"] + 1):
        begin = time.monotonic()
        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
            return_tensors="pt",
            return_dict=True,
        ).to("cuda")
        with torch.inference_mode():
            result = model.generate(
                **inputs,
                max_new_tokens=request.get("generation", {}).get("max_new_tokens", 5000)
                if compact
                else 12000,
                do_sample=False,
            )
        torch.cuda.synchronize()
        raw = tokenizer.decode(
            result[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )
        write_json(
            out / f"text-attempt-{attempt + 1}.json",
            {
                "provider_kind": "local",
                "model": REVISIONS["text"],
                "raw": raw,
                "generation_seconds": time.monotonic() - begin,
                "load_seconds": loaded - start,
                "prompt_hash": digest(canonical(messages)),
                "seed": request["seed"],
            },
        )
        try:
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = output_schema.model_validate_json(stripped)
            plan = compile_script(parsed, brief) if compact else parsed
            if compact:
                write_json(out / "script.json", parsed)
            validate_plan(plan, brief)
            write_json(out / "plan.json", plan)
            break
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": "Repair the entire JSON. Validation error: "
                        + str(exc)[:4000],
                    },
                ]
            )
    else:
        raise RuntimeError("SCHEMA_REPAIR_EXHAUSTED: " + errors[-1])
    write_json(
        out / "inference.json",
        {
            "provider_kind": "local",
            "model": REVISIONS["text"],
            "dtype": "bfloat16",
            "attention": "sdpa",
            "contract": request.get("contract", "episode-plan-v1"),
            "load_seconds": loaded - start,
            "total_seconds": time.monotonic() - start,
            "attempts": attempt + 1,
            "cuda_peak_bytes": torch.cuda.max_memory_allocated(),
            "rss_peak_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "errors": errors,
            "output_hash": hash_file(out / "plan.json"),
        },
    )


def image_generate(request, out):
    import torch
    from diffusers import StableDiffusionXLPipeline

    start = time.monotonic()
    pipe = StableDiffusionXLPipeline.from_pretrained(
        local_path(request["cache"], "image"),
        local_files_only=True,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    ).to("cuda")
    loaded = time.monotonic()
    records = []
    settings = request.get(
        "generation",
        {"height": 1024, "width": 1024, "steps": 30, "guidance_scale": 6.5},
    )
    for i, item in enumerate(request["images"]):
        begin = time.monotonic()
        seed = request["seed"] + i
        image = pipe(
            prompt=item["prompt"],
            negative_prompt=item.get(
                "negative_prompt",
                "text, watermark, logo, blurry, malformed hands, duplicate limbs, photorealistic",
            ),
            height=settings["height"],
            width=settings["width"],
            num_inference_steps=settings["steps"],
            guidance_scale=settings["guidance_scale"],
            generator=torch.Generator("cuda").manual_seed(seed),
        ).images[0]
        torch.cuda.synchronize()
        file = out / (item["id"] + ".png")
        image.save(file)
        record = {
            "id": item["id"],
            "provider_kind": "local",
            "model": REVISIONS["image"],
            "seed": seed,
            "prompt": item["prompt"],
            "settings": {
                "height": settings["height"],
                "width": settings["width"],
                "steps": settings["steps"],
                "guidance": settings["guidance_scale"],
                "dtype": "float16",
                "variant": "fp16",
            },
            "sampling_decode_seconds": time.monotonic() - begin,
            "sha256": hash_file(file),
        }
        records.append(record)
        write_json(out / (item["id"] + ".json"), record)
    write_json(
        out / "inference.json",
        {
            "provider_kind": "local",
            "model": REVISIONS["image"],
            "load_seconds": loaded - start,
            "total_seconds": time.monotonic() - start,
            "cuda_peak_bytes": torch.cuda.max_memory_allocated(),
            "rss_peak_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "candidates": records,
        },
    )


def main():
    import sys

    request = read_json(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    import fcntl

    lock_path = (
        Path(request["gpu_lock"])
        if "gpu_lock" in request
        else Path(request["cache"]).parent / "svf-device.lock"
    )
    with open(lock_path, "a") as device_lock:
        fcntl.flock(device_lock, fcntl.LOCK_EX)
        {"text": text_generate, "image": image_generate}[request["kind"]](request, out)


if __name__ == "__main__":
    main()
