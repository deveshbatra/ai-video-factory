import subprocess
import array
import re
from .rendering import ffmpeg
from .schemas import QAReport, Check
from .storage import hash_file


def inspect(path, plan, width, height, fps):
    decoded = subprocess.run(
        [
            ffmpeg(),
            "-v",
            "info",
            "-i",
            str(path),
            "-vf",
            "blackdetect=d=1:pix_th=0.05,freezedetect=n=-60dB:d=2",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        timeout=180,
    )
    diagnostic = decoded.stderr.decode()
    black = [float(x) for x in re.findall(r"black_duration:([0-9.]+)", diagnostic)]
    freezes = [float(x) for x in re.findall(r"freeze_start: ([0-9.]+)", diagnostic)]
    from .rendering import sampled_state

    ends = [float(x) for x in re.findall(r"freeze_end: ([0-9.]+)", diagnostic)]
    unexpected = []
    for index, start_time in enumerate(freezes):
        end_time = ends[index] if index < len(ends) else plan.shots[-1].end
        positions = {}
        for tick in range(int(start_time * 4) + 1, int(end_time * 4)):
            t = tick / 4
            shot = next((s for s in plan.shots if s.start <= t < s.end), plan.shots[-1])
            state = sampled_state(shot, (t - shot.start) / (shot.end - shot.start))
            for name, obj in state.objects.items():
                positions.setdefault(name, []).append((obj.x, obj.y))
        if any(
            max(x for x, y in points) - min(x for x, y in points) > 0.02
            or max(y for x, y in points) - min(y for x, y in points) > 0.02
            for points in positions.values()
            if points
        ):
            unexpected.append(start_time)
    raw = subprocess.Popen(
        [
            ffmpeg(),
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    decoded_bytes = 0
    for block in iter(lambda: raw.stdout.read(1024 * 1024), b""):
        decoded_bytes += len(block)
    raw.wait(timeout=180)
    expected = round(plan.shots[-1].end * fps) * width * height * 3
    dimensions = re.search(r"Video:.*? (\d{2,5})x(\d{2,5})(?:[ ,])", diagnostic)
    dimensions_ok = dimensions is not None and tuple(map(int, dimensions.groups())) == (
        width,
        height,
    )
    checks = [
        Check(
            name="decode",
            status="pass" if decoded.returncode == 0 else "fail",
            reason="full video/audio decode"
            if decoded.returncode == 0
            else diagnostic[-1000:],
        ),
        Check(
            name="frames_dimensions_duration",
            status="pass"
            if decoded_bytes == expected and raw.returncode == 0 and dimensions_ok
            else "fail",
            reason=f"RGB bytes {decoded_bytes} expected {expected}",
        ),
    ]
    sound = subprocess.run(
        [
            ffmpeg(),
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "s16le",
            "-ac",
            "1",
            "-",
        ],
        capture_output=True,
        timeout=60,
    )
    samples = array.array("h", sound.stdout)
    peak = max((abs(x) for x in samples), default=0) / 32768
    checks.append(
        Check(
            name="audio_stream_clipping",
            status="pass"
            if sound.returncode == 0 and samples and 0 < peak < 0.999
            else "fail",
            reason=f"decoded peak {peak:.5f}",
        )
    )
    checks.extend(
        [
            Check(
                name="unexpected_black_freeze",
                status="fail" if black or unexpected else "pass",
                reason=f"black segments >=1s: {black}; freezes >=2s during planned motion: {unexpected}; stationary holds permitted",
            ),
            Check(
                name="caption_safe_area",
                status="unavailable",
                reason="wordless episode without captions",
            ),
        ]
    )
    return QAReport(
        artifact_hash=hash_file(path),
        checks=checks,
        editorial_rubric={
            k: None
            for k in ["readability", "coherence", "identity", "motion", "payoff"]
        },
    )
