# Implementation plan

## Product outcome

An overnight job turns an approved brief into reviewable, original animated episodes using local models and reusable assets. A human chooses what to publish. Analytics then informs the next batch of creative experiments. First platform: YouTube Shorts. Other platforms initially receive exported media packages, with no automatic posting.

The pipeline follows the supplied diagram: premise bank → creative director → script/shot plan → hero images and clips → audio/edit → QA → review/publish → measured feedback. Controlled animation is an additional clip backend, not a replacement for implementing the AI stages.

## M0 — Inspect and define the executable contract

Deliver environment report, package skeleton, config loader, Pydantic schemas, source inventory and a `svf doctor` command. Use Python 3.12 as the initial target, subject to the existing NVIDIA container. Keep inference dependencies separate from the CLI/test environment. Inspect any existing Wan adapter for reuse.

Doctor reports architecture, Python/PyTorch/CUDA versions, device, FFmpeg/ffprobe, disk, shared memory and writable paths. It must distinguish unavailable metrics from zero. Record actual model revisions and propose downloads before fetching them. Create a dependency compatibility record; do not use blind `pip install --upgrade` on the host.

Acceptance: CPU config validation works; unknown keys, invalid budgets and invalid paths fail clearly. GPU smoke test performs a CUDA tensor operation in the actual target container. CPU-only machines produce a useful report with GPU tests marked unavailable.

## M1 — Complete the workflow with cheap fixtures

Implement brief → typed plan → preview renderer → audio/edit → QA → review bundle as a durable job graph. Use a fixture provider explicitly labelled `mock` to test workflow mechanics. Implement SQLite claims/leases, atomic artifacts, hashes, cancellation, bounded retries and resume. Create at least two distinct fixture stories to avoid baking one timeline into the engine.

Deliver CLI: `doctor`, `validate`, `plan`, `enqueue`, `worker`, `status`, `resume`, `review export`, `cost report`. Export a static HTML review page with local video, storyboard, alternatives, QA reasons and costs; no dashboard server yet.

Acceptance: kill a worker during rendering, restart it, and complete the episode without rerunning already-valid stages. Two workers cannot execute the same job or heavy GPU stage concurrently. A mocked paid backend cannot run under a zero budget. Fixtures pass technical checks but remain visibly marked as fixtures.

## M2 — Real local-AI vertical slice

Implement a real local text adapter, first image adapter, asset registry and a data-driven renderer. Use Qwen3-8B and SDXL as initial candidates, not permanent promises; benchmark changes must be recorded. Produce script JSON from a human brief, validate it, produce multiple hero-image candidates, select a candidate, generate a low-cost animatic and finish one 20–35 second episode with original/licensed audio and a review bundle.

The renderer must execute supported `ScenePlan` actions; it must not require changing Python for each new story. Establish a limited action vocabulary before expanding it. A manual input image is useful for debugging but does not satisfy the real image-adapter gate. A one-off manual asset selection is allowed and recorded.

In parallel within this milestone, produce a small visual audition using the same premise in detailed pixel art and stylised illustrated cutout form. Assess silhouettes, expressions, staging, camera, movement and sound. The earlier tiny robot prototype is not the target production-quality bar. Select a look based on visible samples before building an asset library.

Acceptance: a new brief follows the same pipeline without editing renderer code; local LLM and image-model manifests prove actual inference; output has coherent beginning, complication and payoff; a review bundle records compute, retries and manual minutes. Owner approves a visual direction or records specific revisions. If rejected, improve one sample rather than generating a large batch.

## M3 — Benchmark I2V and choose the production mix

Add Wan adapters using upstream-supported formats and exact revisions. Benchmark TI2V-5B first, then I2V-A14B within measured shared-memory limits. Implement capabilities, timeouts, OOM handling and one lower-cost fallback profile. Evaluate the comparison set in `docs/MODELS_AND_BENCHMARKS.md`.

Acceptance: show actual Spark results, accepted/rejected shots and reasons. Choose a primary renderer and optional I2V role based on cost per usable second and coherence. A14B may be enabled, restricted to selected shots, or rejected; none is predetermined. No assertion of commercial-model parity without a direct comparison.

## M4 — Overnight production and operator review

Add nightly budgets, model-aware scheduling, asset reuse, free-disk monitoring, run limits, graceful shutdown and morning summary. Add local review actions to accept/reject alternatives, request a targeted shot revision and approve an exact publish package. Preserve previous versions.

Acceptance: run a full configured night on Spark. Record requested and completed jobs, accepted episodes, failures, cost and human review time. On crash, jobs recover within the documented lease policy. A changed caption, music track or title invalidates prior approval. No automatic publication occurs.

## M5 — Manual release and analytics loop

Generate platform-specific packages with media, cover frame, title/description drafts, caption sidecars, rights and disclosure notes. Record manually published video IDs. Implement CSV analytics import and scheduled snapshot comparison before authenticated APIs. Follow `docs/EXPERIMENTS.md`.

Acceptance: import real channel data or clearly labelled fixtures; missing metrics stay null; engagement rates retain their denominators and collection window. Produce a weekly decision report including cost, failures and uncertain conclusions. A view count alone must never populate retention or revenue.

## M6 — Publishing integration, only when useful

Add YouTube OAuth/API adapter after verifying current endpoint capabilities, quotas and project restrictions. Default upload is private and is still an external write requiring explicit user action. Use a publication intent ledger and reconcile uncertain responses before retrying. Public release is a separate command bound to approved hashes.

Acceptance: dry-run fixture verifies every approval/identity boundary. An authorised test upload records platform ID. Timeout recovery cannot blindly duplicate an upload. Manual export remains available if API access is restricted. Other platforms are separate adapters and later tasks.

## M7 — Improve from evidence

Run the first 12–18 genuinely distinct episodes over approximately four weeks once creative quality is acceptable. Update series decisions from observed data. Only then consider larger planning models, asset LoRAs, voice localisation, longer episodes, sponsorship tooling or platform expansion.

Acceptance: a decision record explains what to continue, change or stop with evidence and uncertainty. No automatic change to production prompts based on a single outlier. Budget and operator time remain visible.

## Build boundaries and testing

Implement the minimum usable slice of each stage before optional sophistication. Put tests around schema validation, consistent story state, model capabilities, concurrent claims, crash recovery, cache invalidation, costs and approval hashes. Use deterministic fixtures for CI; actual GPU sample gates are recorded separately. No throughput targets are invented before M3/M4 measurements.

Milestone completion requires evidence in `docs/PROGRESS.md`, not only a checkbox. When a gate is blocked, record the blocker and complete independent work. Do not repeatedly ask the owner to choose routine libraries or approve reversible edits.
