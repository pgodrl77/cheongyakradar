"""청약콕 주간 네이버 클립(9:16 세로 영상) 자동 제작.
(2026-10-12) 사용: python clip.py [weekly] [--date YYYY-MM-DD]
- data/blogdata.json(청약홈 공공데이터)에서 blogpost.weekly 와 같은 기준으로 이번 주 접수 단지를 고름
- 카드 이미지(Pillow) + 타입캐스트 문정 나레이션(audio_tempo 1.1) → ffmpeg 로 1080x1920 mp4
- 결과: clips/cy-YYYY-MM-DD-weekly.mp4 + .json(제목·설명·해시태그)  ※ mp4 는 커밋 제외
- 타입캐스트 키: 환경변수 TYPECAST_API_KEY 또는 Documents\\.secrets\\typecast.env
"""
import datetime as dt, json, os, pathlib, random, re, subprocess, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

import blogpost as bp

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "clips"
W, H = 1080, 1920
FONT_B = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_R = r"C:\Windows\Fonts\malgun.ttf"
NAVY, NAVY2 = (14, 27, 56), (27, 58, 107)
WHITE, SOFT, GOLD, BLUE = (255, 255, 255), (184, 198, 224), (255, 213, 74), (96, 165, 250)
VOICE = "tc_68f9c6a72f0f04a417bb136f"  # 타입캐스트 문정(Moonjung)
WDN = ["월", "화", "수", "목", "금", "토", "일"]


# ---------- 숫자 → 한글 읽기 (TTS 오독 방지) ----------
def kn(n):
    n = int(n)
    if n == 0:
        return "영"
    d = "영일이삼사오육칠팔구"
    out = ""
    for big, unit in ((100000000, "억"), (10000, "만"), (1, "")):
        g, n = divmod(n, big)
        if not g:
            continue
        s = ""
        for p, u in ((1000, "천"), (100, "백"), (10, "십"), (1, "")):
            q, g = divmod(g, p)
            if q:
                s += ("" if (q == 1 and u) else d[q]) + u
        if unit == "만" and s == "일":
            s = ""
        out += s + unit
    return out


def native(n):
    if not 0 < n < 100:
        return kn(n)
    tens = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
    ones = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
    t, o = divmod(n, 10)
    if t == 2 and o == 0:
        return "스무"
    return tens[t] + ones[o]


def short_region(a):
    p = (a or "").split()
    if not p:
        return ""
    if re.search(r"(광역시|특별시|특별자치시)$", p[0]):
        return re.sub(r"(광역시|특별시|특별자치시)$", "", p[0])
    if len(p) > 1:
        return re.sub(r"(특례시|시|군)$", "", p[1]) or p[1]
    return p[0]


def plain(name):
    return re.sub(r"\s*\(.*?\)", "", name).strip()


# ---------- 그림 ----------
def F(size, bold=True):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def base():
    im = Image.new("RGB", (W, H), NAVY)
    dr = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        dr.line([(0, y), (W, y)], fill=tuple(int(NAVY[i] + (NAVY2[i] - NAVY[i]) * t) for i in range(3)))
    rnd = random.Random(7)  # 매번 같은 도시 실루엣
    x = 0
    while x < W:
        bw, bh = rnd.randint(90, 170), rnd.randint(220, 520)
        dr.rectangle([x, H - bh, x + bw - 8, H], fill=(10, 20, 42))
        for wy in range(H - bh + 24, H - 30, 34):
            for wx in range(x + 14, x + bw - 26, 28):
                if rnd.random() < 0.35:
                    dr.rectangle([wx, wy, wx + 12, wy + 16], fill=(214, 180, 96))
        x += bw
    dr.rounded_rectangle([60, 120, 520, 196], 38, outline=BLUE, width=3)
    dr.text((290, 158), "청약콕 · 이번 주 청약", font=F(38), fill=WHITE, anchor="mm")
    return im, dr


