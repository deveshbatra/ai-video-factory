"""Data-driven scene interpreter. No episode-specific timelines."""

import math
import subprocess
import wave
import struct
import shutil
from functools import lru_cache
import yaml
from pathlib import Path
from PIL import Image, ImageDraw
from .storage import write_json, hash_file


def ffmpeg():
    import imageio_ffmpeg

    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


@lru_cache(maxsize=1)
def designs():
    from .config import ROOT

    return yaml.safe_load((ROOT / "configs/render-assets.yaml").read_text())["objects"]


@lru_cache(maxsize=32)
def cached_image(path):
    return Image.open(path).convert("RGBA")


def prop(d, design, x, y, width, height, pose):
    w = design["width"] * width
    h = design["height"] * height
    color = design["color"]
    shape = design["shape"]
    if shape == "key":
        d.ellipse(
            (x - w / 2, y - h, x - w / 5, y), outline=color, width=max(3, int(h * 0.2))
        )
        d.line(
            (x - w / 5, y - h * 0.5, x + w / 2, y - h * 0.5),
            fill=color,
            width=max(3, int(h * 0.18)),
        )
        for k in [0.25, 0.4]:
            d.line(
                (x + w * k, y - h * 0.5, x + w * k, y - h * 0.15),
                fill=color,
                width=max(3, int(h * 0.15)),
            )
    elif shape == "background_door":
        if pose in ["open", "opened", "unlocked"]:
            d.rounded_rectangle(
                (x - w / 2, y - h, x + w / 2, y),
                radius=8,
                fill="#14282c",
                outline="#bca269",
                width=3,
            )
            d.polygon(
                [
                    (x - w / 2, y - h),
                    (x - w * 0.38, y - h * 0.92),
                    (x - w * 0.38, y - h * 0.03),
                    (x - w / 2, y),
                ],
                fill="#286064",
            )
    elif shape == "door":
        d.rounded_rectangle(
            (x - w / 2, y - h, x + w / 2, y),
            radius=10,
            fill="#15252a",
            outline="#c7ac76",
            width=5,
        )
        if pose not in ["open", "opened", "unlocked"]:
            d.rounded_rectangle(
                (x - w / 2 + 6, y - h + 6, x + w / 2 - 6, y - 3), radius=8, fill=color
            )
            d.ellipse(
                (x + w * 0.22, y - h * 0.5, x + w * 0.3, y - h * 0.43), fill="#e8c86a"
            )
        else:
            d.rectangle((x - w / 2, y - h, x - w * 0.38, y), fill=color)
    elif shape == "bell":
        d.pieslice((x - w / 2, y - h, x + w / 2, y + h * 0.3), 180, 360, fill=color)
        d.line((x - w / 2, y - h * 0.25, x + w / 2, y - h * 0.25), fill=color, width=6)
    else:
        d.rounded_rectangle(
            (x - w / 2, y - h, x + w / 2, y),
            radius=5,
            fill=color,
            outline="#bdd1c4",
            width=2,
        )


def sampled_state(shot, u):
    from .planning import apply_actions

    actions = [
        a for a in shot.actions if a.kind not in ["sound_cue", "cut", "camera_move"]
    ]
    state = shot.opening_state.model_copy(deep=True)
    if not actions:
        return state
    position = min(len(actions) - 1e-8, u * len(actions))
    index = int(position)
    fraction = position - index
    for action in actions[:index]:
        state = apply_actions(state, [action])
    action = actions[index]
    end = apply_actions(state, [action])
    if action.kind in ["move", "carry"]:
        ease = fraction * fraction * (3 - 2 * fraction)
        for name, obj in state.objects.items():
            final = end.objects[name]
            obj.x += (final.x - obj.x) * ease
            obj.y += (final.y - obj.y) * ease
        return state
    return end if fraction >= 0.25 else state


