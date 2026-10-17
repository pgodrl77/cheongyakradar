"""발표일 자동 게시용 쓰레드 원고 (2026-10-17, AI 이사회 결정).

매일 빌드 때 '오늘 일이 있는 단지'를 골라 짧은 게시물 원고를 만든다.
  - 오늘 접수 시작 (특별공급·1순위)
  - 오늘 당첨자 발표
  - 1순위 경쟁률이 나온 단지 (접수 마감 1~2일 뒤, 경쟁률 데이터가 있을 때)
결과는 site/feeds/threads.json (공개 피드)과 posts/threads/<날짜>.json (보관)에 쓴다.
쓰레드 계정이 Metricool 에 연결되면 예약 작업이 이 피드를 읽어 하루 최대 3건 올린다.
"""
import json, pathlib, datetime as dt

MAX_POSTS = 3


def _first(r, keys, d):
    for k in keys:
        if d(r.get(k)):
            return d(r.get(k))
    return None


def make(items, today, d, site_url, cmp_summary, short_addr):
    posts = []
    for it in items:
        r = it["d"]
        name = (r.get("HOUSE_NM") or "").strip()
        if not name:
            continue
        url = f"{site_url}/apt/{it['slug']}.html"
        place = short_addr(r.get("HSSPLY_ADRES")) or it.get("region", "")
        start = _first(r, ("SPSPLY_RCEPT_BGNDE", "GNRL_RNK1_CRSPAREA_RCPTDE", "RCEPT_BGNDE", "SUBSCRPT_RCEPT_BGNDE"), d)
        win = d(r.get("PRZWNER_PRESNATN_DE"))
        rnk1_end = _first(r, ("GNRL_RNK1_ETC_AREA_ENDDE", "GNRL_RNK1_CRSPAREA_ENDDE"), d)
        cs = cmp_summary(it) if it.get("cmp") else None
        if win == today:
            posts.append({"kind": "winner", "prio": 1, "url": url,
                          "text": f"오늘 {name} 당첨자 발표날입니다.\n\n{place}\n당첨 확인은 청약홈에서, 주택형별 경쟁률과 당첨 가점 커트라인은 정리해 두었어요.\n\n{url}\n\n#청약 #당첨자발표 #{name.replace(' ', '')}"})
        elif cs and rnk1_end and 1 <= (today - rnk1_end).days <= 2:
            top = f" 가장 치열한 곳은 {cs['top_ty']} {cs['top_rate']:g}대1." if cs.get("top_rate") else ""
            posts.append({"kind": "result", "prio": 2, "url": url,
                          "text": f"{name} 1순위 결과 나왔습니다.\n\n{cs['sup']:,}세대에 {cs['req']:,}명, 평균 {cs['rate']:.1f}대1.{top}\n\n주택형별 경쟁률·평당 분양가 → {url}\n\n#청약 #청약경쟁률 #{name.replace(' ', '')}"})
        elif start == today:
            posts.append({"kind": "open", "prio": 3, "url": url,
                          "text": f"오늘부터 {name} 청약 접수 시작입니다.\n\n{place} · {it.get('kind', '')}\n일정·분양가·평당가를 한 페이지에 정리했어요. 내 가점으로 될지 계산기로 확인해 보세요.\n\n{url}\n\n#청약 #청약일정 #{name.replace(' ', '')}"})
    posts.sort(key=lambda p: p["prio"])
    return posts[:MAX_POSTS]


def write(posts, today, out_site, root):
    feed = {"date": today.isoformat(), "posts": posts}
    (out_site / "feeds").mkdir(parents=True, exist_ok=True)
    (out_site / "feeds" / "threads.json").write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    arch = pathlib.Path(root) / "posts" / "threads"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / f"{today.isoformat()}.json").write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    print("쓰레드 원고", len(posts), "건", flush=True)
