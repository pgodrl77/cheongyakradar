"""옛 주소(cheongyakradar.com) → 새 주소(cheongyakkok.com) 이전용 리디렉트 사이트 생성.
사용: python tools/make_redirect.py <원본 site 폴더> <출력 폴더>
원본 사이트의 모든 .html 경로마다 같은 경로의 새 주소로 보내는 페이지를 만든다.
(canonical + meta refresh 0초 + JS replace — 구글은 이를 영구 이동으로 취급)
"""
import sys, pathlib, html

NEW = "https://cheongyakkok.com"
OLD_DOMAIN = "cheongyakradar.com"

TPL = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>청약콕으로 이전했습니다</title>
<link rel="canonical" href="{url}">
<meta name="robots" content="noindex,follow">
<meta http-equiv="refresh" content="0; url={url}">
<script>location.replace({js}+location.search+location.hash)</script>
</head><body><p>청약레이더가 <a href="{url}">청약콕(cheongyakkok.com)</a>으로 이름을 바꿨습니다. 잠시 후 이동합니다.</p></body></html>
"""

FALLBACK_404 = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>청약콕으로 이전했습니다</title>
<meta name="robots" content="noindex">
<script>location.replace("%s"+location.pathname+location.search+location.hash)</script>
</head><body><p><a href="%s/">청약콕(cheongyakkok.com)</a>으로 이전했습니다.</p></body></html>
""" % (NEW, NEW)

# 옛 주소에 설치된 웹앱 서비스워커를 지우고 새 주소로 보내는 서비스워커
SW = """self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.map(k=>caches.delete(k)))).then(()=>self.registration.unregister()).then(()=>self.clients.matchAll()).then(cs=>cs.forEach(c=>c.navigate(c.url))))});
"""


def main(src, out):
    src, out = pathlib.Path(src), pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in src.rglob("*.html"):
        rel = p.relative_to(src).as_posix()
        path = "/" if rel == "index.html" else "/" + rel
        url = NEW + path
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(TPL.format(url=html.escape(url), js=repr(url).replace("'", '"')), encoding="utf-8")
        n += 1
    (out / "404.html").write_text(FALLBACK_404, encoding="utf-8")
    (out / "sw.js").write_text(SW, encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (out / "CNAME").write_text(OLD_DOMAIN, encoding="ascii")
    (out / ".nojekyll").write_text("", encoding="ascii")
    print(f"redirect pages: {n}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
