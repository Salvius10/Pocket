"""Draws the Poko app icon (the pocket with a coin) and writes the web and Android icon files.

Same shapes and colours as the painted mascot in apps/mobile/lib/features/mascot/mascot.dart.
Run: uv run --with pillow python scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "apps" / "mobile"
INK, BG = (18, 20, 13), (12, 13, 10)
LIME, HEM, SHADE = (200, 241, 105), (180, 220, 85), (57, 71, 20)
COIN, COIN_EDGE, SHINE = (242, 204, 107), (185, 143, 46), (246, 251, 228)
S = 8  # supersampling: draw at 8x, scale down for clean edges


def quad(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], n: int = 24) -> list[tuple[float, float]]:
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (i / n for i in range(n + 1))]


def body_points() -> list[tuple[float, float]]:
    left, right, top, c = 38.0, 162.0, 64.0, 12.0
    pts: list[tuple[float, float]] = [(left + c, top), (right - c, top)]
    pts += quad((right - c, top), (right, top), (right, top + c))
    pts += [(right, 126)]
    pts += quad((right, 126), (right - 1, 158), (114, 175))
    pts += quad((114, 175), (100, 181), (86, 175))
    pts += quad((86, 175), (left + 1, 158), (left, 126))
    pts += [(left, top + c)]
    pts += quad((left, top + c), (left, top), (left + c, top))
    return pts


def draw_poko(size: int, scale: float, background: tuple[int, int, int] | None) -> Image.Image:
    """`scale` is how much of the canvas the 200-unit drawing fills (maskable icons need a margin)."""
    px = size * S
    img = Image.new("RGBA", (px, px), (*background, 255) if background else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = px * scale / 200
    ox, oy = (px - 200 * k) / 2, (px - 200 * k) / 2 - 2 * k  # nudge up: the coin makes it top-heavy

    def P(x: float, y: float) -> tuple[float, float]:
        return (ox + x * k, oy + y * k)

    def poly(points: list[tuple[float, float]], dx: float = 0, dy: float = 0) -> list[tuple[float, float]]:
        return [P(x + dx, y + dy) for x, y in points]

    body = body_points()
    d.polygon(poly(body, 7, 7), fill=SHADE)  # hard offset shadow
    # coin, behind the pocket
    cx, cy, r = 100, 50, 26
    d.ellipse([*P(cx - r, cy - r), *P(cx + r, cy + r)], fill=COIN, outline=INK, width=round(3.2 * k))
    d.ellipse([*P(cx - 19.5, cy - 19.5), *P(cx + 19.5, cy + 19.5)], outline=COIN_EDGE, width=max(1, round(1.6 * k)))
    try:
        font = ImageFont.truetype(str(MOBILE / "assets" / "fonts" / "IBMPlexMono-SemiBold.ttf"), round(25 * k))
        d.text(P(cx, cy - 0.5), "₹", font=font, fill=INK, anchor="mm")
    except OSError:
        pass
    # pocket
    d.polygon(poly(body), fill=LIME)
    hem = [(x, y) for x, y in body if y <= 81] + [(162, 81), (38, 81)]
    d.polygon(poly([(38, 76), (38 + 12, 64), (162 - 12, 64), (162, 76), (162, 81), (38, 81)]), fill=HEM)
    del hem
    d.line([P(38, 81), P(162, 81)], fill=(18, 20, 13, 90), width=max(1, round(1.6 * k)))
    stitch = (18, 20, 13, 120)
    for x in range(47, 150, 11):  # top stitch
        d.line([P(x, 72.5), P(min(x + 6, 153), 72.5)], fill=stitch, width=max(1, round(1.8 * k)))
    side = [(47.0, 92.0), (47.0, 125.0)] + quad((47, 125), (49, 151), (89, 166)) + quad((89, 166), (100, 170.5), (111, 166)) \
        + quad((111, 166), (151, 151), (153, 125)) + [(153.0, 92.0)]
    for i in range(0, len(side) - 2, 4):  # dashed side stitch
        d.line([P(*side[i]), P(*side[i + 2])], fill=stitch, width=max(1, round(1.8 * k)))
    d.line(poly(body) + [P(*body[0])], fill=INK, width=round(3.2 * k), joint="curve")
    # face
    for ex in (78, 122):
        d.rounded_rectangle([*P(ex - 6.75, 114 - 10.5), *P(ex + 6.75, 114 + 10.5)], radius=6.75 * k, fill=INK)
        d.ellipse([*P(ex + 2.4 - 2.3, 109.4 - 2.3), *P(ex + 2.4 + 2.3, 109.4 + 2.3)], fill=SHINE)
    smile = quad((88, 140), (100, 148), (112, 140), 16)
    d.line(poly(smile), fill=INK, width=round(3.6 * k), joint="curve")
    for end in (smile[0], smile[-1]):
        d.ellipse([*P(end[0] - 1.8, end[1] - 1.8), *P(end[0] + 1.8, end[1] + 1.8)], fill=INK)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    web = MOBILE / "web"
    for size in (192, 512):
        draw_poko(size, 0.80, BG).convert("RGB").save(web / "icons" / f"Icon-{size}.png")
        draw_poko(size, 0.62, BG).convert("RGB").save(web / "icons" / f"Icon-maskable-{size}.png")  # safe zone
    draw_poko(64, 0.92, None).save(web / "favicon.png")
    res = MOBILE / "android" / "app" / "src" / "main" / "res"
    for folder, size in (("mipmap-mdpi", 48), ("mipmap-hdpi", 72), ("mipmap-xhdpi", 96), ("mipmap-xxhdpi", 144), ("mipmap-xxxhdpi", 192)):
        if (res / folder).exists():
            draw_poko(size, 0.70, BG).convert("RGB").save(res / folder / "ic_launcher.png")
    print("icons written")


if __name__ == "__main__":
    main()
