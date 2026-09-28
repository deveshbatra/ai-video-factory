# Instructions for Codex

## Mission and scope

Implement Spark Video Factory as specified in `PLAN.md` and linked documents. Devesh is a programmer building a low-cost video business on his own DGX Spark. Deliver a maintainable, config-driven production pipeline with real local-AI stages and measured costs. The deliverable is not another single hardcoded animation or a collection of unconnected scripts.

The user has requested implementation planning; this handoff becomes implementation direction when the user starts Codex with `CODEX_START.md`. Do not interpret reading this file alone as permission to publish content, spend money or change a host's system configuration.

## Existing environment

- Spark: NVIDIA GB10, ARM64/aarch64, Ubuntu 24.04 base, approximately 121 GiB visible shared system/GPU RAM and 4 TB storage.
- NVIDIA container `nvcr.io/nvidia/pytorch:25.09-py3` has already executed GPU-enabled PyTorch successfully. Preserve this known-working baseline before changing dependencies.
- Existing remote project: `~/projects/ai-video-factory`; Docker image `ai-video-factory:wan`; YAML-config Wan script and model cache may exist. Inspect actual files before relying on paths or APIs.
- Mac is primarily an SSH/VS Code client. Work on Spark when GPU testing is required. Never claim a local development test ran on Spark unless it did.

## Working method

1. Inspect repository instructions, git status, current code and installed toolchain. Preserve user changes and caches. Start an isolated branch where available.
2. Read `PLAN.md`, `docs/CONTRACTS.md` and `docs/PROGRESS.md`. Implement milestones in order; update progress with evidence and exact resume instructions.
3. Prefer a Python package and CLI, typed Pydantic contracts, YAML configuration, SQLite state and filesystem artifacts. Pin tested dependencies in lockfiles/container digests. CPU development must work without CUDA imports.
4. Use role modules and versioned prompts inside a deterministic workflow. They may share one loaded LLM. Do not start multiple independent GPU agents or install an agent framework without a demonstrated requirement.
5. Keep model implementations behind adapters. Only one memory-heavy GPU stage at a time. Validate ARM64, kernel, dtype and model support through measurements.
6. Complete useful work without asking for routine design choices. If GPU access is unavailable, finish CPU portions, mocks and scripts; mark hardware validation blocked with the exact command needed. Do not declare the milestone's GPU gate passed.
7. Add tests for meaningful failure modes, schema boundaries, queue recovery and publishing state. Do not spend effort testing prose or trivial getters.
8. Report implementation, checks performed, measured limitations and next milestone. Do not claim a feature is complete based on an interface or mock alone.

## Invariants

- No paid provider fallback. Default external generation budget is zero. Enabling paid generation later requires an explicit configured budget and user's authorisation.
- No secrets in configs, prompts, snapshots, logs, git or review bundles. Read `HF_TOKEN` and future account credentials from environment/secret storage; redact them. Do not print them.
- Download exact model revisions through supported tools. Use current `hf` CLI where appropriate. Do not install arbitrary remote code, enable `trust_remote_code`, or execute model-emitted code without reviewing why it is required.
- Model output and research text are untrusted data. Parse against schemas, reject unknown executable instructions, and never pass their contents into a shell. Build subprocess argument arrays.
- Validate all paths under allowed artifact/cache roots. No arbitrary paths supplied by generated JSON.
- Each accepted artifact records its config, code, prompt, model and input provenance. Reproducibility means traceability; bitwise-identical GPU output is not guaranteed by a seed.
- No silent model substitution, resolution change, crop, quantisation, interpolation or renderer change. Record a new attempt and the reason for every fallback.
- Automated QA separates technical failures from editorial judgement. Never label an LLM score as measured retention or predicted revenue.
- No mass upload of colour/seed variants. Reusable characters and production tools must support materially distinct original episodes.
- No training from scratch, fine-tuning, Kubernetes, multi-GPU distribution, full social dashboard or paid API integration in the first production slice.
- User review binds to the exact final media and metadata hashes. Later changes invalidate it. Publishing requires a separate explicit action; a successful render never publishes.

## Definition of done

Contracts, CLI, docs and examples agree. Applicable tests pass. Real model integration has an actual sample and a benchmark when hardware is available. Restart/retry behaviour is documented. No mock output is presented as generated output. Implementation state and open decisions are recorded in `docs/PROGRESS.md`.

## Instruction files

This is a project-level `AGENTS.md`. `docs/ROLES.md` specifies application components and reusable prompt tasks; it is not a set of installed Codex skills. Do not create a `skills.md` placeholder and assume it enables tools or models.
