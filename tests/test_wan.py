import pytest
import yaml
from svf.config import ROOT
from svf.wan import WanConfig


def test_wan_config_validates_cached_profile():
    config = WanConfig.model_validate(
        yaml.safe_load((ROOT / "configs/wan-video.yaml").read_text())
    )
    assert config.generation.frames / config.generation.fps == 5.0625


@pytest.mark.parametrize("field,value", [("width", 831), ("frames", 80), ("steps", 0)])
def test_wan_rejects_invalid_generation(field, value):
    data = yaml.safe_load((ROOT / "configs/wan-video.yaml").read_text())
    data["generation"][field] = value
    with pytest.raises(ValueError):
        WanConfig.model_validate(data)
