# Typed contracts and state machine

Codex must implement Pydantic models and export JSON Schema from those models. The field sets below are normative requirements, not standalone executable schemas. Use `schema_version: 1`, UTC ISO8601 timestamps, stable UUIDs, SHA-256 hashes and explicit units. Reject unknown config fields. Keep migrations for persisted records.

## Core records

| Record | Required content |
| --- | --- |
| `Premise` | ID, original synopsis, content family, target audience hypothesis, source refs, observation/inference labels, collected date, duplicate fingerprint |
| `SeriesBible` | Version, character IDs and traits, approved asset IDs, world rules, palette/style constraints, permitted actions, prohibited continuity changes, audio identity |
| `EpisodeBrief` | ID, premise ID or original brief, series version, duration range, language, core question, payoff, creative constraints, production budget, experiment ID |
| `EpisodePlan` | Brief ID/hash, hook, beats, causal explanation, shot IDs, ending, estimated cost, plan critique, revisions and unresolved issues |
| `ShotPlan` | ID, timeline range, purpose, renderer, cast, asset refs, opening/closing state, camera, actions, keyframe prompt, motion prompt, negative constraints, fallback |
| `SceneState` | Object IDs, positions/anchors, inventory/ownership, active rules, support/contact relationships, character pose, visibility |
| `Asset` | ID/version/hash, file ref, type, character/world IDs, anchors/masks where needed, source/generation manifest, licence, attribution, approval status |
| `ProviderCapabilities` | Provider/model/revision, supported tasks/dtypes, dimension/frame constraints, input forms, dependencies, memory profile, timeout, measured status |
| `Attempt` | Job/stage/attempt ID, timestamps, input/config/code/model/prompt hashes, seed, requested/effective settings, timings, cost, result/error, output hashes |
| `QAReport` | Artifact hash, checks with pass/fail/unavailable, observations with timecodes, severity, method/version, editorial rubric and human result |
| `ReviewDecision` | Reviewer, timestamp, approved/rejected/revise, reasons, referenced versions and hashes, requested shot changes |
| `PublishPackage` | Final media/caption/cover hashes, platform, metadata, audience/disclosure fields, source-rights references, approval hash |
| `MetricSnapshot` | Platform/video/episode ID, publication time, collection time, covered period, geography/language if available, metric values/units, definitions version, source |

## Validation

- Plans have monotonic non-overlapping shot times and a complete covered timeline within the brief's duration range. Transitions/overlaps must be represented explicitly and included in duration arithmetic.
- Referenced characters/assets exist in the selected bible. Props needed for a payoff are introduced before use. Every controlled action has satisfied preconditions and valid postconditions.
- I2V plans declare intended states, but a schema pass is not proof that generated pixels satisfy them. Observed QA is separate.
- Dimensions and frame counts satisfy the selected adapter's capabilities. Reject unsupported requests before expensive inference. Never assume a universal `4n+1` frame rule or identical resolution names across models.
- Seeds are recorded per attempt. Requested durations, source frames/fps and delivered durations/frames/fps are all retained. Any trim, retime, upscale or crop is explicit.
- Budget values are nonnegative and use decimal currency amounts. Unknown actual energy/revenue is null with a reason, never silently zero.
- No secrets, raw credentials or executable commands in model-facing records. Generated asset paths are IDs resolved by the application.

## Provider interfaces

Implement typed request/result methods equivalent to:

```python
TextProvider.generate_structured(request, schema, budget) -> StructuredResult
ImageProvider.generate(request, budget) -> AssetCandidates
VideoProvider.generate(request, budget) -> ClipCandidates
AudioProvider.render(request, budget) -> AudioTracks
Renderer.render(scene_plan, assets, budget) -> ClipResult
```

Each provider exposes capabilities and health checks. Results contain attempt metadata, not only paths. Mock providers use explicit `provider_kind=mock`; reject them in a production-mode run. Imports remain lazy so CPU commands do not initialise CUDA.

## Production job states

`queued → running → succeeded | failed | cancelled | blocked`

Dependencies gate stage eligibility. `blocked` includes missing approved assets, unavailable hardware and budget limits, with machine-readable reasons. A retry creates a new attempt and returns the job to queued; preserve all previous attempts. Limit schema repair to two retries and production shot candidates to the configured cap, counting the first attempt.

Default retry policy: retry transient IO/download failures with bounded backoff; invalid config/model licence is terminal; malformed model JSON gets bounded repair; OOM ends the worker, records memory observations and permits at most one declared lower-memory profile. Creative revision is a new version, not a hidden infrastructure retry.

GPU jobs obtain both a job lease and the single GPU-resource lease before loading weights. Leases have fencing tokens. Cancellation reaches subprocesses and releases resources after cleanup. A job must reserve its estimated runtime/cost before starting, then reconcile actual usage; stop new admissions when the remaining budget is insufficient. Hard timeout handles underestimation.

## Episode and publication states

Episode: `draft → planned → producing → ready_for_review → approved | revision_requested | rejected`.

Publication: `not_requested → intent_recorded → uploading → private_uploaded → public_published`, plus `failed` and `outcome_unknown`. Changing approved content returns the episode to review. Approval and upload never occur as side effects of worker completion.

Persist the publish intent before the request. An uncertain platform response requires reconciliation or operator resolution; do not blindly retry uploads. A local idempotency key cannot guarantee a third-party API's behaviour.

## Minimum run artifact set

`brief.json`, `resolved-config.json` (redacted), `plan.json`, `storyboard/`, `shots/<id>/attempts/`, `audio/`, `final.mp4`, `captions.srt` when applicable, `qa.json`, `costs.json`, `manifest.json`, `review/index.html`, `publish-package/`.

The manifest links every artifact hash and producing attempt. Stable relative paths make review exports portable. A review bundle must include rejected candidates or accessible references to them, not only the winner.
