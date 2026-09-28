# Implementation progress

## Status at handoff

Planning documents and example configs created. No Spark Video Factory application has been implemented or installed by this handoff. The separate earlier pixel-animation sample and user's existing Wan pipeline are references, not completed milestones below.

| Milestone | Status | Evidence |
| --- | --- | --- |
| M0 environment/contracts | Not started | User previously demonstrated NVIDIA PyTorch GPU access; inspect current environment |
| M1 durable fixture workflow | Not started | None |
| M2 real local-AI episode | Not started | None |
| M3 I2V comparison | Not started | None |
| M4 overnight operation | Not started | None |
| M5 release/analytics | Not started | None |
| M6 optional publishing API | Not started | None |
| M7 audience-driven iteration | Not started | None |

## Decisions already made

- CLI/config-first; zero paid generation by default.
- One heavy GPU worker, local storage and durable state.
- Implement both controlled and I2V routes, with measured renderer selection.
- Real local planning and asset generation are required in the first meaningful slice.
- Final human review and separate explicit publishing action.
- YouTube Shorts first; platform export adapters before account automation.

## Decisions awaiting evidence

- Final channel name, character design and visual style.
- Exact model revisions, compatible runtimes and selected download set.
- Spark memory envelope, shot latency, overnight capacity and electricity tariff.
- Audience response, language/geography strategy and commercial viability.

## Coding-agent update template

For each working session append:

1. Date, branch/commit and environment.
2. Milestone and concrete changes.
3. Commands actually run and results; identify mocks versus real inference.
4. Artifact paths, measured timings/costs and remaining risks.
5. Blocked gates, their specific reason, independent work completed.
6. Exact next command and next milestone task.

Never mark a GPU benchmark passed from a mocked provider, a CPU render or a successful model download alone.

## Implementation session — 2026-09-11, codex/m0-m2

M0 and M1 implementation underway; M2 real inference starting. No milestone is yet declared complete.

- Environment and baseline evidence: `docs/ENVIRONMENT.md`.
- Added isolated CPU package, strict nested configuration, initial Pydantic records and exported schemas, local SQLite queue with fenced leases, atomic JSON/artifact manifests, state validators, CLI, renderer, procedural audio and portable review export.
- Added lazy Qwen and SDXL adapters; model downloads authorised by owner for exact revisions within 30 GiB and three GPU hours. Existing Wan files/image/cache retained.
- `.venv/bin/pytest -q`: **17 passed**. Covers schema/path failures, scene continuity, ownership, claim races, expiry fences, cancellation and retry cap.
- Actual fixture command: `.venv/bin/svf enqueue --config configs/fixtures.yaml --brief examples/episode-brief.yaml --mock`, then `.venv/bin/svf worker --config configs/fixtures.yaml --once`.
- Fixture stages passed: plan 0.03s, images 0.03s, render 1.30s, QA 0.23s, review 0.08s. Five attempts. CPU fixture at 180×320, 12 fps. **Not real AI output**.
- Fixture artifact root: `runs/fixtures/ep001-the-heavy-key/attempts/`.
- GPU baseline test passed in actual NVIDIA container. Local model benchmark gates remain pending.
- Remaining work: second fixture and process-kill recovery test; complete contract/CLI audit; real planner validation and image audition; owner style decision; final local-AI rendering and measured review bundle.
- Resume inspection: `.venv/bin/svf status`; inspect `/tmp/svf-real-worker.log` and `runs/ep001-the-heavy-key/attempts/`. Avoid restarting completed model work without checking queue/artifact hashes.

### 2026-09-12 update

- Authorised model cache: about 22 GiB. All selected sizes and LFS weight checksums verified; `docs/download-verification.json` records exact results.
- First Qwen response: 474.386 seconds generation. Parseable JSON but 15-second duration violates the 20–30-second brief; all five repeated closing states also disagree with deterministic action postconditions. Rejected response preserved under the real episode's plan attempt. Bounded repair is running; no accepted local plan or image output claimed yet.
- CPU suite most recently passed 22 tests, including real process kill/resume and action sequencing. Additional atomic-manifest reconciliation test added and being checked.
- Strict configuration is now explicit in `config_types.py`, with decimal currency. Default GPU budget remains globally capped at 10,800 seconds; reservations charge crashed attempts conservatively.
- A compact `ScriptDraft` compiler is implemented for a separately recorded next attempt if full-state planning fails. Model still supplies all story/actions/durations; compiler computes redundant states and timeline. See `docs/DECISIONS.md`.

## Terminal handoff — 2026-09-12

Owner requested a single configurable terminal entry point. Implemented and CPU-smoke-tested:

```bash
bash scripts/reproduce.sh --config configs/local.yaml --brief examples/episode-brief.yaml
```

This reads YAML, resumes valid work, runs local stages, prompts in the terminal for pending storyboard/style decisions, then writes the final review bundle. It retains existing approval when the plan hash is unchanged. `--non-interactive` stops at missing decisions; `--mock` is explicit and rejected in production mode. No publishing command is invoked.

