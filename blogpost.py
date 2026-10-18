"""네이버 블로그(insight_archive77) '청약·분양 정보' 카테고리 글 자동 작성 → 청약콕 단지 페이지로 유입.
(2026-10-11) 사용: python blogpost.py [weekly|picks|auto] [--out DIR]
- weekly (한국 월요일): 이번 주 청약 접수 일정 총정리 표 + 당첨 발표 일정
- picks  (한국 목요일): 다음 열흘 안에 접수하는 큰 단지 3곳 — 분양가·평당가·역 거리·일정
- 사실은 청약콕 빌드가 남긴 data/blogdata.json(청약홈 공공데이터) 값만 쓰고, 평가·추천 문장은 쓰지 않음
- 결과: pgodrl77/naver-blog/queue_cy/cy-YYYY-MM-DD-<kind>.json (daily.py --queue queue_cy 가 발행)
"""
import datetime as dt, html, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT.parent / "pgodrl77" / "naver-blog" / "queue_cy"
KST = dt.timezone(dt.timedelta(hours=9))
WD = "월화수목금토일"
CAT = "청약·분양 정보"
RCPT = ("sp", "r1")  # 특별공급·1순위·청약 접수


def e(s):
    return html.escape(str(s or ""))


def md(v):
    return f"{v.month}월 {v.day}일({WD[v.weekday()]})"


def evs(x):
    return [(dt.date.fromisoformat(a), t, lab) for a, t, lab in x["ev"]]


def link(x, text=None):
    return f'<a href="{x["u"]}" target="_blank">{e(text or x["n"])}</a>'


def walk(m):
    return f"{m:,}m(도보 약 {max(1, round(m / 67))}분)" if m < 1000 else f"{m / 1000:.1f}km"


def foot():
    return ('<p>단지 이름을 누르면 <b>청약콕</b>에서 주택형별 분양가, 경쟁률, 가까운 역·학교 거리, '
            '내 캘린더에 일정 추가까지 한 번에 볼 수 있어요. 내 청약 가점이 궁금하면 '
            '<a href="https://cheongyakkok.com/calc.html" target="_blank">청약 가점 계산기</a>로 1분이면 확인됩니다.</p>'
            '<p>일정은 공고 정정으로 바뀔 수 있으니, 청약 전에는 청약홈 입주자모집공고 원문을 꼭 확인하세요.</p>')


def calcbox():
    # 2026-10-18 주 3회 결정형 개편: 첫 문단 바로 뒤 "내 숫자로 계산" 버튼(청약콕 가점 계산기)
    return ('<p><b>내 숫자로 바로 계산해 보기</b><br>'
            '<a href="https://cheongyakkok.com/calc.html" target="_blank">청약 가점 계산기 — 무주택 기간·부양가족·통장 기간 넣고 내 가점 1분 확인</a><br>'
            '단지 이름을 눌러 나오는 청약콕 단지 페이지의 경쟁률·당첨 가점 결과와 비교하면 넣어 볼 만한 곳인지 판단하기 쉬워요.</p>')


def weekly(items, today):
    mon = today - dt.timedelta(days=today.weekday())
    sun = mon + dt.timedelta(days=6)
    rows, wins = [], []
    for x in items:
        ev = evs(x)
        rc = sorted(v for v, t, _ in ev if t in RCPT and mon <= v <= sun)
        if rc:
            rows.append((rc[0], x))
        w = [v for v, t, _ in ev if t == "win" and mon <= v <= sun]
        if w:
            wins.append((w[0], x))
    if not rows:
        return None
    rows.sort(key=lambda r: (r[0], -(int(r[1].get("hh") or 0))))
    wins.sort(key=lambda r: r[0])
    apt = [x for _, x in rows if x["p"] == "apt"]
    hh = sum(int(x.get("hh") or 0) for _, x in rows)
    title = f"이번 주 아파트 청약 일정 총정리 ({mon.month}월 {mon.day}일~{sun.month}월 {sun.day}일)"
    big = max((x for _, x in rows), key=lambda x: int(x.get("hh") or 0))
    h = [f'<p>이번 주({md(mon)}~{md(sun)})에 청약 접수를 받는 곳은 <b>{len(rows)}곳</b>이에요. '
         f'일반 분양 아파트가 {len(apt)}곳이고, 나머지는 무순위·잔여세대 같은 줍줍 물량입니다. '
         f'공급 세대가 가장 많은 곳은 {link(big)}({e(big["a"])}, 총 {e(big.get("hh"))}세대)예요.</p>',
         calcbox(), f'<p>작성일 {today.isoformat()}</p>',
         '<h3>이번 주 청약 접수 단지</h3>',
         '<table><tr><th>접수 시작</th><th>단지</th><th>지역</th><th>유형</th><th>세대수</th><th>평당 분양가</th></tr>']
    for v, x in rows:
        h.append(f'<tr><td>{md(v)}</td><td>{link(x)}</td><td>{e(x["a"])}</td><td>{e(x["k"])}</td>'
                 f'<td>{e(x.get("hh") or "-")}</td><td>{(format(x["ppp"], ",") + "만원") if x.get("ppp") else "-"}</td></tr>')
    h.append('</table><p>※ 평당 분양가는 주택형별 최고 분양가를 공급면적(3.3㎡) 기준으로 나눈 평균이에요.</p>')
    if wins:
        h.append('<h3>이번 주 당첨자 발표</h3><table><tr><th>발표일</th><th>단지</th><th>지역</th></tr>')
        for v, x in wins:
            h.append(f'<tr><td>{md(v)}</td><td>{link(x)}</td><td>{e(x["a"])}</td></tr>')
        h.append('</table><p>당첨 여부는 발표일에 청약홈에서 확인할 수 있어요.</p>')
    h.append(foot())
    regions = list(dict.fromkeys(x["rg"] for _, x in rows))[:4]
    tags = ["청약일정", "아파트청약", "이번주청약", "분양정보", "청약홈", "청약콕"] + [f"{r}청약" for r in regions]
    return {"title": title, "category": CAT, "tags": tags[:10], "blocks": [{"html": "".join(h)}]}


