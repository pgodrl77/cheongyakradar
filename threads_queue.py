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
        card = {"name": name, "place": place}
        if cs:
            card["rate"] = f"평균 {cs['rate']:.1f} : 1"
        if win == today:
            posts.append({"kind": "winner", "prio": 1, "url": url, "card": card,
                          "text": f"오늘 {name} 당첨자 발표날입니다.\n\n{place}\n주택형별 경쟁률·당첨 가점 커트라인은 청약콕에 정리해 두었어요.\n👉 프로필 링크에서 단지 이름으로 검색하세요.\n\n{url}\n\n#청약 #당첨자발표 #{name.replace(' ', '')}"})
        elif cs and rnk1_end and 1 <= (today - rnk1_end).days <= 2:
            top = f" 가장 치열한 곳은 {cs['top_ty']} {cs['top_rate']:g}대1." if cs.get("top_rate") else ""
            posts.append({"kind": "result", "prio": 2, "url": url, "card": card,
                          "text": f"{name} 1순위 결과 나왔습니다.\n\n{cs['sup']:,}세대에 {cs['req']:,}명, 평균 {cs['rate']:.1f}대1.{top}\n\n주택형별 경쟁률·평당 분양가는 청약콕에서 → {url}\n👉 프로필 링크에서 단지 이름으로 검색하세요.\n\n#청약 #청약경쟁률 #{name.replace(' ', '')}"})
        elif start == today:
            posts.append({"kind": "open", "prio": 3, "url": url, "card": card,
                          "text": f"오늘부터 {name} 청약 접수 시작입니다.\n\n{place} · {it.get('kind', '')}\n일정·분양가·평당가를 한 페이지에 정리했어요. 내 가점으로 될지 청약콕 계산기로 확인해 보세요.\n👉 프로필 링크에서 단지 이름으로 검색하세요.\n\n{url}\n\n#청약 #청약일정 #{name.replace(' ', '')}"})
    posts.sort(key=lambda p: p["prio"])
    return posts[:MAX_POSTS]


KIND_LABEL = {"winner": "오늘 당첨자 발표", "result": "1순위 경쟁률 결과", "open": "오늘 청약 접수 시작"}
KIND_SUB = {"winner": "주택형별 경쟁률·당첨 커트라인 정리", "result": "주택형별 경쟁률·평당 분양가 정리", "open": "일정·분양가·내 가점 계산"}


def _font(size, bold=True):
    from PIL import ImageFont
    for f in (("malgunbd.ttf" if bold else "malgun.ttf"), "NanumGothicBold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    """단어(띄어쓰기) 단위로 줄바꿈, 한 단어가 너무 길 때만 글자 단위로 자른다."""
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if draw.textlength(cand, font=font) <= width:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:
            if draw.textlength(cur + ch, font=font) > width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
    if cur:
        lines.append(cur)
    return lines


def card_png(post, today, path):
    """인스타그램용 4:5 카드 이미지 (1080x1350). 실패해도 빌드는 계속된다."""
    from PIL import Image, ImageDraw
    W, H = 1080, 1350
    blue, white, pale = (29, 99, 219), (255, 255, 255), (200, 220, 255)
    im = Image.new("RGB", (W, H), blue)
    dr = ImageDraw.Draw(im)
    c = post.get("card", {})
    pad = 90
    label, f_lab = KIND_LABEL.get(post["kind"], "청약 소식"), _font(46)
    dr.rounded_rectangle((pad, 140, pad + 80 + int(dr.textlength(label, font=f_lab)), 230), radius=45, fill=white)
    dr.text((pad + 40, 160), label, font=f_lab, fill=blue)
    f_name = _font(96)
    lines = _wrap(dr, c.get("name", ""), f_name, W - pad * 2)[:4]
    y = 330
    for ln in lines:
        dr.text((pad, y), ln, font=f_name, fill=white)
        y += 122
    y += 30
    if c.get("place"):
        dr.text((pad, y), c["place"], font=_font(48, False), fill=pale)
        y += 80
    if post["kind"] == "result" and c.get("rate"):
        dr.text((pad, y + 10), c["rate"], font=_font(110), fill=white)
        y += 150
    dr.text((pad, H - 330), KIND_SUB.get(post["kind"], ""), font=_font(44, False), fill=pale)
    dr.text((pad, H - 260), f"{today.month}월 {today.day}일 기준", font=_font(40, False), fill=pale)
    dr.line((pad, H - 180, W - pad, H - 180), fill=pale, width=3)
    dr.text((pad, H - 150), "청약콕", font=_font(56), fill=white)
    dr.text((W - pad - dr.textlength("cheongyakkok.com", font=_font(44, False)), H - 140), "cheongyakkok.com", font=_font(44, False), fill=pale)
    im.save(path, "PNG", optimize=True)


def write(posts, today, out_site, root):
    cards = out_site / "cards"
    cards.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(posts, 1):
        try:
            fn = f"{today.isoformat()}-{i}.png"
            card_png(p, today, cards / fn)
            base = p["url"].split("/apt/")[0]
            p["image"] = f"{base}/cards/{fn}"
        except Exception as e:  # 카드가 없어도 쓰레드·페이스북 게시는 된다
            print("카드 이미지 실패:", e, flush=True)
        # 2026-10-19 사용자 지시 "혜택 한 장처럼 카드 뉴스를 만들어서 게시" — 15초 카드뉴스 릴스(인스타 릴스·틱톡용)
        try:
            import reel
            slug = p["url"].split("/apt/")[1].rsplit(".html", 1)[0]
            vn = f"{today.isoformat()}-{i}.mp4"
            reel.make(slug, p["kind"], cards / vn, today, out_site)
            base = p["url"].split("/apt/")[0]
            p["video"] = f"{base}/cards/{vn}"
            p["cover"] = f"{base}/cards/{vn[:-4]}.jpg"
        except Exception as e:  # 릴스가 없으면 예약 작업이 카드 이미지로 게시한다
            print("릴스 실패:", e, flush=True)
    feed = {"date": today.isoformat(), "posts": posts}
    (out_site / "feeds").mkdir(parents=True, exist_ok=True)
    (out_site / "feeds" / "threads.json").write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    arch = pathlib.Path(root) / "posts" / "threads"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / f"{today.isoformat()}.json").write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    print("쓰레드 원고", len(posts), "건", flush=True)
