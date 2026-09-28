import argparse
from pathlib import Path

import torch
import yaml
from diffusers import WanPipeline
from diffusers.utils import export_to_video


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    model = config["model"]
    generation = config["generation"]
    output_path = Path(config["output"]["path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dtype = getattr(torch, model["dtype"])
    torch.backends.cuda.matmul.allow_tf32 = True

    pipe = WanPipeline.from_pretrained(
        model["id"],
        torch_dtype=dtype,
    ).to("cuda")

    generator = torch.Generator(device="cuda").manual_seed(generation["seed"])

    frames = pipe(
        prompt=generation["prompt"],
        negative_prompt=generation["negative_prompt"],
        num_frames=generation["frames"],
        height=generation["height"],
        width=generation["width"],
        num_inference_steps=generation["steps"],
        guidance_scale=generation["guidance_scale"],
        generator=generator,
    ).frames[0]

    export_to_video(frames, str(output_path), fps=generation["fps"])
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()