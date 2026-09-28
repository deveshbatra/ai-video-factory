import subprocess
import time
import uuid
import pytest
import yaml
from svf.config import Config, ROOT
from svf.schemas import EpisodeBrief
from svf.workflow import create, worker, queue, resume, stage_dir


def test_real_process_kill_and_resume():
    name = "test-" + uuid.uuid4().hex
    c = yaml.safe_load((ROOT / "configs/fixtures.yaml").read_text())
    c["project"].update(
        output_root="./runs/tests/" + name, database_path="./state/" + name + ".db"
    )
    c["resources"].update(lease_seconds=3, heartbeat_seconds=1)
    c["delivery"].update(width=720, height=1280, fps=24)
    cfg = Config.model_validate(c)
    b = EpisodeBrief.model_validate(
        yaml.safe_load((ROOT / "examples/episode-brief.yaml").read_text())
    )
    root = create(cfg, b, True)
    cfg_path = root / "test-config.yaml"
    cfg_path.write_text(yaml.safe_dump(c))
    p = subprocess.Popen(
        [str(ROOT / ".venv/bin/svf"), "worker", "--config", str(cfg_path), "--once"],
        stdout=subprocess.DEVNULL,
    )
    q = queue(cfg)
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            rows = q.status(b.episode_id)
            if any(r["stage"] == "render" and r["state"] == "running" for r in rows):
                break
            time.sleep(0.02)
        else:
            raise AssertionError("render not reached")
        before = {r["stage"]: r["attempts"] for r in rows}
        p.kill()
        p.wait()
        time.sleep(3.1)
        worker(cfg, b.episode_id)
        rows = q.status(b.episode_id)
        assert all(r["state"] == "succeeded" for r in rows)
        assert (
            next(r for r in rows if r["stage"] == "plan")["attempts"]
            == before["plan"]
            == 1
        )
        assert next(r for r in rows if r["stage"] == "render")["attempts"] == 2
        rendered = stage_dir(q, b.episode_id, "render")
        (rendered / "cover.png").write_bytes(b"corrupt")
        resume(cfg, b.episode_id)
        assert [r["state"] for r in q.status(b.episode_id)] == [
            "succeeded",
            "succeeded",
            "queued",
            "queued",
            "queued",
        ]
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_production_mock_rejected():
    c = yaml.safe_load((ROOT / "configs/fixtures.yaml").read_text())
    c["project"]["mode"] = "production"
    b = EpisodeBrief.model_validate(
        yaml.safe_load((ROOT / "examples/episode-brief.yaml").read_text())
    )
    with pytest.raises(ValueError, match="mock"):
        create(Config.model_validate(c), b, True)
