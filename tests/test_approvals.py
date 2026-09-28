from svf.approvals import approve, is_current


def test_metadata_or_media_change_invalidates_approval(tmp_path):
    (tmp_path / "publish-package").mkdir()
    for name in ["final.mp4", "cover.png", "publish-package/package.json"]:
        (tmp_path / name).write_bytes(b"original")
    decision = approve(tmp_path, "owner", "reviewed playback")
    assert is_current(tmp_path, decision)
    (tmp_path / "publish-package/package.json").write_bytes(b"new title")
    assert not is_current(tmp_path, decision)
    (tmp_path / "publish-package/package.json").write_bytes(b"original")
    (tmp_path / "final.mp4").write_bytes(b"new render")
    assert not is_current(tmp_path, decision)