def wrap(dr, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if dr.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def center(dr, y, text, font, fill):
    dr.text((W // 2, y), text, font=font, fill=fill, anchor="mm")


def md(v):
    return f"{v.month}월 {v.day}일({WDN[v.weekday()]})"


def slide_hook(n, mon, sun):
    im, dr = base()
    center(dr, 560, "이번 주 아파트 청약", F(84), WHITE)
    center(dr, 800, f"{n}곳", F(260), GOLD)
    center(dr, 1050, f"{md(mon)} ~ {md(sun)}", F(52, False), SOFT)
    center(dr, 1140, "접수 단지 한눈에 정리", F(52, False), SOFT)
    return im


def slide_card(rank, x, start):
    im, dr = base()
    center(dr, 360, f"이번 주 세대수 {rank}위", F(52), BLUE)
    y = 520
    for ln in wrap(dr, plain(x["n"]), F(92), 940)[:3]:
        center(dr, y, ln, F(92), WHITE)
        y += 118
    center(dr, y + 10, x["a"], F(48, False), SOFT)
    if x["p"] != "apt":
        center(dr, y + 90, x["k"], F(44), GOLD)
    stats = [("세대수", f"{int(x['hh']):,}세대")]
    if x.get("ppp"):
        stats.append(("평당 분양가", f"{x['ppp']:,}만원"))
    stats.append(("접수 시작", md(start)))
    by = max(y + 190, 1020)
    for i, (k, v) in enumerate(stats):
        top = by + i * 150
        dr.rounded_rectangle([110, top, 970, top + 124], 26, fill=(30, 52, 92), outline=(70, 100, 150), width=2)
        dr.text((150, top + 62), k, font=F(44, False), fill=SOFT, anchor="lm")
        dr.text((930, top + 62), v, font=F(56), fill=WHITE, anchor="rm")
    return im


def slide_list(rest):
    im, dr = base()
    center(dr, 380, "이 밖에 이번 주 접수", F(76), WHITE)
    y = 540
    for v, x in rest:
        nm = plain(x["n"])
        f = F(48)
        while dr.textlength(nm, font=f) > 590 and len(nm) > 4:
            nm = nm[:-2] + "…" if not nm.endswith("…") else nm[:-3] + "…"
        dr.text((110, y), nm, font=f, fill=WHITE, anchor="lm")
        dr.text((970, y), f"{short_region(x['a'])} · {v.month}/{v.day}", font=F(40, False), fill=SOFT, anchor="rm")
        y += 108
    return im


def slide_cta():
    im, dr = base()
    center(dr, 560, "단지별 분양가 · 역 거리", F(72), WHITE)
    center(dr, 660, "청약 일정 캘린더 저장까지", F(72), WHITE)
    dr.rounded_rectangle([110, 820, 970, 1000], 40, fill=(37, 99, 235))
    center(dr, 910, "cheongyakkok.com", F(76), WHITE)
    center(dr, 1140, "네이버에서 ‘청약콕’ 검색", F(56), GOLD)
    return im


# ---------- 음성 ----------
def tc_key():
    k = os.environ.get("TYPECAST_API_KEY")
    if k:
        return k.strip()
    p = pathlib.Path.home() / "Documents" / ".secrets" / "typecast.env"
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.startswith("TYPECAST_API_KEY="):
            return ln.split("=", 1)[1].strip()
    raise SystemExit("타입캐스트 키 없음")


def tts(text, path):
    body = {"voice_id": VOICE, "text": text, "model": "ssfm-v30", "language": "kor",
            "prompt": {"emotion_type": "smart"}, "output": {"audio_format": "mp3", "audio_tempo": 1.1}}
    req = urllib.request.Request("https://api.typecast.ai/v1/text-to-speech", data=json.dumps(body).encode(),
                                 headers={"X-API-KEY": tc_key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        path.write_bytes(r.read())


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


# ---------- 대본 ----------
def plan(items, today):
    mon = today - dt.timedelta(days=today.weekday())
    sun = mon + dt.timedelta(days=6)
    rows = []
    for x in items:
        rc = sorted(v for v, t, _ in bp.evs(x) if t in bp.RCPT and mon <= v <= sun)
        if rc:
            rows.append((rc[0], x))
    if not rows:
        return None
    rows.sort(key=lambda r: (r[0], -(int(r[1].get("hh") or 0))))
    top = sorted(rows, key=lambda r: -int(r[1].get("hh") or 0))[:3]
    ids = {id(x) for _, x in top}
    rest = [r for r in rows if id(r[1]) not in ids][:7]
    S = [(slide_hook(len(rows), mon, sun), f"이번 주 아파트 청약, 접수받는 곳이 {native(len(rows))} 곳이에요.")]
    lead = ["가장 큰 곳은", "두 번째는", "세 번째는"]
    for i, (v, x) in enumerate(top):
        hh = int(x.get("hh") or 0)
        mu = "무순위 " if x["p"] != "apt" else ""
        t = f"{lead[i]} {short_region(x['a'])} {plain(x['n'])}, {mu}{kn(hh)} 세대예요."
        if x.get("ppp"):
            t += f" 평당 분양가는 {kn(x['ppp'])}만 원이고, {WDN[v.weekday()]}요일부터 접수해요."
        else:
            t += f" {WDN[v.weekday()]}요일부터 접수해요."
        S.append((slide_card(i + 1, x, v), t))
    if rest:
        regs = list(dict.fromkeys(short_region(x["a"]) for _, x in rest))[:3]
        S.append((slide_list(rest), f"이 밖에 {', '.join(regs)} 등에서도 접수가 있어요."))
    S.append((slide_cta(), "단지별 분양가와 역까지 거리는 청약콕에서 한 번에 확인하세요."))
    names = [plain(x["n"]) for _, x in top]
    meta = {
        "title": f"이번 주 아파트 청약 {len(rows)}곳 ({mon.month}/{mon.day}~{sun.month}/{sun.day})",
        "desc": (f"{mon.month}월 {mon.day}일~{sun.month}월 {sun.day}일 청약 접수 {len(rows)}곳 정리. "
                 f"세대수 상위: {', '.join(names)}. 단지별 분양가·역 거리·일정은 네이버에서 '청약콕' 검색."),
        "tags": ["#청약", "#아파트청약", "#청약일정", "#분양정보", "#청약콕"]
               + [f"#{short_region(x['a'])}청약" for _, x in top][:3],
    }
    return S, meta


def build(today):
    data = json.loads((ROOT / "data" / "blogdata.json").read_text(encoding="utf-8"))
    p = plan(data["items"], today)
    if not p:
        print("이번 주 접수 단지 없음")
        return None
    S, meta = p
    work = OUT / f"_work-{today.isoformat()}"
    work.mkdir(parents=True, exist_ok=True)
    segs = []
    for i, (img, text) in enumerate(S):
        ip, ap, vp = work / f"s{i}.png", work / f"s{i}.mp3", work / f"s{i}.mp4"
        img.save(ip)
        if not ap.exists():
            tts(text, ap)
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(ip), "-i", str(ap),
             "-filter_complex", "[1:a]adelay=300|300,apad=pad_dur=0.6,pan=stereo|c0=c0|c1=c0,"
             "loudnorm=I=-14:TP=-1.5,aresample=44100[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", str(vp)])
        segs.append(vp)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    out = OUT / f"cy-{today.isoformat()}-weekly.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])
    meta["script"] = [t for _, t in S]
    (OUT / f"cy-{today.isoformat()}-weekly.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("완성:", out)
    return out


if __name__ == "__main__":
    a = sys.argv
    day = dt.date.fromisoformat(a[a.index("--date") + 1]) if "--date" in a else dt.datetime.now(bp.KST).date()
    if "auto" in a and day.weekday() != 0:
        print("clip: not Monday KST, skip")
    else:
        build(day)
