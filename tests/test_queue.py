import concurrent.futures
import time
import pytest
from svf.jobs import Queue


def test_exclusive_claim_and_dependencies(tmp_path):
    q = Queue(tmp_path / "q.db")
    q.enqueue("a", ["plan", "render"])
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda name: q.claim(name, 60, 3), ["one", "two"]))
    assert sum(r is not None for r in results) == 1
    job = next(r for r in results if r)
    q.finish(job, "succeeded")
    assert q.claim("three", 60, 3)["stage"] == "render"


def test_expiry_fences_old_owner(tmp_path):
    q = Queue(tmp_path / "q.db")
    q.enqueue("a", ["render"])
    old = q.claim("old", 0.01, 3)
    time.sleep(0.02)
    new = q.claim("new", 60, 3)
    assert new["fence"] > old["fence"]
    with pytest.raises(RuntimeError, match="stale"):
        q.finish(old, "succeeded")
    q.finish(new, "succeeded")
    with q.db() as db:
        assert (
            db.execute(
                "SELECT result FROM attempts WHERE id=?", (old["attempt_id"],)
            ).fetchone()[0]
            == "interrupted"
        )


def test_cancel_fences_completion(tmp_path):
    q = Queue(tmp_path / "q.db")
    q.enqueue("a", ["render"])
    job = q.claim("one", 60, 3)
    q.cancel("a")
    with pytest.raises(RuntimeError):
        q.finish(job, "succeeded")


def test_gpu_lock(tmp_path):
    q = Queue(tmp_path / "q.db")
    q.enqueue("a", ["x"])
    job = q.claim("a", 60, 3)
    with q.gpu(job, 60):
        with pytest.raises(RuntimeError, match="GPU_BUSY"):
            with q.gpu(job, 60):
                pass


def test_retry_cap(tmp_path):
    q = Queue(tmp_path / "q.db")
    q.enqueue("a", ["x"])
    q.claim("a", 0.01, 1)
    time.sleep(0.02)
    assert q.claim("b", 60, 1) is None
    assert q.status()[0]["state"] == "failed"


def test_budget_reserves_before_execution_and_counts_crashes(tmp_path):
    from svf.budgets import Budget

    b = Budget(tmp_path / "b.db", 100)
    first, seconds = b.reserve(60, "first")
    assert seconds == 60
    second, seconds = b.reserve(60, "second")
    assert seconds == 40
    with pytest.raises(RuntimeError, match="BUDGET"):
        b.reserve(1, "over")
    b.finish(first, 10)
    _, seconds = b.reserve(60, "third")
    assert seconds == 50


def test_atomic_manifest_reconciliation(tmp_path):
    from svf.storage import write_json, hash_file
    from svf.recovery import reconcile

    q = Queue(tmp_path / "q.db")
    q.enqueue("episode", ["render"])
    job = q.claim("owner", 0.01, 3)
    directory = tmp_path / "runs/episode/attempts/render" / job["attempt_id"]
    directory.mkdir(parents=True)
    write_json(
        directory / "attempt.json",
        {"job_id": job["id"], "result": "succeeded", "timings": {"wall_seconds": 1}},
    )
    write_json(
        directory / "manifest.json",
        {
            "attempt_id": job["attempt_id"],
            "outputs": {"attempt.json": hash_file(directory / "attempt.json")},
        },
    )
    time.sleep(0.02)
    assert reconcile(q, tmp_path / "runs") == [job["id"]]
    assert q.status()[0]["state"] == "succeeded"
    assert q.claim("next", 60, 3) is None


def test_future_database_schema_is_not_downgraded(tmp_path):
    import sqlite3

    path = tmp_path / "future.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=2")
    with pytest.raises(ValueError, match="migration"):
        Queue(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
