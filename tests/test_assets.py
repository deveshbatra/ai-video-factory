import pytest
from svf.assets import AssetRegistry
from svf.schemas import Asset
from svf.storage import hash_file


def test_registry_reuses_hash_and_rejects_corruption(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"image bytes")
    asset = Asset(
        id="pip",
        sha256=hash_file(source),
        file_ref="source.png",
        type="cutout",
        generation_manifest={"provider_kind": "mock"},
        licence="test",
        attribution="fixture",
    )
    registry = AssetRegistry(tmp_path / "assets", tmp_path / "state.db")
    first = registry.register(asset, source)
    assert registry.register(asset, source).version == first.version == 1
    assert registry.get("pip", 1).sha256 == asset.sha256
    (registry.root / first.file_ref).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        registry.get("pip", 1)
