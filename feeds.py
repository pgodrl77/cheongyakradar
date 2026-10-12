"""공유·수집용 부가 파일(2026-10-11)
- og.png: 카카오톡·네이버·페이스북 링크 미리보기 이미지(1200x630)
- rss.xml: 네이버 서치어드바이저 RSS 제출용(최근 공고 50건)
"""
import datetime as dt
from email.utils import format_datetime
from xml.sax.saxutils import escape


def og_image(path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), "#1B64DA")
    d = ImageDraw.Draw(im)
    for i in range(H):  # 위→아래 살짝 진해지는 배경
        c = int(218 - i * 0.06)
        d.line([(0, i), (W, i)], fill=(27, 100 - i // 40, c))
    fb = "C:/Windows/Fonts/malgunbd.ttf"
    fr = "C:/Windows/Fonts/malgun.ttf"
    try:
        big, mid, sm = ImageFont.truetype(fb, 132), ImageFont.truetype(fb, 50), ImageFont.truetype(fr, 34)
    except Exception:
        big = mid = sm = ImageFont.load_default()
    d.rounded_rectangle([90, 120, 210, 240], 30, fill="white")
    d.ellipse([118, 148, 172, 202], outline="#1B64DA", width=12)
    d.line([(166, 196), (190, 220)], fill="#1B64DA", width=14)
    d.text((240, 108), "청약콕", font=big, fill="white")
    d.text((96, 300), "아파트 청약 일정·분양가·경쟁률", font=mid, fill="white")
    d.text((96, 372), "한눈에 보고, 캘린더로 챙기세요", font=mid, fill="#D6E6FF")
    d.text((96, 520), "cheongyakkok.com  ·  가점 계산기 · 입지 정보 · 줍줍 일정", font=sm, fill="#BFD6FF")
    im.save(path, optimize=True)


def rss(items, site_url, site_name, d, esc_short):
    rows = []
    for it in items:
        r = it["d"]
        when = d(r.get("RCRIT_PBLANC_DE"))
        if when:
            rows.append((when, it))
    rows.sort(key=lambda x: x[0], reverse=True)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           f"<title>{site_name} - 아파트 청약 일정</title>", f"<link>{site_url}/</link>",
           "<description>청약홈 분양공고를 매일 정리한 아파트 청약 일정·분양가·경쟁률</description>", "<language>ko</language>"]
    for when, it in rows[:50]:
        r = it["d"]
        name = r.get("HOUSE_NM") or "청약"
        url = f"{site_url}/apt/{it['slug']}.html"
        desc = f"{esc_short(r.get('HSSPLY_ADRES'))} · {it.get('kind') or ''} · {it['status'][1]}"
        if r.get("TOT_SUPLY_HSHLDCO"):
            desc += f" · 총 {r.get('TOT_SUPLY_HSHLDCO')}세대"
        pub = format_datetime(dt.datetime.combine(when, dt.time(9), tzinfo=dt.timezone(dt.timedelta(hours=9))))
        out.append(f"<item><title>{escape(name + ' 청약 일정·분양가')}</title><link>{url}</link><guid>{url}</guid>"
                   f"<description>{escape(desc)}</description><pubDate>{pub}</pubDate></item>")
    out.append("</channel></rss>")
    return "\n".join(out)
