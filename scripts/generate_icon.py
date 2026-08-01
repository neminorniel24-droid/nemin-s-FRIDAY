"""
generate_icon.py — renders a small glowing peacock-teal orb and saves it as
a multi-resolution .ico, for use as the desktop shortcut icon.

Run once: python3 generate_icon.py
"""

import numpy as np
from PIL import Image, ImageFilter, ImageDraw

SIZE = 512
CENTER = SIZE / 2
RADIUS = SIZE * 0.30

# Colors (matching the app's peacock palette)
CORE = np.array([200, 255, 245])      # near-white cyan highlight
MID = np.array([20, 224, 192])        # main peacock teal
EDGE = np.array([6, 40, 36])          # dark teal edge
BG_GLOW = np.array([20, 224, 192])    # glow color, same teal


def make_sphere():
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(float)
    # highlight offset toward upper-left, like a glossy sphere
    hx, hy = CENTER - RADIUS * 0.35, CENTER - RADIUS * 0.35
    dist_from_highlight = np.sqrt((x - hx) ** 2 + (y - hy) ** 2)
    dist_from_center = np.sqrt((x - CENTER) ** 2 + (y - CENTER) ** 2)

    t = np.clip(dist_from_highlight / (RADIUS * 1.6), 0, 1)
    # blend CORE -> MID -> EDGE along t
    t2 = np.clip((t - 0.35) / 0.65, 0, 1)
    color = (CORE[None, None, :] * (1 - t)[..., None] + MID[None, None, :] * t[..., None])
    color = color * (1 - t2)[..., None] + EDGE[None, None, :] * t2[..., None]

    alpha = np.where(dist_from_center <= RADIUS, 255, 0).astype(np.uint8)
    # soft anti-aliased edge
    edge_band = 3.0
    soft = np.clip((RADIUS - dist_from_center) / edge_band, 0, 1)
    alpha = (soft * 255).clip(0, 255).astype(np.uint8)

    rgba = np.dstack([color.clip(0, 255).astype(np.uint8), alpha])
    return Image.fromarray(rgba, mode="RGBA")


def make_glow(sphere_img):
    # Extract just the alpha as a glow mask, blur it, tint teal, put behind the sphere
    alpha = sphere_img.split()[-1]
    glow_alpha = alpha.filter(ImageFilter.GaussianBlur(radius=SIZE * 0.06))
    glow_rgba = Image.new("RGBA", (SIZE, SIZE), (*BG_GLOW.tolist(), 0))
    glow_rgba.putalpha(glow_alpha.point(lambda p: int(p * 0.55)))
    return glow_rgba


def make_ring(draw_target):
    # A couple of thin wireframe-style rings, echoing the orb UI's shells
    draw = ImageDraw.Draw(draw_target)
    for scale, alpha in [(1.35, 90), (1.55, 50)]:
        r = RADIUS * scale
        bbox = [CENTER - r, CENTER - r * 0.4, CENTER + r, CENTER + r * 0.4]
        draw.ellipse(bbox, outline=(20, 224, 192, alpha), width=3)


def main():
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sphere = make_sphere()
    glow = make_glow(sphere)

    canvas = Image.alpha_composite(canvas, glow)
    make_ring(canvas)
    canvas = Image.alpha_composite(canvas, sphere)

    canvas.save("assets/nemiii.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    canvas.save("assets/nemiii.png")
    print("Saved assets/nemiii.ico and assets/nemiii.png")


if __name__ == "__main__":
    main()
