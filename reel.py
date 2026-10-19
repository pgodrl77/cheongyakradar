"""청약콕 카드뉴스 릴스 (2026-10-19, 사용자 지시 "혜택 한 장처럼 카드 뉴스를 만들어서 게시").

혜택 한 장 릴스와 같은 형식: 1080x1920 · 15초 · 장면 4개(표지 → 분양가 → 일정/가점 → 청약콕 유입),
장면 안 글자·줄이 하나씩 올라오고, 분양가 막대가 차오르고, 큰 숫자는 0부터 세어 올라간다(30fps 프레임 렌더).
위쪽 진행 막대, 배경 빛 번짐이 계속 움직여 정지 화면이 없다. 배경음 static/reel_bgm.m4a.
2026-10-19 사용자 지적 "왜 청약홈이야?" — 마지막 장면은 청약콕 주소·프로필 링크만 내세우고, 청약홈은 출처 줄에만 둔다.

원료는 이미 만든 단지 페이지(site/apt/<slug>.html)의 숫자만 쓴다 — 페이지에 없는 숫자는 만들지 않는다.
사용: python reel.py <slug> <winner|result|open> <출력.mp4> [YYYY-MM-DD]
빌드에서는 threads_queue.write 가 make() 를 부른다(실패해도 빌드는 계속).
"""
import datetime as dt, html, json, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent
W, H, FPS, T = 1080, 1920, 30, 15.0
BGM = ROOT / "static" / "reel_bgm.m4a"
FONT = "'Pretendard','Noto Sans KR','Malgun Gothic','맑은 고딕',sans-serif"
C = dict(bg="#F2F6FE", fg="#0E1B38", blue="#1D63DB", soft="#5B6B8C", card="#FFFFFF", line="#D9E3F5", hot="#E8590C")
KIND_LABEL = {"winner": "오늘 당첨자 발표", "result": "1순위 경쟁률 결과", "open": "오늘 청약 접수 시작"}
WD = "월화수목금토일"
SCENES = [(0.0, 3.6), (3.6, 7.6), (7.6, 11.4), (11.4, T)]


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
    m = re.match(r"(\d+㎡)\s*[\d.]*([A-Z]*)", s)
    return (m.group(1) + (" " + m.group(2) if m and m.group(2) else "")) if m else s


def man(v):
    """'9억 5,400만원' → 95400 (만원 단위), 실패하면 None"""
    m = re.match(r"(?:(\d+)억)?\s*([\d,]+)?만?원?", v.replace(" ", ""))
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 10000 + int((m.group(2) or "0").replace(",", ""))


def md(s):
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", s)
    if not m:
        return s, None
    day = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return f"{day.month}월 {day.day}일({WD[day.weekday()]})", day


def e(s):
    return html.escape(str(s or ""))


# ---------------- 장면 HTML (움직임은 아래 JS R(t) 가 프레임마다 계산) ----------------
CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px}}
body{{font-family:{FONT};background:{C['bg']};color:{C['fg']};position:relative;overflow:hidden;word-break:keep-all;letter-spacing:-0.03em}}
#glow{{position:absolute;right:-240px;top:-260px;width:820px;height:820px;border-radius:50%;
 background:radial-gradient(circle,rgba(29,99,219,.26),rgba(29,99,219,0) 68%)}}
#glow2{{position:absolute;left:-300px;bottom:-320px;width:760px;height:760px;border-radius:50%;
 background:radial-gradient(circle,rgba(29,99,219,.12),rgba(29,99,219,0) 70%)}}
