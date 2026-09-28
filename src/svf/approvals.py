"""Approval is a statement about exact bytes, never a worker side effect."""

from pathlib import Path
from .storage import hash_file, now
from .schemas import ReviewDecision


def package_hashes(bundle):
    bundle = Path(bundle)
    return {
        name: hash_file(bundle / name)
        for name in ["final.mp4", "cover.png", "publish-package/package.json"]
    }


def approve(bundle, reviewer, reason):
    decision = ReviewDecision(
        reviewer=reviewer,
        timestamp=now(),
        decision="approved",
        reasons=[reason],
        hashes=package_hashes(bundle),
        versions={"package": 1},
    )
    return decision


def is_current(bundle, decision):
    try:
        return decision.decision == "approved" and decision.hashes == package_hashes(
            bundle
        )
    except OSError:
        return False
