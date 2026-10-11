# -*- coding: utf-8 -*-
"""청약레이더 앱 아이콘 생성 (static/ 에 저장). 한 번만 실행하면 됨."""
import pathlib
from PIL import Image, ImageDraw

OUT = pathlib.Path(__file__).resolve().parent / "static"
OUT.mkdir(exist_ok=True)


def icon(n, mask=False, rgb=False):
    S = n * 4
    im = Image.new("RGBA", (S, S), (27, 100, 218, 255))
    d = ImageDraw.Draw(im)
    c = S / 2
    sc = S / 26 * (0.6 if mask else 0.74)
    w = int(2.2 * sc)
    for r in (9.9, 5.5):
        d.ellipse([c - r * sc, c - r * sc, c + r * sc, c + r * sc], outline="white", width=w)
    d.line([c, c, c + 5.6 * sc, c - 5.6 * sc], fill="white", width=w)
    r = 2.3 * sc
    x, y = c + 5.6 * sc, c - 5.6 * sc
    d.ellipse([x - r, y - r, x + r, y + r], fill="white")
    im = im.resize((n, n), Image.LANCZOS)
    return im.convert("RGB") if rgb else im


for name, im in [("icon-192.png", icon(192)), ("icon-512.png", icon(512)),
                 ("icon-mask-512.png", icon(512, True)), ("apple-touch-icon.png", icon(180, rgb=True)),
                 ("favicon-32.png", icon(32))]:
    im.save(OUT / name, "PNG", optimize=True)
    print(name, (OUT / name).stat().st_size)
