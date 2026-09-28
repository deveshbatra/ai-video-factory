# Spark Video Factory — Codex handoff

Planning baseline: 11 September 2026. Suggested repository name: `spark-video-factory`.

Build a local-first studio for original, engaging short animated stories, using Devesh's DGX Spark for planning and visual generation. Optimise accepted creative output, audience growth and eventual contribution profit. Owning a Spark is a production opportunity, not evidence of a competitive advantage by itself.

**This archive contains specifications, configuration examples and implementation instructions. It does not contain the implemented studio.** Commands described in the documents are target interfaces for Codex to implement.

## Put this in the repository

Copy the contents of this folder into the repository root. `AGENTS.md` belongs at the root so a coding agent working there can discover it. Open that repository in VS Code on Spark and paste the prompt from [CODEX_START.md](CODEX_START.md).

If using the existing `~/projects/ai-video-factory` repository, preserve its Dockerfile, configs, model cache and working Wan script. Have Codex inspect and integrate them on a new branch. Do not replace existing files blindly with these planning files; reconcile any existing `AGENTS.md` first. A new repository may instead reference the existing model cache through configuration.

## Read in this order

1. [AGENTS.md](AGENTS.md): binding project instructions for implementation.
2. [PLAN.md](PLAN.md): ordered milestones and evidence required to finish them.
3. [docs/PRODUCT.md](docs/PRODUCT.md): audience, content and business hypotheses.
4. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): pipeline and runtime design.
5. [docs/CONTRACTS.md](docs/CONTRACTS.md): typed records and state transitions.
6. [docs/ROLES.md](docs/ROLES.md): director and other role specifications.
7. [docs/MODELS_AND_BENCHMARKS.md](docs/MODELS_AND_BENCHMARKS.md): model candidates and Spark validation.
8. [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md): measurement and decision rules.
9. [docs/RUNBOOK.md](docs/RUNBOOK.md): target operating workflow.

`configs/*.example.yaml` are proposed settings, not yet executable configs. Codex must implement validation against them and update examples as interfaces settle. `examples/episode-brief.yaml` is an original creative fixture, not evidence of audience demand.

## The first meaningful delivery

An operator supplies a brief and an editable config. A local model produces a valid script and shot plan. A local image model produces an approved visual asset. The chosen renderer produces an original short with audio and a review bundle. A killed run can resume without losing completed work. Its costs and failures are recorded. Nothing is published automatically.

The earlier robot/pixel pilot is a disposable technical reference. Its art and plot are not the approved channel identity. Pixel art, stylised illustrated animation and hybrid I2V must compete in a small visual trial before committing to a production style.

No promise of Seedance-equivalent quality, virality, revenue or overnight throughput is part of this specification. Those claims require evidence.

## Run the implemented pipeline

From this checkout on Spark:

```bash
bash scripts/reproduce.sh --config configs/local.yaml --brief examples/episode-brief.yaml
```

Edit the YAML to configure the run. The launcher resumes completed stages, handles pending review choices in your terminal and prints the video/review paths. The authorised models are already cached on this Spark. Nothing is published automatically. Use `--non-interactive` to stop cleanly at required review decisions. See `docs/PROGRESS.md` for measured real-model results and remaining quality gates.
