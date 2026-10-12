"""입지 정보(2026-10-11): 카카오 로컬 API로 단지 주소 → 좌표 → 가까운 역·학교·마트·병원 직선거리.
- 키: 환경변수 KAKAO_REST_KEY 또는 Documents/.secrets/kakao.env (KAKAO_REST_KEY=...)
- 키가 없으면 아무것도 하지 않음(키가 생기면 다음 갱신부터 자동으로 켜짐)
- 결과는 data/loc_cache.json 에 저장해 같은 단지는 다시 조회하지 않음(주소가 같으면 재사용)
- 문장으로 평가하지 않고 측정값만 보여 줌(직선거리 기준, 도보 분 = 거리 ÷ 67m)
"""
import json, os, pathlib, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / "data" / "loc_cache.json"
API = "https://dapi.kakao.com/v2/local"
_key, _cache, _dirty = None, None, False


def key():
    global _key
    if _key is None:
        _key = os.environ.get("KAKAO_REST_KEY", "").strip()
        if not _key:
            for p in (ROOT.parent / ".secrets" / "kakao.env", ROOT.parent / "pgodrl77" / ".secrets" / "kakao.env"):
                if p.exists():
                    for line in p.read_text(encoding="utf-8-sig").splitlines():
                        if line.startswith("KAKAO_REST_KEY="):
                            _key = line.split("=", 1)[1].strip()
    return _key


def _get(path, params):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {key()}"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8")).get("documents", [])
        except Exception as e:
            if getattr(e, "code", None) in (401, 403):
                break
            time.sleep(1 + i)
    global _key
    _key = ""  # 키 오류·장애 시 이번 갱신에서는 입지 조회를 멈춤(캐시는 오염시키지 않음)
    return None


def _coord(addr, name):
    """주소로 먼저, 안 되면 '시군구 + 단지명' 키워드로."""
    import re
    a = (addr or "").replace("번지", "").strip()
    b = re.sub(r"\(.*?\)|일원|일대|외\s*\d+\s*필지|[,·].*$", "", a).strip()
    for q in dict.fromkeys([a, b]):  # 동 중심 좌표로 떨어지는 '동까지만' 검색은 하지 않음(거리 왜곡)
        if not q:
            continue
        docs = _get("search/address.json", {"query": q, "size": 1})
        if docs is None:
            return None
        if docs and docs[0].get("address_type") != "REGION":
            return float(docs[0]["x"]), float(docs[0]["y"])
    # 택지지구 주소: 괄호 안이나 중간에 '○○동 123번지'가 있으면 '시 + 동 + 번지'로
    city = re.search(r"\S+[시군](?=\s)", a)
    for m in re.finditer(r"(\S+[동리가])\s*(\d+(?:-\d+)?)\s*(?:번지)?", addr or ""):
        q = f"{city.group(0) if city else ''} {m.group(1)} {m.group(2)}".strip()
        docs = _get("search/address.json", {"query": q, "size": 1})
        if docs is None:
            return None
        if docs and docs[0].get("address_type") != "REGION":
            return float(docs[0]["x"]), float(docs[0]["y"])
    # 마지막: 단지명 키워드 — 실제 아파트(공사 중 포함)만, 견본주택·홍보관은 위치가 달라 제외
    if name:
        sido = (addr or "").split()[0] if addr else ""
        for q in (f"{sido} {name}".strip(),):
            docs = _get("search/keyword.json", {"query": q, "size": 5})
            if docs is None:
                return None
            for d in docs or []:
                cat, nm = d.get("category_name", ""), d.get("place_name", "")
                same_city = not city or city.group(0) in (d.get("address_name", "") + d.get("road_address_name", ""))
                if same_city and "아파트" in cat and not any(k in cat + nm for k in ("분양", "견본", "모델하우스", "홍보관")):
                    return float(d["x"]), float(d["y"])
    return None


def _near(x, y, radius, code=None, query=None, want=None, n=1):
    params = {"x": x, "y": y, "radius": radius, "sort": "distance", "size": 15}
    if code:
        params["category_group_code"] = code
    path = "search/keyword.json" if query else "search/category.json"
    if query:
        params["query"] = query
    out = []
    for page in (1, 2, 3):
        params["page"] = page
        docs = _get(path, params)
        if not docs:
            break
        for d in docs:
            nm = d.get("place_name", "")
            if want and not want(nm):
                continue
            if any(o["name"] == nm for o in out):
                continue
            out.append({"name": nm, "m": int(d.get("distance") or 0)})
            if len(out) >= n:
                return out
        if len(docs) < 15:
            break
    return out


def _station(nm):
    return nm.endswith("역") or "역 " in nm


