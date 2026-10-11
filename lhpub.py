"""LH 분양·임대 공고(공공데이터포털 '한국토지주택공사_분양임대공고문 조회'). 활용신청 전(403)이면 빈 목록."""
import json, urllib.parse, urllib.request

URL = "https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"


def _find(o):
    if isinstance(o, list):
        if o and isinstance(o[0], dict) and any(k.upper() == "PAN_NM" for k in o[0]):
            return o
        for x in o:
            r = _find(x)
            if r:
                return r
    elif isinstance(o, dict):
        for v in o.values():
            r = _find(v)
            if r:
                return r
    return None


def fetch(key):
    out = []
    for page in range(1, 4):
        q = urllib.parse.urlencode({"serviceKey": key, "PG_SZ": 100, "PAGE": page})
        try:
            with urllib.request.urlopen(f"{URL}?{q}", timeout=30) as r:
                j = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("LH 공고 API 실패/미등록:", e)
            return out
        rows = _find(j) or []
        out += [{k.upper(): v for k, v in x.items()} for x in rows]
        if len(rows) < 100:
            break
    return out