Current actual results:

- **27 CPU tests passed** in the final full run; launcher fixture smoke test passed. Tests include claims, fencing, kill/restart recovery, atomic-manifest reconciliation, budget reservations, asset corruption, exact approval hashes, UTC/hash boundaries and future DB version protection.
- Qwen v1 rejected response: 474.386s generation; verbose repair interrupted. Entire stopped stage charged 1099.821s to the authorised global GPU ledger.
- Qwen compact v2: accepted first response; stage 285.09s, model load 119.466s, inference total 281.179s; peak CUDA allocation 16,938,278,400 bytes. Actual local inference, not a fixture.
- SDXL first audition: six actual images, 107.26s stage. Character sheets/identity failures retained as rejected candidates.
- Targeted illustrated refinement: two actual images, 60.44s stage. Eight generated images total; no new weights or paid calls.
- Two explicit data-only editorial revisions preserve the original Qwen response and compile the revised actions from `examples/heavy-key-editorial-revision.yaml`. These edits are labelled Codex-authored, not raw model output.
- Latest immutable audition version: `runs/ep001-the-heavy-key/audition/versions/7ad1357e-e4b3-4f0f-8d81-6857e6054cf1/`. Both clips are 26s, 576×1024, 24 fps, with original procedural audio. Latest extraction/render/QA took 10.118s pixel and 13.419s illustrated. Both pass implemented technical checks.
- Portable audition entry: `runs/ep001-the-heavy-key/audition/audition.html`. Includes exact version links, QA, costs and original/rejected art. Earlier development preview rerenders and editorial effort were not fully timed; do not interpret the ledger as complete development effort. Electricity and operator cost remain unknown.
- **M2 owner quality gate remains open**: pixel candidate has incorrect human identity; illustrated amber asset has clipped feet. No final storyboard/style approval has been recorded. A storyboard/asset decision is now handled by the terminal launcher; the final episode/review stages resume after that decision. Nothing published.
- M0/M1 have executable implementation and CPU/GPU-baseline evidence. M2 has real text/image inference and playable drafts; do not mark the full milestone accepted before owner quality review.
- Next milestone after accepting/improving the prototype: M3 Wan I2V benchmarks, beginning with the preserved existing installation. No M3 downloads authorised or performed.

All supplied uncommitted files remain present. Branch `codex/m0-m2` still has no commits; root Wan script and Dockerfile remain unchanged. New model cache is separate at `models/svf` (about 22 GiB, verified against selected upstream sizes/LFS hashes).

## Direct model-generated video command — 2026-09-12

User clarified that model-generated motion is the intended deliverable and requested a terminal script. Added `scripts/generate_video.sh`, `configs/wan-video.yaml` and the lazy `svf.wan` adapter. This uses the existing cached **Wan2.1-T2V-1.3B-Diffusers**, exact revision `0fad780a534b6463e45facd96134c9f345acfa5b`, with the preserved NVIDIA-based image. It generates frames through Wan, not the cutout renderer.

```bash
bash scripts/generate_video.sh configs/wan-video.yaml
```

Default is one 81-frame, 16-fps, 832×480 silent clip (~5.06 seconds). Edit prompt/settings in YAML. Each invocation creates a unique `outputs/wan/<attempt-id>/video.mp4`, config snapshot and timing/hash manifest. Offline/local-files-only loading, global GPU lock, resource checks and a configured timeout are enabled. No model downloads or publication. Original Wan script/config remain unchanged.

Validation actually performed: shell syntax, lint, installed exporter signature, cached pipeline/VAE metadata and `bash scripts/generate_video.sh configs/wan-video.yaml --check` in the actual preserved container. Four focused config tests added. **No Wan inference was started during this handoff; user requested the command to run it themselves.** This provides a direct T2V clip runner; integration into the episode DAG and M3 I2V benchmarks remain separate work.

## Larger Wan download handoff — 2026-09-12

User requested the bigger Wan model. Prepared official Wan2.2-T2V-A14B-Diffusers revision `5be7df9619b54f4e2667b2755bc6a756675b5cd7`, matching the current text-to-video workflow. Public Hub metadata lists 41 selected runtime files totalling 126,199,274,206 bytes (117.53 GiB): both transformer experts, text encoder, VAE, tokenizer, scheduler and model index. Exact filenames, sizes and upstream LFS hashes are in `docs/wan22-download.json`. Disk budget 125 GiB plus 30 GiB free reserve; separate `models/wan22` cache. Existing cache and host packages are unchanged. Uses the preserved NVIDIA-based container's supported hf CLI, with no GPU request.

Validated Python download preview and lint; no weights downloaded and no A14B inference performed. User can explicitly start the displayed set with `python3 scripts/download_wan_large.py --download`; the same command resumes interruption. This set is outside the previous Qwen/SDXL approval, so it has not been fetched automatically. Existing `generate_video.sh` remains limited to the small Wan model; A14B adapter/profile and measured Spark memory validation remain pending.