.top{{position:absolute;left:72px;right:72px;top:66px;display:flex;align-items:center;gap:18px;font-size:38px;font-weight:800;color:{C['blue']}}}
.chipb{{background:{C['blue']};color:#fff;font-weight:900;padding:8px 20px;border-radius:12px}}
.track{{position:absolute;left:72px;right:72px;top:140px;height:10px;border-radius:5px;background:{C['line']};overflow:hidden}}
#bar{{height:100%;width:0;background:{C['blue']};border-radius:5px}}
.scene{{position:absolute;left:72px;right:72px;top:360px;bottom:0;display:none}}
.k{{display:inline-block;background:{C['fg']};color:#fff;font-size:36px;font-weight:800;padding:12px 26px;border-radius:14px}}
.k.b{{background:{C['blue']}}}
.title{{font-size:106px;line-height:1.16;font-weight:900;margin-top:34px}}
.h2{{font-size:90px;line-height:1.16;font-weight:900;margin-top:30px}}
.sub{{font-size:46px;line-height:1.45;font-weight:600;color:{C['soft']};margin-top:30px}}
.big{{font-size:170px;font-weight:900;color:{C['blue']};line-height:1;margin-top:80px;transform-origin:left bottom}}
.big small{{font-size:68px;color:{C['fg']};margin-left:12px}}
.note{{font-size:38px;line-height:1.5;color:{C['soft']};margin-top:30px;font-weight:600}}
.rows{{display:flex;flex-direction:column;gap:26px;margin-top:56px}}
.row{{background:{C['card']};border-radius:26px;padding:32px 40px;box-shadow:0 6px 24px rgba(14,27,56,.07)}}
.row .l{{display:flex;justify-content:space-between;align-items:baseline;font-size:48px;font-weight:800}}
.row .l>span:last-child{{color:{C['blue']}}}
.barw{{height:20px;border-radius:10px;background:{C['line']};margin-top:18px;overflow:hidden}}
.barw i{{display:block;height:100%;width:0;background:{C['fg']};border-radius:10px}}
.row.hot{{outline:6px solid {C['blue']}}}
.tag{{color:#fff;background:{C['hot']};font-size:30px;padding:4px 12px;border-radius:8px;margin-left:14px;vertical-align:middle}}
.url{{margin-top:70px;background:{C['blue']};color:#fff;border-radius:34px;padding:50px 40px;text-align:center}}
.url b{{display:block;font-size:84px;font-weight:900;letter-spacing:-0.02em}}
.url span{{display:block;font-size:40px;margin-top:16px;color:#DCE7FF;font-weight:700}}
.save{{margin-top:40px;font-size:42px;font-weight:800;text-align:center}}
.foot{{position:absolute;left:72px;right:72px;bottom:110px;font-size:28px;color:{C['soft']};line-height:1.5}}
"""

JS = """
const T=%(T)s;
function ez(x){x=Math.min(1,Math.max(0,x));return 1-Math.pow(1-x,3)}
function R(t){
  document.querySelectorAll('.scene').forEach(s=>{const a=+s.dataset.s,b=+s.dataset.e;
    let o=(t<a||t>b)?0:Math.min(1,(t-a)/0.3,(b>=T-0.01)?1:(b-t)/0.3);
    s.style.display=o>0?'block':'none';s.style.opacity=o;});
  document.querySelectorAll('[data-t]').forEach(el=>{const p=ez((t-(+el.dataset.t))/0.55),fx=el.dataset.fx||'up';
    if(fx==='up'){el.style.opacity=p;el.style.transform='translateY('+((1-p)*70)+'px)';}
    else if(fx==='left'){el.style.opacity=p;el.style.transform='translateX('+((1-p)*-90)+'px)';}
    else if(fx==='pop'){el.style.opacity=p;el.style.transform='scale('+(0.55+0.45*p)+')';}
    else if(fx==='grow'){el.style.width=(ez((t-(+el.dataset.t))/0.9)*(+el.dataset.w))+'%';}
    else if(fx==='count'){const q=ez((t-(+el.dataset.t))/1.1),v=+el.dataset.v,dc=+(el.dataset.dec||0);
      el.textContent=(v*q).toLocaleString('ko-KR',{minimumFractionDigits:dc,maximumFractionDigits:dc});}
  });
  document.querySelectorAll('.breathe').forEach(el=>{if(el.style.opacity==='1'||!el.dataset.t)
    el.style.transform='scale('+(1+0.025*Math.sin(t*3.2))+')';});
  document.getElementById('bar').style.width=(t/T*100)+'%';
  document.getElementById('glow').style.transform='translate('+(Math.sin(t*0.7)*60)+'px,'+(Math.cos(t*0.55)*45)+'px)';
  document.getElementById('glow2').style.transform='translate('+(Math.cos(t*0.5)*50)+'px,'+(Math.sin(t*0.6)*40)+'px)';
}
""".replace("%(T)s", str(T))


def A(t, fx="up", **kw):
    """움직임 속성: data-t(등장 시각) data-fx(효과)"""
    extra = "".join(f" data-{k}='{v}'" for k, v in kw.items())
    return f" data-t='{t:.2f}' data-fx='{fx}'{extra}"


def big_count(text, t0):
    """'1,128' → 0부터 세는 숫자, '9.09' → 소수 둘째자리까지"""
    raw = text.replace(",", "")
    try:
        float(raw)
    except ValueError:
        return e(text)
    dec = len(raw.split(".")[1]) if "." in raw else 0
    return f"<span{A(t0, 'count', v=raw, dec=dec)}>0</span>"


def scenes_html(d, kind, today):
    g = d["glance"]
    s1, s2, s3, s4 = SCENES
    place = " · ".join(x for x in (d["place"], d["kind"]) if x)
    rng = g.get("분양가(최고가 기준)", "")
    low = rng.split("~")[0].strip() if rng else ""
    supply = re.sub(r"[^\d,]", "", g.get("공급", ""))
    rate = g.get("경쟁률", "")
    score = g.get("당첨 가점", "")

    # 1. 표지 — 단지명이 올라오고, 큰 숫자(경쟁률 또는 세대수)가 0부터 세어 올라감
    a = s1[0]
    m = re.match(r"평균 ([\d.]+) : 1", rate) if kind in ("winner", "result") else None
    stat = unit = note = ""
    if m:
        stat, unit, note = m.group(1), ": 1", "1순위 평균 경쟁률"
    elif supply:
        stat, unit, note = supply, "세대", (f"총 공급 · 분양가 {low}부터" if low else "총 공급")
    p1 = (f"<span class='k b'{A(a + .1, 'pop')}>{e(KIND_LABEL.get(kind, '청약 소식'))}</span>"
          f"<div class='title'{A(a + .35)}>{e(d['name'])}</div><div class='sub'{A(a + .7)}>{e(place)}</div>")
    if stat:
        p1 += (f"<div class='big breathe'{A(a + 1.1, 'left')}>{big_count(stat, a + 1.1)}<small>{e(unit)}</small></div>"
               f"<div class='note'{A(a + 1.5)}>{e(note)}</div>")

    # 2. 분양가 — 줄이 하나씩 올라오고 막대가 차오름
    a = s2[0]
    ts = d["types"][:4]
    vals = [man(x["price"]) or 0 for x in ts]
    mx = max(vals) if vals else 1
    rows = ""
    for i, (x, v) in enumerate(zip(ts, vals)):
        ti = a + .7 + i * .35
        pct = max(18, round(100 * v / mx)) if mx else 50
        rows += (f"<div class='row'{A(ti)}><div class='l'><span>{e(x['ty'])}</span><span>{e(x['price'])}</span></div>"
                 f"<div class='barw'><i{A(ti + .2, 'grow', w=pct)}></i></div></div>")
    py = g.get("평당 분양가", "")
    pnote = " · ".join(x for x in (f"평당 {py}" if py else "", d["region_cmp"]) if x)
    p2 = (f"<span class='k'{A(a + .1, 'pop')}>얼마예요?</span><div class='h2'{A(a + .3)}>주택형별<br>최고 분양가</div>"
          f"<div class='rows'>{rows}</div>" + (f"<div class='note'{A(a + .9 + len(ts) * .35)}>{e(pnote)}</div>" if pnote else ""))

    # 3. 가점 커트라인(있으면) 또는 일정
    a = s3[0]
    sm = re.match(r"최저 (\d+)점(.*?)(?:· 최고 (\d+)점)?$", score) if score and kind in ("winner", "result") else None
    if sm:
        p3 = (f"<span class='k'{A(a + .1, 'pop')}>몇 점에 붙었나?</span><div class='h2'{A(a + .3)}>당첨 가점<br>커트라인</div>"
              f"<div class='big breathe'{A(a + .8, 'left')}>{big_count(sm.group(1), a + .8)}<small>점부터</small></div>"
              f"<div class='note'{A(a + 1.3)}>{e(('가장 낮은 당첨 점수' + sm.group(2)).strip())}"
              f"{' · 최고 ' + sm.group(3) + '점' if sm.group(3) else ''}</div>")
    else:
        keep = ("특별공급", "1순위", "2순위", "청약 접수", "당첨자 발표", "계약", "입주")
        has1 = any(k.startswith("1순위") for k, _ in d["sched"])
        items = []
        for k, v in d["sched"]:
            if not k.startswith(keep) or (k == "청약 접수" and has1):
                continue
            label, day = md(v)
            if "~" in v and day:
                label += " ~"
            items.append((k, label, day == today))
        if kind != "open":
            items = [x for x in items if x[0].startswith(("당첨자 발표", "계약", "입주"))] or items
        rows = "".join(
            f"<div class='row{' hot' if hot else ''}'{A(a + .7 + i * .3)}><div class='l'><span>{e(k)}"
            f"{'<span class=tag>오늘</span>' if hot else ''}</span><span>{e(lb)}</span></div></div>"
            for i, (k, lb, hot) in enumerate(items[:5]))
        head = ("언제 넣나요?", "청약 일정") if kind == "open" else ("당첨됐다면", "다음 일정")
        p3 = (f"<span class='k'{A(a + .1, 'pop')}>{head[0]}</span><div class='h2'{A(a + .3)}>{head[1]}</div>"
              f"<div class='rows'>{rows}</div>")

    # 4. 청약콕 유입 — 주소를 가장 크게, 청약홈은 출처 줄에만
    a = s4[0]
    if kind == "open":
        msg = "내 가점으로<br><span style='color:%s'>될까?</span>" % C["blue"]
        sub4 = "청약콕 가점 계산기로 1분이면 확인해요"
    else:
        msg = "경쟁률·커트라인<br><span style='color:%s'>청약콕</span>에 다 있어요" % C["blue"]
        sub4 = "주택형별 경쟁률 · 당첨 가점 · 평당가 한 페이지"
    p4 = (f"<div class='title' style='margin-top:120px'{A(a + .1)}>{msg}</div><div class='sub'{A(a + .45)}>{e(sub4)}</div>"
          f"<div class='url breathe'{A(a + .8, 'pop')}><b>cheongyakkok.com</b><span>프로필 링크 → 단지 이름 검색</span></div>"
          f"<div class='save'{A(a + 1.3)}>📌 저장해 두고 부모님·지인께 공유하세요</div>"
          f"<div class='foot' style='left:0;right:0;bottom:110px'>데이터: 한국부동산원 청약홈 분양정보 · "
          f"{today.month}월 {today.day}일 기준 · 청약 전 입주자모집공고 원문 확인</div>")

    body = "".join(f"<div class='scene' data-s='{s:.2f}' data-e='{en:.2f}'>{p}</div>"
                   for (s, en), p in zip(SCENES, (p1, p2, p3, p4)))
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f"<div id='glow'></div><div id='glow2'></div>"
            f"<div class='top'><span class='chipb'>청약콕</span><span>cheongyakkok.com</span></div>"
            f"<div class='track'><div id='bar'></div></div>{body}<script>{JS}</script></body></html>")


# ---------------- 렌더: 30fps 프레임 → mp4 ----------------
def launch(p):
    for ch in ("msedge", "chrome", None):  # 설치된 Edge/크롬 사용(플레이라이트 브라우저 내려받기 불필요)
        try:
            return p.chromium.launch(channel=ch) if ch else p.chromium.launch()
        except Exception:
            continue
    raise RuntimeError("브라우저 실행 실패")


def render(page_html, out_mp4):
    from playwright.sync_api import sync_playwright
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="cyreel_"))
    n = int(T * FPS)
    cover = pathlib.Path(out_mp4).with_suffix(".jpg")
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.set_content(page_html)
        pg.wait_for_timeout(300)
        for i in range(n):
            pg.evaluate(f"R({i / FPS:.4f})")
            pg.screenshot(path=str(tmp / f"f{i:04d}.jpg"), type="jpeg", quality=92)
        pg.evaluate("R(3.2)")
        pg.screenshot(path=str(cover), type="jpeg", quality=90)
        b.close()
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(tmp / "f%04d.jpg")]
    if BGM.exists():
        cmd += ["-stream_loop", "-1", "-i", str(BGM), "-map", "0:v", "-map", "1:a",
                "-af", f"volume=0.85,afade=t=in:d=0.4,afade=t=out:st={T - 1.2:.2f}:d=1.2", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-t", f"{T:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out_mp4)]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return cover


def make(slug, kind, out_mp4, today=None, site=ROOT / "site"):
    today = today or dt.date.today()
    d = parse(site / "apt" / f"{slug}.html")
    if not d["name"] or not d["types"]:
        raise ValueError(f"단지 페이지에서 이름·분양가를 못 읽음: {slug}")
    out_mp4 = pathlib.Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cover = render(scenes_html(d, kind, today), out_mp4)
    return {"video": str(out_mp4), "cover": str(cover), "name": d["name"]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    day = dt.date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 else dt.date.today()
    print(json.dumps(make(sys.argv[1], sys.argv[2], sys.argv[3], day), ensure_ascii=False))
