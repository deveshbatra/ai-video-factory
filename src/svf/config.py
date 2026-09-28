from pathlib import Path
from decimal import Decimal
import yaml
from pydantic import model_validator


from .config_types import BaseConfig, InferenceSettings
from pydantic import Field

ROOT = Path(__file__).resolve().parents[2]


class Config(BaseConfig):
    inference: InferenceSettings = Field(default_factory=InferenceSettings)

    @model_validator(mode="after")
    def constraints(self):
        if (
            self.inference.text.dtype != "bfloat16"
            or self.inference.text.attention != "sdpa"
            or self.inference.image.dtype != "float16"
        ):
            raise ValueError("unbenchmarked inference dtype/attention")
        if self.inference.image.width % 8 or self.inference.image.height % 8:
            raise ValueError("SDXL dimensions must be multiples of 8")
        for key in ["output_root", "database_path", "model_cache", "asset_root"]:
            resolve(getattr(self.project, key))
        if self.project.mode not in ["development", "production"]:
            raise ValueError("invalid mode")
        if self.resources.gpu_concurrency != 1:
            raise ValueError("only one heavy GPU stage supported")
        if (
            self.publishing.enabled
            or not self.publishing.require_explicit_publish_action
        ):
            raise ValueError("publishing disabled through M2")
        if (
            self.production.paid_generation_allowed
            or Decimal(str(self.costs.max_external_generation_spend_per_run)) != 0
        ):
            raise ValueError("M0-M2 enforces zero paid API spend")
        for group in [self.resources, self.production, self.nightly, self.costs]:
            for key, value in group.model_dump().items():
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and value < 0
                ):
                    raise ValueError(f"{key} must be nonnegative")
        if self.resources.heartbeat_seconds * 2 >= self.resources.lease_seconds:
            raise ValueError("lease must exceed two heartbeat periods")
        if self.resources.downloads.max_total_gib < 0:
            raise ValueError("negative download budget")
        if (
            self.production.max_schema_repairs > 2
            or self.production.max_candidates_per_shot < 1
        ):
            raise ValueError("invalid retry/candidate cap")
        if (
            self.delivery.width % 2
            or self.delivery.height % 2
            or min(self.delivery.width, self.delivery.height, self.delivery.fps) <= 0
        ):
            raise ValueError("invalid delivery dimensions/fps")
        allowed = {
            "text": ("local_transformers", "Qwen/Qwen3-8B"),
            "image": ("local_diffusers", "stabilityai/stable-diffusion-xl-base-1.0"),
            "video": ("wan", "Wan-AI/Wan2.2-TI2V-5B"),
        }
        for kind, (adapter, model) in allowed.items():
            provider = getattr(self.providers, kind)
            if provider.adapter != adapter or provider.model_id != model:
                raise ValueError("unsupported provider: " + kind)
        for p in [self.providers.text, self.providers.image, self.providers.video]:
            if p.enabled and (not p.revision or len(p.revision) != 40):
                raise ValueError("enabled models require exact revision")
        return self


def resolve(value):
    p = (ROOT / str(value)).resolve()
    if not p.is_relative_to(ROOT) or p == ROOT:
        raise ValueError(f"path must be inside project: {value}")
    return p


def load(path):
    return Config.model_validate(yaml.safe_load(Path(path).read_text()))
