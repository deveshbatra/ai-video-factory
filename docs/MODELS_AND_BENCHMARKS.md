# Model selection and Spark benchmark protocol

## Initial candidates, not a leaderboard

| Stage | First candidate | Reason to test | Fallback / decision |
| --- | --- | --- | --- |
| Structured planning | `Qwen/Qwen3-8B` | Local general-purpose planner candidate with a modest initial footprint | A larger locally supported model only if plan quality justifies it |
| Stills/assets | `stabilityai/stable-diffusion-xl-base-1.0` | Established image-generation baseline for an isolated adapter | Replace after a fixed-brief art trial if consistency/quality is inadequate |
| Precise animation | Custom scene interpreter + FFmpeg | Control of timing, object identity and interactions | Improve assets/poses before abandoning deterministic motion |
| I2V efficiency trial | `Wan-AI/Wan2.2-TI2V-5B` | Smaller upstream video option | Retain only if output is useful for this series |
| I2V quality trial | `Wan-AI/Wan2.2-I2V-A14B` | Larger upstream image-conditioned option | Selected shots only, or disable after measured rejection |
| Audio | Original cues + recorded licensed assets | No voice model needed for wordless stories | Add a separately benchmarked local TTS adapter when language tests require it |

Qwen and SDXL are provisional engineering choices, not claims of being the newest or highest-quality models. Read exact revisions, terms and current runtime instructions before implementing. [Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B), [SDXL model card](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)

Upstream Wan documents I2V-A14B's 480P/720P modes and an example using at least 80 GB GPU memory. TI2V-5B has different size conventions and a documented 24 GB example. These are upstream examples, not verified Spark performance or guarantees that shared RAM behaves like discrete VRAM. Resolve the exact checkpoint format for the chosen runtime; an upstream repository and a Diffusers-formatted repository are not interchangeable by assumption. [Wan2.2 official repository](https://github.com/Wan-Video/Wan2.2)

## Runtime choices

Prefer direct Python adapters for programmatic control. Start with the tested NVIDIA PyTorch container and compatible Transformers/Diffusers versions. Pin resolved versions after a smoke test. If native upstream inference is more reliable for a model, wrap it through a documented subprocess interface; preserve the same request/result contract.

ComfyUI is an optional backend if it solves a demonstrated model compatibility problem. It must use a versioned workflow and a programmatic adapter; it must not make interactive clicking a production dependency. Avoid an unreviewed collection of custom nodes.

Record model ID and commit, runtime/image digest, precision, quantisation method, attention implementation, offload settings, VAE options, dimensions, frames, FPS and all generation controls. Do not assume FlashAttention wheels, FP8 or bitsandbytes work on this ARM64/GB10 combination. Use supported attention first and optimise only a measured bottleneck.

## Memory and failure planning

Shared memory means CPU offloading can reduce device allocation pressure without removing the underlying physical-memory requirement. Keep the OS and decoder headroom. Initial proposed admission limits are in config and must be tuned from actual measurements; they are not hardware guarantees. Check peak use during VAE decoding and export as well as denoising.

Run only one heavy model stage. Distinguish load time, generation time and decode/export time. Count failed and rejected attempts. Downloads are a separately recorded setup cost and do not inflate every episode's warm runtime.

## Fixed comparison set

Use three original shot briefs: (A) a single character notices an object, (B) two characters pass a prop, (C) a prop triggers a visible bridge/door change. Hold art references and intended action constant. Create one controlled-animation reference for each; run two seeds per brief for each video candidate. Initial comparison therefore has 3 controlled references + 6 smaller-model clips + 6 larger-model clips = 15 outputs, subject to budget admission. Start with one smoke-test clip before expanding.

Choose approximately five seconds per trial, mapped to each backend's supported frame count and FPS. Preserve source and delivered durations. Compare the same aspect ratio and fair delivery size; document when native sizes differ. Never improve one entry with unreported interpolation or post-processing.

Human review labels each clip usable / repairable / unusable, with reasons for identity, motion, action correctness, aesthetic appeal and consistency. Review complete playback, not just a contact sheet. Blind model labels where practical. Tiny samples establish a working hypothesis, not a statistical ranking of models.

Record per attempt:

- Cold/warm load, sampling, decoding and export seconds.
- Available system memory, process RSS and framework allocation where available.
- Crash, OOM, timeout and artifact-validation outcomes.
- Actual electrical energy from a wall meter when available; otherwise null or an explicitly labelled estimate with assumptions. GPU-reported watts are not whole-machine wall power.
- Manual cleanup/selection minutes, usable delivered seconds, model terms/revision and output hashes.

`cost per usable second = total comparison production cost / total accepted usable seconds`.

Also record wall-clock throughput. A lower cash cost can still be a poor choice if it occupies the machine all night for one rejected shot. Estimate overnight capacity from the measured full mix of loads, generation, editing and failures, not denoising speed alone.

## Selection rule

For each shot class, choose the cheapest measured route that meets the owner's visual and coherence bar. The bar is evaluated before cost. If neither local video model meets it, improve art/staging or use controlled animation; record the failure honestly. Do not reduce the goal to producing lots of technically valid files.

The user's reference to Seedance is a quality aspiration. No exact version, API price, benchmark parity or comparable performance is assumed here. A later cloud comparison must verify the product and price at the time, use a user-approved budget, and include rejected outputs and editing time.

## Model registry gate

Before first download/inference, store an immutable registry entry: exact model revision, runtime, local cache, total download estimate, licence/usage review, selected profile, supported capabilities, verification date and benchmark status. Recheck terms for derived checkpoints, LoRAs, voice packs and other assets independently. Do not assume the base model's licence covers every add-on.
