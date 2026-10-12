"""일회성: 실패 주소 재시도 + 예전 필터로 들어간 소형 마트(익스프레스 등) 다시 조회."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import location as L

L.lookup("x", None)  # 캐시 로드
bad = ("익스프레스", "에브리데이", "슈퍼", "편의점", "노브랜드")
ok = fail = fixed = 0
for addr, v in list(L._cache.items()):
    if v and v.get("x"):
        m = v.get("mart") or []
        if m and any(k in m[0]["name"] for k in bad):
            v["mart"] = L._near(v["x"], v["y"], 5000, code="MT1", want=lambda s: any(k in s for k in ("이마트", "홈플러스", "롯데마트", "코스트코", "트레이더스", "농협하나로", "하나로마트")) and not any(k in s for k in bad), n=1)
            L._dirty = True
            fixed += 1
        continue
    del L._cache[addr]
    r = L.lookup(addr, None)
    ok += bool(r)
    fail += not r
L.save()
print("재시도 성공", ok, "실패", fail, "마트 교정", fixed, "키", bool(L.key()))
