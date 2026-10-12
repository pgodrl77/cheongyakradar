"""IndexNow(2026-10-11): 새로 생기거나 바뀐 페이지를 빙·네이버 등 참여 검색엔진에 바로 알림.
- 키 파일 site/<KEY>.txt 를 사이트에 함께 올림(소유 확인)
- gh-pages 업로드가 끝난 뒤 publish.ps1 에서 `python indexnow.py` 실행
- data/indexnow_sent.json 에 보낸 주소·내용 지문을 저장해, 처음 보는 주소와 핵심 내용이 바뀐 주소만 보냄
  (매일 바뀌는 '최종 업데이트 날짜'는 지문에서 제외)
"""
import hashlib, json, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
SITE = ROOT / "site"
HOST = "cheongyakkok.com"
KEY = "c7e4a1f9b2d84e6a9f0c3b5d7e8a2f41"
SENT = ROOT / "data" / "indexnow_sent.json"


def write_key():
    (SITE / f"{KEY}.txt").write_text(KEY, encoding="utf-8")


def _fp(p):
    t = p.read_text(encoding="utf-8", errors="ignore")
    t = re.sub(r"최종 업데이트 [\d.]+|업데이트</b> [\d.]+|\?v=\w+", "", t)
    m = re.search(r"<main.*?</main>", t, re.S)
    return hashlib.md5((m.group(0) if m else t).encode("utf-8")).hexdigest()[:12]


def main():
    try:
        sent = json.loads(SENT.read_text(encoding="utf-8"))
    except Exception:
        sent = {}
    sm = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    urls, new = re.findall(r"<loc>(.*?)</loc>", sm), {}
    for u in urls:
        rel = u.split(HOST, 1)[1].lstrip("/") or "index.html"
        p = SITE / rel
        if p.exists():
            new[u] = _fp(p)
    todo = [u for u, h in new.items() if sent.get(u) != h][:10000]
    if not todo:
        print("IndexNow: 바뀐 페이지 없음")
        return
    body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": todo}).encode("utf-8")
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = r.status
    except Exception as e:
        code = getattr(e, "code", str(e))
    print(f"IndexNow: {len(todo)}개 전송 → {code}")
    if code in (200, 202):
        sent.update({u: new[u] for u in todo})
        SENT.parent.mkdir(parents=True, exist_ok=True)
        SENT.write_text(json.dumps(sent, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    write_key() if "--key" in sys.argv else main()
