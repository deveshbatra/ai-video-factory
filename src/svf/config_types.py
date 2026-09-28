"""Strict typed configuration; defaults mirror the supplied project example."""

from decimal import Decimal
from pydantic import Field
from .schemas import Record


class BaseConfigProject(Record):
    name: str = "spark-video-factory"
    mode: str = "development"
    timezone: str = "Europe/London"
    output_root: str = "./runs"
    database_path: str = "./state/studio.sqlite3"
    model_cache: str = "./models"
    asset_root: str = "./assets"


class BaseConfigProvidersText(Record):
    adapter: str = "local_transformers"
    model_id: str = "Qwen/Qwen3-8B"
    revision: str | None = None
    enabled: bool = False


class BaseConfigProvidersImage(Record):
    adapter: str = "local_diffusers"
    model_id: str = "stabilityai/stable-diffusion-xl-base-1.0"
    revision: str | None = None
    enabled: bool = False


class BaseConfigProvidersVideo(Record):
    adapter: str = "wan"
    model_id: str = "Wan-AI/Wan2.2-TI2V-5B"
    revision: str | None = None
    enabled: bool = False
    capability_profile: str | None = None


class BaseConfigProvidersControlled(Record):
    adapter: str = "scene_interpreter"
    enabled: bool = True


class BaseConfigProvidersAudio(Record):
    adapter: str = "procedural_and_licensed"
    speech_enabled: bool = False


class BaseConfigProvidersVisualCritic(Record):
    enabled: bool = False


class BaseConfigProviders(Record):
    text: BaseConfigProvidersText = Field(default_factory=BaseConfigProvidersText)
    image: BaseConfigProvidersImage = Field(default_factory=BaseConfigProvidersImage)
    video: BaseConfigProvidersVideo = Field(default_factory=BaseConfigProvidersVideo)
    controlled: BaseConfigProvidersControlled = Field(
        default_factory=BaseConfigProvidersControlled
    )
    audio: BaseConfigProvidersAudio = Field(default_factory=BaseConfigProvidersAudio)
    visual_critic: BaseConfigProvidersVisualCritic = Field(
        default_factory=BaseConfigProvidersVisualCritic
    )


class BaseConfigProduction(Record):
    primary_renderer: str = "controlled"
    allow_i2v: bool = False
    paid_generation_allowed: bool = False
    max_shots_per_episode: int = Field(default=7, ge=0)
    max_candidates_per_shot: int = Field(default=3, ge=0)
    max_schema_repairs: int = Field(default=2, ge=0)
    max_infrastructure_retries: int = Field(default=2, ge=0)
    max_oom_fallbacks: int = Field(default=1, ge=0)
    storyboard_review_required: bool = True
    final_review_required: bool = True
    default_seed: int = Field(default=42, ge=0)


class BaseConfigDeliveryCaptions(Record):
    enabled: bool = False
    sidecar: bool = True
    safe_area_profile: str = "vertical_default"


class BaseConfigDelivery(Record):
    width: int = Field(default=1080, ge=0)
    height: int = Field(default=1920, ge=0)
    fps: int = Field(default=24, ge=0)
    video_codec: str = "h264"
    audio_codec: str = "aac"
    preserve_native_render_metadata: bool = True
    captions: BaseConfigDeliveryCaptions = Field(
        default_factory=BaseConfigDeliveryCaptions
    )


class BaseConfigResourcesDownloads(Record):
    enabled: bool = False
    max_total_gib: int = Field(default=150, ge=0)


class BaseConfigResources(Record):
    gpu_concurrency: int = Field(default=1, ge=0)
    cpu_workers: int = Field(default=2, ge=0)
    min_available_system_ram_gib: int = Field(default=20, ge=0)
    min_free_disk_gib: int = Field(default=100, ge=0)
    gpu_job_timeout_minutes: int = Field(default=60, ge=0)
    lease_seconds: int = Field(default=120, ge=0)
    heartbeat_seconds: int = Field(default=20, ge=0)
    downloads: BaseConfigResourcesDownloads = Field(
        default_factory=BaseConfigResourcesDownloads
    )


class BaseConfigNightly(Record):
    enabled: bool = False
    start_local: str = "23:00"
    stop_local: str = "07:00"
    max_wall_hours: int = Field(default=8, ge=0)
    max_gpu_hours: int = Field(default=6, ge=0)
    max_episodes: int = Field(default=3, ge=0)
    stop_admitting_before_end_minutes: int = Field(default=30, ge=0)
    finish_inflight_within_hard_deadline: bool = True


class BaseConfigCosts(Record):
    currency: str = "GBP"
    max_external_generation_spend_per_run: Decimal = Decimal("0")
    electricity_gbp_per_kwh: Decimal | None = Field(default=None, ge=0)
    operator_gbp_per_hour: Decimal | None = Field(default=None, ge=0)
    hardware_allocation_gbp_per_episode: Decimal | None = Field(default=None, ge=0)
    energy_source: str = "unavailable"


class BaseConfigPublishing(Record):
    enabled: bool = False
    primary_platform: str = "youtube"
    upload_default_visibility: str = "private"
    require_explicit_publish_action: bool = True
    platforms_export_only: list[str] = ["instagram", "facebook", "tiktok", "snapchat"]


class BaseConfigAnalytics(Record):
    input: str = "csv"
    snapshot_hours_after_publication: list[int] = [24, 168]
    missing_metrics: str | None = None


class BaseConfig(Record):
    project: BaseConfigProject = Field(default_factory=BaseConfigProject)
    providers: BaseConfigProviders = Field(default_factory=BaseConfigProviders)
    production: BaseConfigProduction = Field(default_factory=BaseConfigProduction)
    delivery: BaseConfigDelivery = Field(default_factory=BaseConfigDelivery)
    resources: BaseConfigResources = Field(default_factory=BaseConfigResources)
    nightly: BaseConfigNightly = Field(default_factory=BaseConfigNightly)
    costs: BaseConfigCosts = Field(default_factory=BaseConfigCosts)
    publishing: BaseConfigPublishing = Field(default_factory=BaseConfigPublishing)
    analytics: BaseConfigAnalytics = Field(default_factory=BaseConfigAnalytics)


class TextGeneration(Record):
    max_new_tokens: int = Field(default=5000, gt=0, le=12000)
    dtype: str = "bfloat16"
    attention: str = "sdpa"


class ImageGeneration(Record):
    width: int = Field(default=1024, ge=256, le=1536)
    height: int = Field(default=1024, ge=256, le=1536)
    steps: int = Field(default=30, ge=1, le=60)
    guidance_scale: float = Field(default=6.5, ge=0, le=20)
    dtype: str = "float16"


class InferenceSettings(Record):
    text: TextGeneration = Field(default_factory=TextGeneration)
    image: ImageGeneration = Field(default_factory=ImageGeneration)
