"""주변 실거래가(국토교통부 아파트 매매 실거래가 API)로 분양가와 시세 차이(안전마진)를 계산한다.
공공데이터포털 활용신청이 안 돼 있으면(403) 조용히 건너뛴다. 지난달 이전 자료는 data/rtms_cache 에 캐시."""
import datetime as dt, json, pathlib, statistics, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / "data" / "rtms_cache"
URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
SGG = json.loads((ROOT / "data" / "sgg.json").read_text(encoding="utf-8"))
SIDO = sorted({k.split()[0] for k in SGG})
DISABLED = False


def lawd(addr):
    w = (addr or "").split()
    if len(w) < 2:
        return None
    sido = next((s for s in SIDO if s[:2] == w[0][:2]), w[0])
    for k in (f"{sido} {w[1]} {w[2]}" if len(w) > 2 else None, f"{sido} {w[1]}", sido):
        if k and k in SGG:
            return SGG[k]
    return None


def months(today, n=6):
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def fetch(key, code, ym, today):
    global DISABLED
    if DISABLED:
        return []
    cur = ym == f"{today.year}{today.month:02d}"
    cf = CACHE / f"{code}-{ym}.json"
    if cf.exists() and not cur:
        return json.loads(cf.read_text(encoding="utf-8"))
    q = urllib.parse.urlencode({"serviceKey": key, "LAWD_CD": code, "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": 1})
    try:
        with urllib.request.urlopen(f"{URL}?{q}", timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        if "403" in str(e) or "401" in str(e):
            DISABLED = True
            print("실거래가 API 미등록 — 시세 비교 생략")
        return []
    rows = []
    for it in root.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        if g("cdealType"):  # 해제된 거래 제외
            continue
        try:
            rows.append({"n": g("aptNm"), "ar": float(g("excluUseAr")), "amt": int(g("dealAmount").replace(",", "")), "by": int(g("buildYear") or 0)})
        except Exception:
            continue
    CACHE.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def won(v):
    eok, man = divmod(int(round(v)), 10000)
    if eok and man >= 1000:
        return f"{eok}억 {man // 1000 * 1000:,}만원"
    return f"{eok}억원" if eok else f"{man:,}만원"


def gap(it, key, today, ty_of):
    """it['gap'] 문구와 it['gap_v'](만원, +면 분양가가 시세보다 낮음) 설정."""
    if DISABLED or it["prefix"] != "apt":
        return
    code = lawd(it["d"].get("HSSPLY_ADRES"))
    if not code:
        return
    for lo, hi, lab in ((80, 86, "84㎡"), (57, 61, "59㎡")):
        mine = [float(m.get("LTTOT_TOP_AMOUNT") or 0) for m in it["mdl"] if lo <= ty_of(m) <= hi]
        mine = [x for x in mine if x > 0]
        if mine:
            break
    else:
        return
    price = max(mine)
    trades = []
    for ym in months(today):
        trades += [t for t in fetch(key, code, ym, today) if lo <= t["ar"] <= hi]
        if DISABLED:
            return
    new = [t for t in trades if t["by"] >= today.year - 10]
    basis, pool = ("입주 10년 이내", new) if len(new) >= 3 else ("같은 시·군·구 전체", trades)
    if len(pool) < 3:
        return
    med = statistics.median(t["amt"] for t in pool)
    diff = med - price
    word = "낮음" if diff > 0 else "높음"
    it["gap_v"] = diff
    it["gap"] = (f"<b>분양가가 약 {won(abs(diff))} {word}</b> <span class='small muted'>({lab} 최고 분양가 {won(price)} vs 주변 {basis} 아파트 {lab} 최근 6개월 실거래 중앙값 {won(med)}, {len(pool)}건)</span>")
