"""Generate a branded README hero/banner PNG for SpamSMS Guardian.

Pure PIL — no network, no fonts beyond the bundled DejaVu that ships with Pillow.
Run:  python -I scripts/make_banner.py
Writes docs/banner.png (1600x480).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "docs" / "banner.png"
W, H = 1600, 480

# Palette (dark slate + emerald accent, readable in GitHub light & dark)
BG_TOP = (15, 23, 42)      # slate-900
BG_BOT = (30, 41, 59)      # slate-800
ACCENT = (16, 185, 129)    # emerald-500
ACCENT_SOFT = (52, 211, 153)
TEXT = (241, 245, 249)     # slate-100
MUTED = (148, 163, 184)    # slate-400
CARD = (51, 65, 85)        # slate-700


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)

    # Vertical gradient background
    for y in range(H):
        t = y / H
        col = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=col)

    # Subtle diagonal accent glow on the right
    for r in range(420, 0, -6):
        alpha = int(26 * (1 - r / 420))
        d.ellipse([W - 260 - r, H // 2 - r, W - 260 + r, H // 2 + r],
                  fill=(BG_BOT[0] + alpha, BG_BOT[1] + alpha + 18, BG_BOT[2] + alpha + 8))

    # Shield mark (left)
    cx, cy, s = 150, H // 2, 92
    d.rounded_rectangle([cx - s, cy - s, cx + s, cy + s], radius=28,
                        fill=CARD, outline=ACCENT, width=4)
    # checkmark inside shield
    d.line([(cx - 40, cy + 2), (cx - 8, cy + 36), (cx + 46, cy - 34)],
           fill=ACCENT_SOFT, width=16, joint="curve")

    # Title
    title_f = font(76, bold=True)
    tag_f = font(30)
    chip_f = font(22, bold=True)

    tx = 300
    d.text((tx, 96), "SpamSMS Guardian", font=title_f, fill=TEXT)
    d.text((tx + 2, 200),
           "Offline-first SMS spam & phishing checker · explainable verdicts",
           font=tag_f, fill=MUTED)

    # Feature chips
    chips = ["FastAPI", "React + TS", "TF-IDF · Naive Bayes", "Zero egress", "Stripe-ready"]
    x = tx
    y = 300
    for label in chips:
        tw = d.textlength(label, font=chip_f)
        pad = 22
        box = [x, y, x + tw + pad * 2, y + 52]
        d.rounded_rectangle(box, radius=26, fill=CARD, outline=ACCENT, width=2)
        d.text((x + pad, y + 12), label, font=chip_f, fill=TEXT)
        x += tw + pad * 2 + 18

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