def lookup(addr, name):
    """주소 하나의 입지 측정값. 키 없거나 좌표 실패 시 None."""
    global _cache, _dirty
    if not addr:
        return None
    if _cache is None:
        try:
            _cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    v = _cache.get(addr)
    if v and v.get("x"):
        return v
    if v is not None and v.get("fail", "") > time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400)):
        return None  # 실패한 주소는 7일 뒤 다시 시도
    if not key():
        return None
    c = _coord(addr, name)
    if not key():
        return None
    if not c:
        _cache[addr] = {"fail": time.strftime("%Y-%m-%d")}
        _dirty = True
        return None
    x, y = c
    loc = {
        "x": x, "y": y,
        "subway": _near(x, y, 5000, code="SW8", n=2),
        "elem": _near(x, y, 3000, code="SC4", query="초등학교", want=lambda s: s.endswith("초등학교"), n=1),
        "mid": _near(x, y, 4000, code="SC4", query="중학교", want=lambda s: s.endswith("중학교"), n=1),
        "mart": _near(x, y, 5000, code="MT1", want=lambda s: any(k in s for k in ("이마트", "홈플러스", "롯데마트", "코스트코", "트레이더스", "농협하나로", "하나로마트")) and not any(k in s for k in ("익스프레스", "에브리데이", "슈퍼", "편의점", "노브랜드")), n=1),
        "hosp": _near(x, y, 10000, code="HP8", query="종합병원", want=lambda s: "병원" in s and "동물" not in s, n=1),
        "t": time.strftime("%Y-%m-%d"),
    }
    if not key():  # 조회 도중 오류가 나면 불완전한 값은 저장하지 않음
        return None
    _cache[addr] = loc
    _dirty = True
    return loc


def save():
    if _dirty and _cache is not None:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=0), encoding="utf-8")


# ───────────── 화면 ─────────────

def _dist(m):
    walk = max(1, round(m / 67))
    d = f"약 {m:,}m" if m < 1000 else f"약 {m / 1000:.1f}km"
    return f"{d} <span class='small muted'>(도보 약 {walk}분)</span>" if m <= 2500 else d


def _station_tag(m):
    if m <= 500:
        return " <span class='b b-open'>역세권</span>"
    if m <= 1000:
        return " <span class='b b-soon'>역 도보권</span>"
    return ""


def html(loc, name, esc, kv):
    """'입지 한눈에 보기' 표 + 지도 링크. 측정값만, 평가 문장 없음."""
    if not loc:
        return ""
    rows = []
    sw = loc.get("subway") or []
    if sw:
        s0 = sw[0]
        v = f"{esc(s0['name'])} · {_dist(s0['m'])}{_station_tag(s0['m'])}"
        if len(sw) > 1:
            v += f"<br><span class='small muted'>다음 역: {esc(sw[1]['name'])} {_dist(sw[1]['m'])}</span>"
        rows.append(("가까운 지하철역", v))
    else:
        rows.append(("가까운 지하철역", "반경 5km 안에 지하철역 없음"))
    for k, lab, r in (("elem", "가까운 초등학교", "3km"), ("mid", "가까운 중학교", "4km"), ("mart", "대형마트", "5km"), ("hosp", "종합병원", "10km")):
        L = loc.get(k) or []
        rows.append((lab, f"{esc(L[0]['name'])} · {_dist(L[0]['m'])}" if L else f"반경 {r} 안에 없음"))
    mp = f"https://map.kakao.com/link/map/{urllib.parse.quote(name or '단지')},{loc['y']},{loc['x']}"
    return (f"<h2>{esc(name)} 입지 한눈에 보기</h2>" + kv(rows)
            + f"<p class='small muted' style='margin-top:8px'>단지 주소 기준 직선거리라 실제 걷는 거리는 더 깁니다. 배정 학교는 교육청 학구도로 꼭 확인하세요. "
            f"<a href=\"{mp}\" target=\"_blank\" rel=\"noopener\">카카오맵에서 위치 보기</a></p>")


def faq(loc, name):
    """FAQ 문답(검색 유입용 '○○ 역세권/학교' 질문)."""
    out = []
    if not loc:
        return out
    sw = loc.get("subway") or []
    if sw:
        m = sw[0]["m"]
        tag = " 단지에서 500m 안이라 역세권에 해당합니다." if m <= 500 else (" 걸어서 갈 수 있는 거리입니다." if m <= 1000 else "")
        out.append((f"{name} 가까운 지하철역은 어디인가요?", f"가장 가까운 역은 {sw[0]['name']}으로 직선거리 약 {m:,}m(도보 약 {max(1, round(m / 67))}분)입니다.{tag}"))
    e, mi = loc.get("elem") or [], loc.get("mid") or []
    if e or mi:
        parts = []
        if e:
            parts.append(f"초등학교는 {e[0]['name']}(약 {e[0]['m']:,}m)")
        if mi:
            parts.append(f"중학교는 {mi[0]['name']}(약 {mi[0]['m']:,}m)")
        out.append((f"{name} 근처 학교는 어디인가요?", "가장 가까운 " + ", ".join(parts) + "입니다. 실제 배정 학교는 교육청 학구도로 확인해야 합니다."))
    return out
