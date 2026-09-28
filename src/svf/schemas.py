from typing import Literal, Annotated
from datetime import datetime, timezone
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator, AfterValidator


def utc_stamp(value):
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("UTC timezone required")
    return value


UTCStamp = Annotated[datetime, AfterValidator(utc_stamp)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal[1] = 1


class Duration(Record):
    min: float = Field(gt=0)
    max: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.max < self.min:
            raise ValueError("duration max < min")
        return self


class Experiment(Record):
    id: str
    hypothesis: str
    status: str


class EpisodeBrief(Record):
    episode_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    series_id: str
    series_version: int = Field(ge=1)
    status: str = "proposed"
    content_family: Literal["cooperation", "competition", "mystery"]
    original_brief: str
    viewer_question: str
    payoff: str
    duration_seconds: Duration
    language: str
    characters: list[str]
    required_props: list[str]
    constraints: list[str]
    suggested_renderer: Literal["controlled"] = "controlled"
    i2v_candidate_shots: list[str] = []
    experiment: Experiment
    budget_seconds: float = Field(default=10800, gt=0)


class ObjectState(Record):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    pose: str = "neutral"
    visible: bool = True
    owner: str | None = None
    supported_by: str | None = None


class SceneState(Record):
    objects: dict[str, ObjectState]
    active_rules: list[str] = []


class Action(Record):
    kind: Literal[
        "move",
        "look",
        "pose",
        "pick_up",
        "carry",
        "place",
        "activate_switch",
        "change_mechanism_state",
        "camera_move",
        "cut",
        "sound_cue",
    ]
    actor: str
    target: str | None = None
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    value: str = ""


class ShotPlan(Record):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    purpose: str
    renderer: Literal["controlled"] = "controlled"
    cast: list[str]
    asset_refs: list[str] = []
    opening_state: SceneState
    closing_state: SceneState
    camera: Literal["wide", "medium", "close"] = "wide"
    actions: list[Action]
    keyframe_prompt: str
    motion_prompt: str = ""
    negative_constraints: list[str] = []
    fallback: str | None = None


class EpisodePlan(Record):
    brief_id: str
    brief_hash: Sha256
    provider_kind: Literal["mock", "local"]
    hook: str
    beats: list[str]
    causal_explanation: str
    ending: str
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    plan_critique: list[str] = []
    revisions: int = Field(default=0, ge=0, le=2)
    unresolved_issues: list[str] = []
    shots: list[ShotPlan] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def timeline(self):
        end = 0
        ids = set()
        for shot in self.shots:
            if (
                shot.id in ids
                or abs(shot.start - end) > 0.001
                or shot.end <= shot.start
            ):
                raise ValueError("invalid shot timeline or duplicate ID")
            ids.add(shot.id)
            end = shot.end
        return self


class Asset(Record):
    id: str
    version: int = 1
    sha256: Sha256
    file_ref: str
    type: str
    character_ids: list[str] = []
    world_ids: list[str] = []
    anchors: dict[str, list[float]] = {}
    masks: list[str] = []
    generation_manifest: dict
    licence: str
    attribution: str
    approval_status: Literal["pending", "approved", "rejected"] = "pending"


class ProviderCapabilities(Record):
    provider: str
    model: str
    revision: str | None
    tasks: list[str]
    dtypes: list[str]
    input_forms: list[str]
    dependencies: dict[str, str]
    memory_profile: str
    timeout_seconds: float
    measured: bool = False
    dimension_multiple: int = 1


class Attempt(Record):
    id: UUID
    job_id: str
    stage: str
    started_at: UTCStamp
    finished_at: UTCStamp | None = None
    input_hash: Sha256
    config_hash: Sha256
    code_hash: Sha256
    model_hash: Sha256 | None = None
    prompt_hash: Sha256 | None = None
    seed: int
    requested: dict
    effective: dict
    timings: dict[str, float]
    cost: dict
    result: str
    error: str | None = None
    output_hashes: dict[str, str] = {}


class Check(Record):
    name: str
    status: Literal["pass", "fail", "unavailable"]
    reason: str


class QAReport(Record):
    artifact_hash: Sha256
    checks: list[Check]
    observations: list[dict] = []
    method: str = "ffmpeg-v1"
    editorial_rubric: dict = {}
    human_result: str | None = None


class ReviewDecision(Record):
    reviewer: str
    timestamp: UTCStamp
    decision: Literal["approved", "rejected", "revise"]
    reasons: list[str]
    hashes: dict[str, Sha256]
    versions: dict[str, int]
    requested_shot_changes: list[str] = []


class PublishPackage(Record):
    media_hash: Sha256
    caption_hash: Sha256 | None
    cover_hash: Sha256
    platform: str
    metadata: dict
    audience: str | None
    disclosure: str | None
    rights: list[str]
    approval_hash: Sha256 | None = None


class SourceReference(Record):
    url: str
    collected_at: UTCStamp
    label: Literal["observation", "inference"]
    note: str


class Premise(Record):
    id: str
    original_synopsis: str
    content_family: Literal["cooperation", "competition", "mystery"]
    audience_hypothesis: str
    source_refs: list[SourceReference]
    collected_at: UTCStamp
    duplicate_fingerprint: str


class Character(Record):
    id: str
    role: str
    appearance: str
    approved_asset_ids: list[str]


class ArtDirection(Record):
    selected: str | None
    audition: list[str]
    requirements: list[str]


class CreativeReview(Record):
    early_viewer_question: str
    genuine_payoff: str
    loop: str
    unexpected_unintroduced_objects: str
    colour_or_seed_variant_as_new_episode: str


class SeriesBible(Record):
    series_id: str
    version: int = Field(ge=1)
    status: str
    audience_hypothesis: str
    language: str
    packaging_language: str
    duration_seconds: Duration
    content_families: list[str]
    art_direction: ArtDirection
    characters: list[Character]
    world_rules: list[str]
    allowed_actions: list[str]
    creative_review: CreativeReview
    prohibited_continuity_changes: list[str] = [
        "unintroduced objects",
        "unexplained ability changes",
    ]
    audio_identity: str = "original procedural cues"


class MetricValue(Record):
    value: float | None
    unit: str
    denominator: str | None
    unavailable_reason: str | None = None


class MetricSnapshot(Record):
    platform: str
    video_id: str
    episode_id: str
    publication_time: UTCStamp
    collection_time: UTCStamp
    covered_period: str
    geography: str | None
    language: str | None
    metrics: dict[str, MetricValue]
    definitions_version: str
    source: str


class ScriptShot(Record):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    duration_seconds: float = Field(gt=0, le=10)
    purpose: str
    camera: Literal["wide", "medium", "close"] = "wide"
    actions: list[Action]
    keyframe_prompt: str


class ScriptDraft(Record):
    hook: str
    causal_explanation: str
    ending: str
    initial_state: SceneState
    shots: list[ScriptShot] = Field(min_length=4, max_length=7)


class ImageSpec(Record):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    prompt: str
    negative_prompt: str = ""


class ArtRefinement(Record):
    reason: str
    images: list[ImageSpec] = Field(min_length=1, max_length=3)