def picks(items, today):
    cand = []
    for x in items:
        if x["p"] != "apt" or not x.get("hh"):
            continue
        rc = sorted(v for v, t, _ in evs(x) if t in RCPT and today <= v <= today + dt.timedelta(days=10))
        if rc:
            cand.append((int(x["hh"]), rc[0], x))
    if not cand:
        return None
    cand.sort(key=lambda c: -c[0])
    top = cand[:3]
    names = ", ".join(c[2]["n"] for c in top)
    title = f"다음 주 청약 큰 단지 {len(top)}곳 분양가·입지 정리 ({today.month}월 {today.day}일 기준)"
    h = [f'<p>앞으로 열흘 안에 청약 접수를 시작하는 일반 분양 아파트 가운데 공급 세대가 많은 {len(top)}곳을 골라 '
         f'분양가와 입지를 숫자로 정리했어요. 대상은 {e(names)}입니다.</p>', calcbox(), f'<p>작성일 {today.isoformat()}</p>']
    for i, (n, start, x) in enumerate(top, 1):
        ev = sorted(evs(x))
        h.append(f'<h3>{i}. {link(x)}</h3>')
        lines = [f'<b>위치</b> {e(x["a"])} · 총 {n:,}세대' + (f' · 시공 {e(x["bd"])}' if x.get("bd") else ""),
                 f'<b>청약 일정</b> ' + " · ".join(f"{lab} {md(v)}" for v, _t, lab in ev if v >= today)]
        if x.get("pr"):
            lines.append(f'<b>분양가</b> {e(x["pr"])} (주택형별 최고가 기준)')
        if x.get("ppp"):
            s = f'<b>평당 분양가</b> {x["ppp"]:,}만원'
            if x.get("ravg"):
                diff = (x["ppp"] - x["ravg"]) / x["ravg"] * 100
                s += f' · 최근 {e(x["rg"])} 공고 평균 {x["ravg"]:,}만원보다 {abs(diff):.0f}% {"높음" if diff > 0 else "낮음"}'
            lines.append(s)
        loc = x.get("loc") or {}
        if loc.get("subway"):
            s0 = loc["subway"][0]
            lines.append(f'<b>가까운 역</b> {e(s0["name"])} 직선 {walk(s0["m"])}')
        if loc.get("elem"):
            lines.append(f'<b>가까운 초등학교</b> {e(loc["elem"][0]["name"])} 직선 {walk(loc["elem"][0]["m"])}')
        if x.get("mv"):
            lines.append(f'<b>입주 예정</b> {e(x["mv"])}')
        h.append("<p>" + "<br>".join(lines) + "</p>")
        h.append(f'<p>{link(x, x["n"] + " 주택형별 분양가·경쟁률 자세히 보기")}</p>')
    h.append('<p>거리는 단지 주소 기준 직선거리라 실제 걷는 거리는 더 길 수 있고, 배정 학교는 교육청 학구도로 확인해야 해요.</p>')
    h.append(foot())
    regions = list(dict.fromkeys(c[2]["rg"] for c in top))
    tags = ["청약", "분양가", "아파트분양", "청약일정", "신규분양", "청약콕"] + [f"{r}분양" for r in regions] + [c[2]["n"].split()[0] for c in top]
    return {"title": title, "category": CAT, "tags": list(dict.fromkeys(tags))[:10], "blocks": [{"html": "".join(h)}]}


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "auto"
    today = dt.datetime.now(KST).date()
    if kind == "auto":
        kind = {0: "weekly", 3: "picks"}.get(today.weekday(), "weekly" if "--force" in sys.argv else None)
        if not kind:
            print("오늘은 청약 글 쓰는 날이 아님(한국 월·목)")
            return
    data = json.loads((ROOT / "data" / "blogdata.json").read_text(encoding="utf-8"))
    post = (weekly if kind == "weekly" else picks)(data["items"], today)
    if not post:
        print("쓸 단지 없음:", kind)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"cy-{today.isoformat()}-{kind}.json"
    p.write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
    print("작성:", p.name, post["title"])


if __name__ == "__main__":
    main()
