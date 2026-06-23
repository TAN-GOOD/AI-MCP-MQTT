import random
import string
import time
import uuid
import math
import io

_store: dict = {}
EXPIRE_SECONDS = 300


def _generate_code(length: int = 4) -> str:
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "").replace("L", "")
    return "".join(random.choices(chars, k=length))


def _generate_svg(code: str) -> str:
    w, h = 150, 50
    svg = io.StringIO()
    svg.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    svg.write(f'<rect width="{w}" height="{h}" fill="#1c1c1e"/>')

    random.seed(hash(code))
    for _ in range(6):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = random.randint(0, w), random.randint(0, h)
        c = random.choice(["#333", "#444", "#555"])
        svg.write(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="1"/>')

    for _ in range(30):
        cx, cy = random.randint(0, w), random.randint(0, h)
        r = random.randint(1, 3)
        c = random.choice(["#444", "#555", "#666"])
        svg.write(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>')

    x_start = 15
    for i, ch in enumerate(code):
        x = x_start + i * 32
        y = 30 + random.randint(-5, 5)
        angle = random.randint(-20, 20)
        size = random.randint(20, 26)
        colors = ["#e5e5e5", "#d4d4d4", "#a3a3a3", "#737373", "#6366f1"]
        color = random.choice(colors)
        svg.write(f'<text x="{x}" y="{y}" font-size="{size}" font-family="monospace" '
                  f'font-weight="bold" fill="{color}" '
                  f'transform="rotate({angle},{x},{y})">{ch}</text>')

    svg.write("</svg>")
    return svg.getvalue()


def create_captcha() -> tuple[str, str]:
    code = _generate_code()
    captcha_id = uuid.uuid4().hex
    svg = _generate_svg(code)
    _store[captcha_id] = {"code": code.lower(), "expire": time.time() + EXPIRE_SECONDS}
    _cleanup()
    return captcha_id, svg


def verify_captcha(captcha_id: str, user_code: str) -> bool:
    entry = _store.pop(captcha_id, None)
    if not entry:
        return False
    if time.time() > entry["expire"]:
        return False
    return entry["code"] == user_code.strip().lower()


def _cleanup():
    now = time.time()
    expired = [k for k, v in _store.items() if now > v["expire"]]
    for k in expired:
        _store.pop(k, None)
