"""플레이 스토어 등록 자료: 그래픽 이미지(1024x500) + 휴대폰 스크린샷(1080x1920) 4장 → app/store/"""
import pathlib, shutil
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "store"
OUT.mkdir(exist_ok=True)
SITE = HERE.parent / "site"

# 1) 아이콘 512 (사이트 아이콘 그대로)
shutil.copy(SITE / "icon-512.png", OUT / "icon-512.png")

# 2) 그래픽 이미지 1024x500
W, H = 1024, 500
im = Image.new("RGB", (W, H))
d = ImageDraw.Draw(im)
for y in range(H):
    d.line([(0, y), (W, y)], fill=(27, 100 - y // 30, 218 - y // 8))
fb, fr = "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf"
icon = Image.open(SITE / "icon-512.png").convert("RGBA").resize((150, 150))
im.paste(icon, (80, 90), icon)
d.text((260, 92), "청약콕", font=ImageFont.truetype(fb, 110), fill="white")
d.text((84, 290), "아파트 청약 일정·분양가·경쟁률", font=ImageFont.truetype(fb, 46), fill="white")
d.text((84, 356), "가점 계산기 · 입지 정보 · 캘린더 일정 알림", font=ImageFont.truetype(fr, 34), fill="#D6E6FF")
im.save(OUT / "feature-1024x500.png")

# 3) 휴대폰 스크린샷 (실제 사이트, 412x732 화면을 2.62배 = 1080x1920)
from playwright.sync_api import sync_playwright
pages = [("1-home", "https://cheongyakkok.com/"),
         ("2-apt", "https://cheongyakkok.com/apt/rem-2026910256-2026910256.html"),
         ("3-calendar", "https://cheongyakkok.com/calendar.html"),
         ("4-calc", "https://cheongyakkok.com/calc.html")]
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")  # PC에 설치된 크롬 사용
    ctx = b.new_context(viewport={"width": 412, "height": 732}, device_scale_factor=1080 / 412, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    for name, url in pages:
        pg.goto(url, wait_until="networkidle", timeout=60000)
        pg.add_style_tag(content=".ad,.adsbygoogle,ins{display:none!important}")  # 빈 광고 자리 숨김
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(OUT / f"phone-{name}.png"))
    b.close()
for f in sorted(OUT.iterdir()):
    print(f.name, Image.open(f).size)
