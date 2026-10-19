"""청약콕 카드뉴스 릴스 (2026-10-19, 사용자 지시 "혜택 한 장처럼 카드 뉴스를 만들어서 게시").

혜택 한 장 릴스와 같은 형식: 1080x1920 · 15초 · 장면 4개(표지 → 분양가 → 일정/경쟁률 → 행동 유도),
장면마다 제목이 먼저 뜨고 내용이 이어서 나타나며, 위쪽 진행 막대가 차오른다. 배경음 static/reel_bgm.m4a.

원료는 이미 만든 단지 페이지(site/apt/<slug>.html)의 숫자만 쓴다 — 페이지에 없는 숫자는 만들지 않는다.
사용: python reel.py <slug> <winner|result|open> <출력.mp4> [YYYY-MM-DD]
빌드에서는 threads_queue.write 가 make() 를 부른다(실패해도 빌드는 계속).
"""
import datetime as dt, html, json, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent
W, H = 1080, 1920
BGM = ROOT / "static" / "reel_bgm.m4a"
FONT = "'Pretendard','Noto Sans KR','Malgun Gothic','맑은 고딕',sans-serif"
C = dict(bg="#F2F6FE", fg="#0E1B38", blue="#1D63DB", soft="#5B6B8C", card="#FFFFFF", line="#D9E3F5", hot="#E8590C")
KIND_LABEL = {"winner": "오늘 당첨자 발표", "result": "1순위 경쟁률 결과", "open": "오늘 청약 접수 시작"}
WD = "월화수목금토일"


# ---------------- 단지 페이지 읽기 ----------------
def page_lines(path):
    t = pathlib.Path(path).read_text(encoding="utf-8")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
    t = re.sub(r"<(tr|br|p|div|h\d|li|dt|dd)[^>]*>", "\n", t)
    t = re.sub(r"<t[dh][^>]*>", " | ", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return [ln.strip() for ln in t.split("\n") if ln.strip()]


def section(lines, start, stops):
    try:
        i = lines.index(start)
    except ValueError:
        return []
    out = []
    for ln in lines[i + 1:]:
        if any(ln.startswith(s) for s in stops):
            break
        out.append(ln)
    return out


def parse(path):
    L = page_lines(path)
    d = {"name": "", "place": "", "kind": "", "glance": {}, "sched": [], "types": [], "region_cmp": ""}
    for i, ln in enumerate(L):
        if " · 공고일 " in ln and not d["place"]:
            parts = [p.strip() for p in ln.split("·")]
            d["place"], d["kind"] = parts[0], (parts[1] if len(parts) > 2 else "")
            m = re.match(r"(.+?) 청약 일정", L[i - 1]) if i else None
            if m:
                d["name"] = m.group(1)
    g = section(L, "한눈에 보기", ("내 가점으로", "청약 일정", "더샵", "이 단지"))
    for k, v in zip(g[0::2], g[1::2]):
        if not d["glance"].get(k):
            d["glance"][k] = v
    s = section(L, "청약 일정", ("내 캘린더",))
    for k, v in zip(s[0::2], s[1::2]):
        if re.search(r"\d{4}\.\d{2}\.\d{2}|\d{4}년", v):
            d["sched"].append((k, v))
    for ln in section(L, "주택형별 분양가", ("자금 계획",)):
        cells = [c.strip() for c in ln.split("|") if c.strip()]
        if len(cells) >= 6 and "㎡" in cells[0] and "원" in cells[4]:
            d["types"].append({"ty": short_ty(cells[0]), "price": cells[4], "py": cells[5]})
    for ln in L:
        m = re.search(r"평균\(([\d,]+만원)\)보다 ([\d.]+% (?:높|낮)습니다)", ln)
        if m and "평당 분양가" in ln:
            reg = re.search(r"동안 (\S+)에서", ln)
            d["region_cmp"] = f"{reg.group(1) if reg else '지역'} 평균보다 {m.group(2).replace('습니다', '아요')}"
            break
    return d


def short_ty(s):
    # "85㎡ 084.9800A" → "85㎡ A",  "107㎡ 106.9500A" → "107㎡ A", "103㎡ 102.8500" → "103㎡"
    m = re.match(r"(\d+㎡)\s*[\d.]*([A-Z]*)", s)
    return (m.group(1) + (" " + m.group(2) if m and m.group(2) else "")) if m else s


def man(v):
    """'9억 5,400만원' → 95400 (만원 단위), 실패하면 None"""
    m = re.match(r"(?:(\d+)억)?\s*([\d,]+)?만?원?", v.replace(" ", ""))
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 10000 + int((m.group(2) or "0").replace(",", ""))


def md(s, today=None):
    """'2026.10.19' → '10월 19일(월)'"""
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", s)
    if not m:
        return s
    day = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return f"{day.month}월 {day.day}일({WD[day.weekday()]})", day


# ---------------- 장면 HTML ----------------
CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px}}
body{{font-family:{FONT};background:{C['bg']};color:{C['fg']};position:relative;overflow:hidden;word-break:keep-all;letter-spacing:-0.03em}}
.glow{{position:absolute;right:-220px;top:-260px;width:760px;height:760px;border-radius:50%;
 background:radial-gradient(circle,rgba(29,99,219,.22),rgba(29,99,219,0) 68%)}}