def frame(plan, t, width, height, assets=None):
    shot = next((s for s in plan.shots if s.start <= t < s.end), plan.shots[-1])
    u = max(0, min(1, (t - shot.start) / (shot.end - shot.start)))
    current = sampled_state(shot, u)
    from .config import ROOT

    layout = yaml.safe_load((ROOT / "configs/scene-layout.yaml").read_text())
    im = Image.new("RGB", (width, height), "#172936")
    if assets and assets.get("background"):
        bg = cached_image(str(assets["background"])).convert("RGB")
        if layout["background_fit"] == "cover":
            crop_width = min(bg.width, bg.height * width / height)
            center = min(
                bg.width - crop_width / 2,
                max(crop_width / 2, bg.width * layout["background_center_x"]),
            )
            bg = bg.crop(
                (
                    int(center - crop_width / 2),
                    0,
                    int(center + crop_width / 2),
                    bg.height,
                )
            ).resize((width, height), Image.Resampling.LANCZOS)
            im.paste(bg, (0, 0))
        else:
            bg.thumbnail((width, height))
            im.paste(bg, ((width - bg.width) // 2, (height - bg.height) // 2))
    d = ImageDraw.Draw(im)
    d.rectangle((0, height * layout["floor_y"], width, height), fill="#304750")
    for name, o in sorted(
        current.objects.items(),
        key=lambda item: -1
        if designs().get(item[0], {}).get("shape") == "background_door"
        else item[1].y,
    ):
        end = o
        if not o.visible:
            continue
        x = o.x * width
        y = o.y * height
        actor = name in shot.cast
        r = width * (0.065 if actor else 0.04)
        if assets and name in assets:
            sprite = cached_image(str(assets[name])).copy()
            sprite.thumbnail((int(width * 0.28), int(height * 0.28)))
            angle = {
                "strained": -8,
                "determined": 5,
                "curious": -4,
                "surprised": 8,
            }.get(o.pose, 0)
            sprite = sprite.rotate(
                angle, resample=Image.Resampling.BICUBIC, expand=True
            )
            im.paste(
                sprite, (int(x - sprite.width / 2), int(y - sprite.height)), sprite
            )
            d = ImageDraw.Draw(im)
        else:
            color = (
                "#eba642"
                if actor and shot.cast.index(name) == 0
                else "#48aeaa"
                if actor
                else "#c4b782"
            )
            if actor:
                d.rounded_rectangle(
                    (x - r, y - r * 2, x + r, y),
                    radius=r * 0.6,
                    fill=color,
                    outline="#101d28",
                    width=3,
                )
                for dx in [-0.35, 0.35]:
                    d.ellipse(
                        (
                            x + dx * r - 3,
                            y - r * 1.3 - 3,
                            x + dx * r + 3,
                            y - r * 1.3 + 3,
                        ),
                        fill="#101d28",
                    )
                if end.pose in ["happy", "surprised"]:
                    d.arc(
                        (x - r * 0.4, y - r, x + r * 0.4, y - r * 0.4),
                        0,
                        180,
                        fill="#101d28",
                        width=2,
                    )
            else:
                prop(
                    d,
                    designs().get(
                        name,
                        {
                            "shape": "platform",
                            "color": color,
                            "width": 0.08,
                            "height": 0.06,
                        },
                    ),
                    x,
                    y,
                    width,
                    height,
                    end.pose if u > 0.5 else o.pose,
                )
        if plan.provider_kind == "mock":
            d.text((x - r, y + 4), name, fill="white")
    if plan.provider_kind == "mock":
        d.rectangle((0, 0, width, 30), fill="#a22")
        d.text((10, 8), "MOCK FIXTURE - workflow test", fill="white")
    zoom = {"wide": 1.0, "medium": 1.18, "close": 1.4}[shot.camera]
    if any(a.kind == "camera_move" for a in shot.actions):
        zoom *= 1 + 0.1 * u
    if zoom > 1:
        crop_width = width / zoom
        crop_height = height / zoom
        center_x = width * 0.5
        center_y = height * 0.55
        box = (
            int(center_x - crop_width / 2),
            int(center_y - crop_height / 2),
            int(center_x + crop_width / 2),
            int(center_y + crop_height / 2),
        )
        im = im.crop(box).resize((width, height), Image.Resampling.LANCZOS)
    return im


def audio(plan, path):
    rate = 48000
    duration = plan.shots[-1].end
    cues = [
        s.start + 0.2 for s in plan.shots for a in s.actions if a.kind == "sound_cue"
    ]
    if not cues:
        cues = [
            s.start + (i + 0.5) * (s.end - s.start) / max(1, len(s.actions))
            for s in plan.shots
            for i, a in enumerate(s.actions)
            if a.kind in ["move", "carry", "pick_up", "place", "change_mechanism_state"]
        ]
    with wave.open(str(path), "wb") as w:
        w.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        for i in range(round(duration * rate)):
            t = i / rate
            value = 0
            for k, c in enumerate(cues):
                dt = t - c
                if 0 <= dt < 0.7:
                    value += (
                        0.2
                        * math.sin(2 * math.pi * (330 + 55 * k) * dt)
                        * math.exp(-7 * dt)
                        * min(1, dt / 0.01)
                    )
            w.writeframesraw(
                struct.pack("<h", round(max(-0.95, min(0.95, value)) * 32767))
            )
    write_json(
        path.with_suffix(".json"),
        {
            "licence": "CC0-1.0",
            "source": "original procedural sine cues, svf audio-v1",
            "sample_rate": rate,
            "peak_bound": 0.95,
            "sha256": hash_file(path),
        },
    )


def render(plan, out, delivery, assets=None, heartbeat=lambda: None):
    from .config import ROOT

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write_json(
        out / "render-settings.json",
        {
            "renderer": "scene-interpreter-v1",
            "source_images": "1024x1024 when SDXL",
            "delivery": {
                "width": delivery.width,
                "height": delivery.height,
                "fps": delivery.fps,
            },
            "background_layout": yaml.safe_load(
                (ROOT / "configs/scene-layout.yaml").read_text()
            ),
            "camera_zoom": {
                "wide": 1.0,
                "medium": 1.18,
                "close": 1.4,
                "camera_move": "10% shot-progress zoom",
            },
            "actions": "sequential equal-duration non-audio actions",
            "cutout_rotation_degrees": {
                "strained": -8,
                "determined": 5,
                "curious": -4,
                "surprised": 8,
            },
            "provider_kind": plan.provider_kind,
        },
    )
    audio(plan, out / "audio.wav")
    cmd = [
        ffmpeg(),
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{delivery.width}x{delivery.height}",
        "-r",
        str(delivery.fps),
        "-i",
        "pipe:0",
        "-i",
        str(out / "audio.wav"),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out / "final.mp4"),
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(round(plan.shots[-1].end * delivery.fps)):
            if i % delivery.fps == 0:
                heartbeat()
            p.stdin.write(
                frame(
                    plan, i / delivery.fps, delivery.width, delivery.height, assets
                ).tobytes()
            )
        p.stdin.close()
        stderr = p.stderr.read()
        code = p.wait(timeout=60)
        if code:
            raise RuntimeError(stderr.decode()[-2000:])
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    frame(plan, 0, delivery.width, delivery.height, assets).save(out / "cover.png")
    storyboard = out / "storyboard"
    storyboard.mkdir(exist_ok=True)
    for shot in plan.shots:
        frame(
            plan, (shot.start + shot.end) / 2, delivery.width, delivery.height, assets
        ).save(storyboard / (shot.id + ".png"))