.top{{position:absolute;left:72px;right:72px;top:70px;display:flex;align-items:center;gap:18px;font-size:30px;font-weight:700;color:{C['soft']}}}
.chipb{{background:{C['blue']};color:#fff;font-weight:900;padding:8px 18px;border-radius:10px}}
.track{{position:absolute;left:72px;right:72px;top:132px;height:8px;border-radius:4px;background:{C['line']}}}
.k{{display:inline-block;background:{C['fg']};color:#fff;font-size:34px;font-weight:800;padding:12px 24px;border-radius:12px}}
.k.b{{background:{C['blue']}}}
.title{{font-size:104px;line-height:1.16;font-weight:900;margin-top:34px}}
.sub{{font-size:44px;line-height:1.45;font-weight:600;color:{C['soft']};margin-top:30px}}
.big{{font-size:150px;font-weight:900;color:{C['blue']};line-height:1;margin-top:70px}}
.big small{{font-size:64px;color:{C['fg']};margin-left:12px}}
.note{{font-size:36px;line-height:1.5;color:{C['soft']};margin-top:28px;font-weight:600}}
.wrap{{position:absolute;left:72px;right:72px;top:380px}}
.rows{{display:flex;flex-direction:column;gap:26px;margin-top:56px}}
.row{{background:{C['card']};border-radius:26px;padding:30px 38px;box-shadow:0 6px 24px rgba(14,27,56,.07)}}
.row .l{{display:flex;justify-content:space-between;align-items:baseline;font-size:46px;font-weight:800}}
.row .l span:last-child{{color:{C['blue']}}}
.bar{{height:18px;border-radius:9px;background:{C['line']};margin-top:18px;overflow:hidden}}
.bar i{{display:block;height:100%;background:{C['fg']};border-radius:9px}}
.row.hot{{outline:5px solid {C['blue']}}}
.row.hot .l span:first-child::after{{content:' 오늘';color:#fff;background:{C['hot']};font-size:30px;padding:4px 12px;border-radius:8px;margin-left:14px;vertical-align:middle}}
.cta{{position:absolute;left:72px;right:72px;bottom:250px;background:{C['fg']};color:#fff;border-radius:30px;padding:44px 40px;text-align:center}}
.cta b{{display:block;font-size:52px;font-weight:900}}
.cta span{{display:block;font-size:34px;color:#C9D6EE;margin-top:12px}}
.foot{{position:absolute;left:72px;right:72px;bottom:120px;font-size:28px;color:{C['soft']};line-height:1.5}}
.hide{{visibility:hidden}}
"""


def frame(inner, foot=""):
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f"<div class='glow'></div><div class='top'><span class='chipb'>청약콕</span><span>cheongyakkok.com</span></div>"
            f"<div class='track'></div><div class='wrap'>{inner}</div>{foot}</body></html>")


def e(s):
    return html.escape(str(s or ""))


def rows_html(items, hide=False):
    return "<div class='rows%s'>%s</div>" % (" hide" if hide else "", "".join(items))


def price_rows(d):
    ts = d["types"][:4]
    vals = [man(t["price"]) or 0 for t in ts]
    mx = max(vals) if vals else 1
    out = []
    for t, v in zip(ts, vals):
        pct = max(18, round(100 * v / mx)) if mx else 50
        out.append(f"<div class='row'><div class='l'><span>{e(t['ty'])}</span><span>{e(t['price'])}</span></div>"
                   f"<div class='bar'><i style='width:{pct}%'></i></div></div>")
    return out


def sched_rows(d, today):
    keep = ("특별공급", "1순위", "2순위", "청약 접수", "당첨자 발표", "계약", "입주")
    out = []
    for k, v in d["sched"]:
        if not k.startswith(keep) or (k == "청약 접수" and any(x.startswith("1순위") for x, _ in d["sched"])):
            continue
        r = md(v)
        label, day = (r if isinstance(r, tuple) else (v, None))
        if "~" in v and day:
            label += " ~"
        hot = " hot" if day == today else ""
        out.append(f"<div class='row{hot}'><div class='l'><span>{e(k)}</span><span>{e(label)}</span></div></div>")
    return out[:5]


def scenes(d, kind, today):
    g = d["glance"]
    name = d["name"]
    place = " · ".join(x for x in (d["place"], d["kind"]) if x)
    rng = g.get("분양가(최고가 기준)", "")
    low = rng.split("~")[0].strip() if rng else ""
    supply = g.get("공급", "")
    rate = g.get("경쟁률", "")
    score = g.get("당첨 가점", "")

    # 1. 표지
    if kind in ("winner", "result") and rate:
        m = re.match(r"평균 ([\d.]+) : 1", rate)
        stat = f"{m.group(1)}<small>: 1</small>" if m else e(rate)
        statnote = "1순위 평균 경쟁률"
    else:
        n = re.sub(r"[^\d,]", "", supply)
        n = f"{int(n.replace(',', '')):,}" if n.replace(",", "").isdigit() else n
        stat, statnote = (f"{n}<small>세대</small>", f"총 공급 · 분양가 {low}부터" if low else "총 공급") if n else ("", "")
    cov = (f"<span class='k b'>{e(KIND_LABEL.get(kind, '청약 소식'))}</span>"
           f"<div class='title'>{e(name)}</div><div class='sub'>{e(place)}</div>")
    s1a = frame(cov + f"<div class='hide'><div class='big'>{stat}</div></div>")
    s1b = frame(cov + (f"<div class='big'>{stat}</div><div class='note'>{e(statnote)}</div>" if stat else ""))

    # 2. 분양가
    py = g.get("평당 분양가", "")
    pnote = " · ".join(x for x in (f"평당 {py}" if py else "", d["region_cmp"]) if x)
    head2 = "<span class='k'>얼마예요?</span><div class='title' style='font-size:88px'>주택형별<br>최고 분양가</div>"
    pr = price_rows(d)
    s2a = frame(head2 + rows_html(pr, True))
    s2b = frame(head2 + rows_html(pr) + (f"<div class='note'>{e(pnote)}</div>" if pnote else ""))

    # 3. 일정 또는 경쟁률·가점
    if kind in ("winner", "result") and score:
        head3 = "<span class='k'>몇 점에 붙었나?</span><div class='title' style='font-size:88px'>당첨 가점<br>커트라인</div>"
        m = re.match(r"최저 (\d+)점(.*?)(?:· 최고 (\d+)점)?$", score)
        body3 = (f"<div class='big'>{m.group(1)}<small>점부터</small></div>"
                 f"<div class='note'>{e(('가장 낮은 당첨 점수' + m.group(2)).strip())}{' · 최고 ' + m.group(3) + '점' if m.group(3) else ''}</div>") if m else f"<div class='sub'>{e(score)}</div>"
    else:
        head3 = ("<span class='k'>언제 넣나요?</span><div class='title' style='font-size:88px'>청약 일정</div>" if kind == "open"
                 else "<span class='k'>당첨됐다면</span><div class='title' style='font-size:88px'>다음 일정</div>")
        rows = sched_rows(d, today)
        if kind != "open":
            rows = [r for r in rows if ("계약" in r or "입주" in r or "발표" in r)] or rows
        body3 = rows_html(rows)
    s3a = frame(head3 + f"<div class='hide'>{body3}</div>")
    s3b = frame(head3 + body3)

    # 4. 행동 유도
    if kind == "open":
        big4, small4 = "내 가점으로<br><span style='color:%s'>될까?</span>" % C["blue"], "청약콕 가점 계산기로 1분이면 확인해요"
        btn = ("저장해 두고 접수일에 꺼내 보세요", "일정·분양가·평당가 한 페이지 정리 → cheongyakkok.com")
    else:
        big4, small4 = "당첨 확인은<br><span style='color:%s'>청약홈</span>에서" % C["blue"], "주택형별 경쟁률·커트라인은 청약콕에 정리했어요"
        btn = ("다음 청약 준비는 저장부터", "이번 주 청약 일정 → cheongyakkok.com")
    foot = f"<div class='foot'>출처: 한국부동산원 청약홈 분양정보 · {today.month}월 {today.day}일 기준<br>청약 전 입주자모집공고 원문을 꼭 확인하세요</div>"
    s4 = frame(f"<div class='title' style='margin-top:200px'>{big4}</div><div class='sub'>{e(small4)}</div>",
               f"<div class='cta'><b>{e(btn[0])}</b><span>{e(btn[1])}</span></div>{foot}")
    return [(s1a, 1.1), (s1b, 2.5), (s2a, 0.8), (s2b, 3.2), (s3a, 0.8), (s3b, 3.1), (s4, 3.5)]


# ---------------- 렌더 ----------------
def render(scs, out_mp4):
    from playwright.sync_api import sync_playwright
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="cyreel_"))
    pngs = []
    with sync_playwright() as p:
        b = None
        for ch in ("msedge", "chrome", None):  # 설치된 Edge/크롬 사용(플레이라이트 브라우저 내려받기 불필요)
            try:
                b = p.chromium.launch(channel=ch) if ch else p.chromium.launch()
                break
            except Exception:
                continue
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, (h, _) in enumerate(scs):
            pg.set_content(h)
            pg.wait_for_timeout(120)
            f = tmp / f"s{i}.png"
            pg.screenshot(path=str(f))
            pngs.append(f)
        b.close()
    X = 0.25  # 장면 사이 겹침(크로스페이드)
    durs = [d for _, d in scs]
    total = sum(durs)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for f, d in zip(pngs, durs):
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{d + X:.2f}", "-i", str(f)]
    fc, last, off = [], "[0:v]", 0.0
    for i in range(1, len(pngs)):
        off += durs[i - 1]
        fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={X}:offset={off:.2f}[x{i}]")
        last = f"[x{i}]"
    n = len(pngs)
    fc.append(f"color=c=0x1D63DB:s=936x8:r=30:d={total:.2f}[bar]")
    fc.append(f"{last}[bar]overlay=x='72-936+936*t/{total:.2f}':y=132:shortest=1,format=yuv420p[v]")
    if BGM.exists():
        cmd += ["-stream_loop", "-1", "-i", str(BGM)]
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]"]
    if BGM.exists():
        cmd += ["-map", f"{n}:a", "-af", f"volume=0.8,afade=t=out:st={total - 1.2:.2f}:d=1.2", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-t", f"{total:.2f}", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)]
    subprocess.run(cmd, check=True)
    cover = pathlib.Path(out_mp4).with_suffix(".jpg")
    from PIL import Image
    Image.open(pngs[1]).convert("RGB").save(cover, "JPEG", quality=90)
    shutil.rmtree(tmp, ignore_errors=True)
    return cover


def make(slug, kind, out_mp4, today=None, site=ROOT / "site"):
    today = today or dt.date.today()
    d = parse(site / "apt" / f"{slug}.html")
    if not d["name"] or not d["types"]:
        raise ValueError(f"단지 페이지에서 이름·분양가를 못 읽음: {slug}")
    out_mp4 = pathlib.Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cover = render(scenes(d, kind, today), out_mp4)
    return {"video": str(out_mp4), "cover": str(cover), "name": d["name"]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    day = dt.date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 else dt.date.today()
    print(json.dumps(make(sys.argv[1], sys.argv[2], sys.argv[3], day), ensure_ascii=False))
