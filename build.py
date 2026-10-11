# -*- coding: utf-8 -*-
"""청약레이더 정적 사이트 생성기.

한국부동산원 청약홈 오픈API(공공데이터포털)에서 분양공고·주택형·경쟁률을 받아
site/ 폴더에 정적 HTML 을 만든다. 표준 라이브러리만 사용.
키: 환경변수 DATA_GO_KR_KEY, 없으면 ../.secrets/datagokr.env
"""
import datetime as dt
import html
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "site"
SITE_URL = os.environ.get("SITE_URL", "https://cheongyakradar.com")
SITE_NAME = "청약레이더"
API = "https://api.odcloud.kr/api"
KST = dt.timezone(dt.timedelta(hours=9))
TODAY = dt.datetime.now(KST).date()
LOOKBACK_DAYS = 120
PYEONG = 3.3058

KINDS = [
    # (경로 접두, 상세, 주택형, 표시 이름)
    ("apt", "ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail", "ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancMdl", "아파트"),
    ("rem", "ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancDetail", "ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancMdl", "무순위·잔여세대"),
    ("opt", "ApplyhomeInfoDetailSvc/v1/getOPTLttotPblancDetail", "ApplyhomeInfoDetailSvc/v1/getOPTLttotPblancMdl", "임의공급"),
]
CMPET = "ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet"


def load_key():
    k = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if k:
        return k
    for p in (ROOT.parent / ".secrets" / "datagokr.env", ROOT.parent / "pgodrl77" / ".secrets" / "datagokr.env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("DATA_GO_KR_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("DATA_GO_KR_KEY 없음")


KEY = None


def call(path, params):
    q = dict(params)
    q["serviceKey"] = KEY
    url = f"{API}/{path}?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # 네트워크·429
            if attempt == 3:
                print("API 실패", path, e)
                return {"data": []}
            time.sleep(2 * (attempt + 1))


def fetch_all(path, cond):
    rows, page = [], 1
    while True:
        params = {"page": page, "perPage": 500}
        params.update(cond)
        j = call(path, params)
        data = j.get("data") or []
        rows += data
        if len(data) < 500:
            return rows
        page += 1


def d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def esc(s):
    return html.escape("" if s is None else str(s))


def won(manwon):
    """만원 단위 정수 → '5억 4,110만원'."""
    try:
        v = int(float(manwon))
    except Exception:
        return "-"
    eok, man = divmod(v, 10000)
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


def area_label(ty):
    try:
        return f"{float(str(ty).strip().rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')):.0f}㎡"
    except Exception:
        return esc(ty)


# ───────────────────────── 데이터 수집 ─────────────────────────

def collect():
    since = (TODAY - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    items = []
    for prefix, detail_path, mdl_path, kind_name in KINDS:
        rows = fetch_all(detail_path, {"cond[RCRIT_PBLANC_DE::GTE]": since})
        def one(r, prefix=prefix, mdl_path=mdl_path, kind_name=kind_name):
            no = r.get("HOUSE_MANAGE_NO")
            mdl = fetch_all(mdl_path, {"cond[HOUSE_MANAGE_NO::EQ]": no})
            cmp_ = fetch_all(CMPET, {"cond[HOUSE_MANAGE_NO::EQ]": no}) if prefix == "apt" else []
            return {"prefix": prefix, "kind": kind_name, "d": r, "mdl": mdl, "cmp": cmp_}
        rows = [r for r in rows if r.get("HOUSE_MANAGE_NO")]
        with ThreadPoolExecutor(max_workers=8) as ex:
            items += list(ex.map(one, rows))
        print(kind_name, len(rows), "건", flush=True)
    return items


def first_rcpt(r):
    for k in ("SPSPLY_RCEPT_BGNDE", "GNRL_RNK1_CRSPAREA_RCPTDE", "RCEPT_BGNDE", "SUBSCRPT_RCEPT_BGNDE"):
        if d(r.get(k)):
            return d(r.get(k))
    return None


def last_rcpt(r):
    for k in ("GNRL_RNK2_ETC_AREA_ENDDE", "GNRL_RNK2_CRSPAREA_ENDDE", "GNRL_RNK1_ETC_AREA_ENDDE", "GNRL_RNK1_CRSPAREA_ENDDE", "RCEPT_ENDDE", "SUBSCRPT_RCEPT_ENDDE"):
        if d(r.get(k)):
            return d(r.get(k))
    return first_rcpt(r)


def status(r):
    s, e, w = first_rcpt(r), last_rcpt(r), d(r.get("PRZWNER_PRESNATN_DE"))
    if s and TODAY < s:
        return ("soon", f"D-{(s - TODAY).days}")
    if s and e and s <= TODAY <= e:
        return ("open", "접수 중")
    if w and TODAY <= w:
        return ("wait", "발표 대기")
    return ("done", "마감")


def enrich(items):
    """평당가(3.3㎡당 최고 분양가) 계산과 같은 시·도 평균 비교."""
    by_region = {}
    for it in items:
        best = []
        for m in it["mdl"]:
            try:
                amt = float(m.get("LTTOT_TOP_AMOUNT") or 0)
                ar = float(m.get("SUPLY_AR") or 0)
            except Exception:
                continue
            if amt > 0 and ar > 0:
                best.append(amt / (ar / PYEONG))
        it["ppp"] = round(sum(best) / len(best)) if best else None
        it["region"] = it["d"].get("SUBSCRPT_AREA_CODE_NM") or "기타"
        if it["ppp"] and it["prefix"] == "apt":
            by_region.setdefault(it["region"], []).append(it["ppp"])
    for it in items:
        vals = by_region.get(it["region"], [])
        it["region_avg"] = round(sum(vals) / len(vals)) if len(vals) >= 2 else None
        it["status"] = status(it["d"])
        it["first"] = first_rcpt(it["d"])
        it["slug"] = f"{it['prefix']}-{it['d'].get('HOUSE_MANAGE_NO')}-{it['d'].get('PBLANC_NO', '')}"
    order = {"open": 0, "soon": 1, "wait": 2, "done": 3}
    soon_open = [x for x in items if x["status"][0] in ("open", "soon", "wait")]
    soon_open.sort(key=lambda x: (order[x["status"][0]], x["first"] or dt.date(2100, 1, 1)))
    done = [x for x in items if x["status"][0] == "done"]
    done.sort(key=lambda x: x["first"] or dt.date(2000, 1, 1), reverse=True)
    return soon_open + done


# ───────────────────────── 달력·알림 ─────────────────────────

def events(it):
    """단지 하나의 주요 일정: (날짜, 종류, 라벨) 목록."""
    r = it["d"]
    ev = []
    def add(k, typ, lab):
        v = d(r.get(k))
        if v:
            ev.append((v, typ, lab))
    add("SPSPLY_RCEPT_BGNDE", "sp", "특별공급")
    add("GNRL_RNK1_CRSPAREA_RCPTDE", "r1", "1순위")
    add("GNRL_RNK2_CRSPAREA_RCPTDE", "r2", "2순위")
    if it["prefix"] != "apt":
        add("SUBSCRPT_RCEPT_BGNDE", "r1", "청약 접수")
        add("RCEPT_BGNDE", "r1", "청약 접수")
    add("PRZWNER_PRESNATN_DE", "win", "당첨 발표")
    add("CNTRCT_CNCLS_BGNDE", "ct", "계약")
    seen, out = set(), []
    for e in ev:
        if (e[0], e[2]) not in seen:
            seen.add((e[0], e[2])); out.append(e)
    return out


def closing_soon(items):
    """오늘·내일 접수가 끝나는 단지."""
    out = []
    for it in items:
        e = last_rcpt(it["d"])
        if e and 0 <= (e - TODAY).days <= 1 and it["status"][0] in ("open", "soon"):
            out.append((it, (e - TODAY).days))
    return out


def soon_bar(items, prefix):
    cs = closing_soon(items)
    if not cs:
        return ""
    links = " · ".join(f'<a href="{prefix}{it["slug"]}.html">{esc(it["d"].get("HOUSE_NM"))}</a> {"오늘" if n == 0 else "내일"} 마감' for it, n in cs[:4])
    return f'<div class="alert"><b>마감 임박</b> {links}</div>'


def build_calendar(items):
    lo, hi = TODAY - dt.timedelta(days=45), TODAY + dt.timedelta(days=120)
    data = []
    for it in items:
        for v, typ, lab in events(it):
            if lo <= v <= hi:
                data.append({"d": v.isoformat(), "t": typ, "l": lab, "n": it["d"].get("HOUSE_NM") or "", "r": it["region"], "s": it["slug"]})
    data.sort(key=lambda x: (x["d"], x["t"]))
    week = [x for x in data if 0 <= (d(x["d"]) - TODAY).days <= 13]
    rows = "".join(f'<tr><td>{d(x["d"]):%m.%d}({"월화수목금토일"[d(x["d"]).weekday()]})</td><td><span class="ev ev-{x["t"]}">{esc(x["l"])}</span></td>'
                   f'<td><a href="apt/{x["s"]}.html">{esc(x["n"])}</a></td><td>{esc(x["r"])}</td></tr>' for x in week)
    body = f"""
<h1>{TODAY.year}년 {TODAY.month}월 청약 달력</h1>
<p class="lead">특별공급·1순위 접수일, 당첨자 발표일, 계약일을 날짜별로 모았습니다. 날짜를 누르면 그날 일정이 아래에 나옵니다. 단지 페이지에서 일정을 내 캘린더에 넣으면 마감 하루 전에 알림이 옵니다.</p>
{soon_bar(items, 'apt/')}
<div class="cal-hd"><button type="button" id="prev" aria-label="이전 달">‹</button><b id="ym"></b><button type="button" id="next" aria-label="다음 달">›</button></div>
<div class="legend small"><span class="ev ev-sp">특별공급</span><span class="ev ev-r1">1순위·접수</span><span class="ev ev-win">당첨 발표</span><span class="ev ev-ct">계약</span></div>
<div class="cal" id="cal"></div>
<h2 id="dayt"></h2><div id="dayl"></div>
<h2>신축 입주 준비<span class="tag">광고·제휴</span></h2>
{aff_html('calendar-' + TODAY.isoformat())}
{ad_slot()}
<h2>앞으로 2주 청약 일정</h2>
<div class="tbl"><table style="min-width:520px"><thead><tr><th>날짜</th><th>일정</th><th>단지</th><th>지역</th></tr></thead><tbody>{rows or '<tr><td colspan="4">2주 안에 예정된 일정이 없습니다.</td></tr>'}</tbody></table></div>
<script>
var EV={json.dumps(data, ensure_ascii=False)};
var T=new Date('{TODAY.isoformat()}T00:00:00'),cur=new Date(T.getFullYear(),T.getMonth(),1),sel='{TODAY.isoformat()}';
var by={{}};EV.forEach(function(e){{(by[e.d]=by[e.d]||[]).push(e)}});var nx=EV.filter(function(e){{return e.d>=sel}})[0];if(nx){{sel=nx.d;var q=sel.split('-');cur=new Date(+q[0],+q[1]-1,1)}}
function iso(y,m,d){{return y+'-'+String(m+1).padStart(2,'0')+'-'+String(d).padStart(2,'0')}}
function esc(s){{return String(s).replace(/[&<>"]/g,function(c){{return{{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}}
function draw(){{var y=cur.getFullYear(),m=cur.getMonth();document.getElementById('ym').textContent=y+'년 '+(m+1)+'월';
var h='';'일월화수목금토'.split('').forEach(function(w){{h+='<div class="cw">'+w+'</div>'}});
var st=new Date(y,m,1).getDay(),n=new Date(y,m+1,0).getDate();for(var i=0;i<st;i++)h+='<div class="cd e"></div>';
for(var d=1;d<=n;d++){{var k=iso(y,m,d),L=by[k]||[];var c='cd'+(k==='{TODAY.isoformat()}'?' today':'')+(k===sel?' sel':'');
h+='<button type="button" class="'+c+'" data-k="'+k+'"><span class="dn">'+d+'</span>';
L.slice(0,2).forEach(function(e){{h+='<span class="ev ev-'+e.t+'">'+esc(e.n.slice(0,7))+'</span>'}});if(L.length>2)h+='<span class="more">+'+(L.length-2)+'</span>';h+='</button>'}}
document.getElementById('cal').innerHTML=h;document.querySelectorAll('#cal button').forEach(function(b){{b.onclick=function(){{sel=b.getAttribute('data-k');draw();day()}}}})}}
function day(){{var L=by[sel]||[],p=sel.split('-');document.getElementById('dayt').textContent=(+p[1])+'월 '+(+p[2])+'일 일정 '+L.length+'건';
document.getElementById('dayl').innerHTML=L.length?'<div class="grid">'+L.map(function(e){{return '<a class="card" href="apt/'+e.s+'.html"><span class="ev ev-'+e.t+'">'+esc(e.l)+'</span><div><b>'+esc(e.n)+'</b></div><div class="small muted">'+esc(e.r)+'</div></a>'}}).join('')+'</div>':'<p class="muted">이날은 예정된 청약 일정이 없습니다.</p>'}}
document.getElementById('prev').onclick=function(){{cur=new Date(cur.getFullYear(),cur.getMonth()-1,1);draw()}};
document.getElementById('next').onclick=function(){{cur=new Date(cur.getFullYear(),cur.getMonth()+1,1);draw()}};
draw();day();
</script>
"""
    return page(f"{TODAY.year}년 {TODAY.month}월 아파트 청약 달력 - 접수일·당첨 발표일 | {SITE_NAME}",
                f"{TODAY.year}년 {TODAY.month}월 아파트 청약 일정을 달력으로 정리했습니다. 특별공급·1순위 접수일, 당첨자 발표일, 계약일을 날짜별로 확인하세요.",
                body, "calendar.html")


def build_ics(it):
    """단지 일정 캘린더 파일 — 접수 시작·마감 하루 전 알림 포함."""
    r = it["d"]; name = (r.get("HOUSE_NM") or "청약").replace(",", " ").replace(";", " ")
    url = f"{SITE_URL}/apt/{it['slug']}.html"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//cheongyakradar//KO", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for i, (v, typ, lab) in enumerate(events(it)):
        nxt = v + dt.timedelta(days=1)
        lines += ["BEGIN:VEVENT", f"UID:{it['slug']}-{i}@cheongyakradar.com", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{v:%Y%m%d}", f"DTEND;VALUE=DATE:{nxt:%Y%m%d}",
                  f"SUMMARY:[{lab}] {name}", f"DESCRIPTION:청약레이더 {url}", f"URL:{url}",
                  "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:내일 {lab} - {name}", "TRIGGER:-PT15H", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ───────────────────────── 화면 ─────────────────────────

CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:'Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#191F28;background:#fff;font-size:15px;line-height:1.6;letter-spacing:-0.2px}
a{color:#1B64DA;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid #E5E8EB}
.hd{height:64px;display:flex;align-items:center;gap:28px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:8px;color:#191F28;font-weight:700;font-size:20px}
.logo:hover{text-decoration:none}
nav{display:flex;gap:22px;flex-wrap:wrap;font-weight:500}
nav a{color:#333D4B}
.bar{background:#F2F4F6;border-bottom:1px solid #E5E8EB;font-size:13px;color:#4E5968;padding:10px 0}
.bar b{color:#1B64DA}
main{padding:28px 0 60px}
h1{margin:0 0 8px;font-size:28px;line-height:1.35}
h2{margin:36px 0 12px;font-size:20px}
.lead{margin:0 0 18px;color:#4E5968}
.pills{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.pills button{height:38px;padding:0 14px;border-radius:19px;border:1px solid #D1D6DB;background:#fff;color:#333D4B;font:inherit;font-size:14px;font-weight:500;cursor:pointer}
.pills button.on{background:#1B64DA;border-color:#1B64DA;color:#fff}
.tbl{overflow-x:auto;border:1px solid #E5E8EB;border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:14px}
.tbl table{min-width:760px}
th{background:#F9FAFB;color:#4E5968;font-weight:500;text-align:left;padding:12px 16px;border-bottom:1px solid #E5E8EB}
td{padding:13px 16px;border-bottom:1px solid #F2F4F6;vertical-align:top}
tr:last-child td{border-bottom:0}
.b{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700;white-space:nowrap}
.b-open{background:#E8F3FF;color:#1B64DA}.b-soon{background:#FFF3E0;color:#B35400}.b-wait{background:#F2F4F6;color:#4E5968}.b-done{background:#F2F4F6;color:#8B95A1}
.muted{color:#6B7684}.small{font-size:13px}
.card{border:1px solid #E5E8EB;border-radius:12px;padding:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.ad{margin:28px 0;min-height:90px}
.aff{display:flex;gap:12px;align-items:center;text-decoration:none;color:inherit;padding:14px}.aff:hover{border-color:#1B64DA}.aff img{border-radius:8px;flex:none;object-fit:cover}.aff>span{display:flex;flex-direction:column;gap:2px}
.tag{font-size:12px;color:#8B95A1;border:1px solid #D1D6DB;border-radius:4px;padding:0 6px;margin-left:6px;vertical-align:middle}
.kv{display:grid;grid-template-columns:140px 1fr;gap:0;border:1px solid #E5E8EB;border-radius:12px;overflow:hidden}
.kv div{padding:11px 16px;border-bottom:1px solid #F2F4F6}
.kv div:nth-child(odd){background:#F9FAFB;color:#4E5968}
.note{background:#F9FAFB;border-radius:12px;padding:16px 18px;color:#333D4B}
.calc label{display:block;font-weight:500;margin:14px 0 6px}
.calc select{width:100%;height:44px;border:1px solid #D1D6DB;border-radius:8px;padding:0 10px;font:inherit;background:#fff}
.score{font-size:44px;font-weight:700;color:#1B64DA}
.alert{background:#FFF0F0;color:#C4161C;border-radius:12px;padding:12px 16px;margin:0 0 18px;font-size:14px}.alert b{margin-right:8px}.alert a{color:#C4161C;font-weight:500}
.cal-hd{display:flex;align-items:center;justify-content:center;gap:18px;margin:8px 0}.cal-hd b{font-size:18px}.cal-hd button{width:36px;height:36px;border:1px solid #D1D6DB;border-radius:18px;background:#fff;font-size:18px;cursor:pointer}
.legend{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-bottom:10px}
.cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border-top:1px solid #E5E8EB;border-left:1px solid #E5E8EB}
.cw{padding:8px;text-align:center;font-size:13px;color:#6B7684;background:#F9FAFB;border-right:1px solid #E5E8EB;border-bottom:1px solid #E5E8EB}
.cd{min-height:92px;padding:6px;border:0;border-right:1px solid #E5E8EB;border-bottom:1px solid #E5E8EB;background:#fff;text-align:left;font:inherit;display:flex;flex-direction:column;gap:3px;cursor:pointer;overflow:hidden}
.cd.e{cursor:default}.cd .dn{font-size:13px;font-weight:500}.cd.today .dn{color:#fff;background:#1B64DA;border-radius:10px;padding:0 7px;align-self:flex-start}.cd.sel{background:#F2F8FF}
.ev{display:inline-block;font-size:11px;line-height:1.5;padding:0 5px;border-radius:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.ev-sp{background:#FFF3E0;color:#B35400}.ev-r1,.ev-r2{background:#E8F3FF;color:#1B64DA}.ev-win{background:#E9F8EE;color:#0B7A3E}.ev-ct{background:#F2F4F6;color:#4E5968}
.more{font-size:11px;color:#6B7684}
.btn{display:inline-block;padding:10px 16px;border-radius:8px;background:#1B64DA;color:#fff;font-weight:500}.btn:hover{text-decoration:none;background:#1957C2}
@media(max-width:640px){.cd{min-height:64px;padding:4px}.cd .ev{font-size:0;width:8px;height:8px;padding:0;border-radius:4px}.cd .ev-sp{background:#F59E0B}.cd .ev-r1,.cd .ev-r2{background:#1B64DA}.cd .ev-win{background:#16A34A}.cd .ev-ct{background:#8B95A1}.more{display:none}}
.barin{display:flex;justify-content:space-between;align-items:center;gap:12px}
.inst{height:30px;padding:0 12px;border:1px solid #1B64DA;border-radius:15px;background:#fff;color:#1B64DA;font:inherit;font-size:13px;font-weight:500;cursor:pointer;white-space:nowrap}
.ios{background:#E8F3FF;color:#1B3A6B;font-size:13px;padding:10px 0}.ios button{border:0;background:none;color:#1B64DA;font:inherit;font-weight:500;cursor:pointer;margin-left:6px}
[hidden]{display:none!important}
footer{border-top:1px solid #E5E8EB;background:#F9FAFB;font-size:12px;color:#6B7684;padding:24px 0}
footer a{color:#4E5968;margin-right:16px}
@media(max-width:640px){h1{font-size:23px}.kv{grid-template-columns:110px 1fr}.hd{height:auto;padding:12px 20px;gap:12px}}
"""

LOGO = ('<svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="11" fill="none" stroke="#1B64DA" stroke-width="2.2"/>'
        '<circle cx="13" cy="13" r="5.5" fill="none" stroke="#1B64DA" stroke-width="2.2"/><path d="M13 13 L21 6" stroke="#1B64DA" stroke-width="2.2" stroke-linecap="round"/>'
        '<circle cx="19" cy="9" r="2" fill="#1B64DA"/></svg>')

ADSENSE_CLIENT = os.environ.get("ADSENSE_CLIENT", "")  # 승인 후 ca-pub-… 입력


def ad_slot():
    if not ADSENSE_CLIENT:
        return '<div class="ad"></div>'
    return ('<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="%s" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>' % ADSENSE_CLIENT)


def page(title, desc, body, path, extra_head=""):
    canonical = f"{SITE_URL}/{path}".rstrip("/") if path else SITE_URL + "/"
    ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}" crossorigin="anonymous"></script>' if ADSENSE_CLIENT else "")
    up = "../" if "/" in path else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<link rel="manifest" href="{up}manifest.webmanifest">
<meta name="theme-color" content="#1B64DA">
<link rel="icon" type="image/png" sizes="32x32" href="{up}favicon-32.png">
<link rel="apple-touch-icon" href="{up}apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{SITE_NAME}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap">
<link rel="stylesheet" href="{up}assets/style.css">
{ads}{extra_head}
</head>
<body>
<header><div class="wrap hd">
<a class="logo" href="{up}index.html">{LOGO}{SITE_NAME}</a>
<nav aria-label="주 메뉴"><a href="{up}index.html">청약 일정</a><a href="{up}calendar.html">청약 달력</a><a href="{up}calc.html">가점 계산기</a><a href="{up}index.html#done">경쟁률</a><a href="{up}about.html">서비스 소개</a></nav>
</div></header>
<div class="bar"><div class="wrap barin"><span><b>업데이트</b> {TODAY:%Y.%m.%d} 기준 청약홈 분양정보 반영</span><button type="button" id="inst" class="inst" hidden>홈 화면에 앱 설치</button></div></div>
<div id="ios" class="ios" hidden><div class="wrap">아이폰은 Safari 아래쪽 <b>공유 버튼</b> → <b>홈 화면에 추가</b>를 누르면 앱처럼 쓸 수 있어요. <button type="button" id="iosx" aria-label="닫기">닫기</button></div></div>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
<div><a href="{up}about.html">서비스 소개</a><a href="{up}privacy.html">개인정보처리방침</a><a href="{up}calc.html">청약 가점 계산기</a></div>
<p>데이터 출처: 한국부동산원 청약홈 분양정보(공공데이터포털 오픈API). 정보는 자동으로 정리되며 오류가 있을 수 있습니다. 청약 전 반드시 청약홈의 입주자모집공고 원문을 확인하세요.</p>
<p>일부 링크는 제휴 링크이며, 이를 통해 일정 수수료를 받을 수 있습니다.</p>
<p>© {TODAY.year} {SITE_NAME}</p>
</div></footer>
<script>
if('serviceWorker' in navigator&&(location.protocol==='https:'||location.hostname==='localhost')){{navigator.serviceWorker.register('/sw.js').catch(function(){{}})}}
var dp,ib=document.getElementById('inst');window.addEventListener('beforeinstallprompt',function(e){{e.preventDefault();dp=e;ib.hidden=false}});
ib.onclick=function(){{if(!dp)return;dp.prompt();dp.userChoice.finally(function(){{dp=null;ib.hidden=true}})}};
window.addEventListener('appinstalled',function(){{ib.hidden=true}});
(function(){{var ua=navigator.userAgent,st=window.navigator.standalone||matchMedia('(display-mode: standalone)').matches,k='cy_ios_x';
var seen;try{{seen=localStorage.getItem(k)}}catch(e){{}}
if(/iPhone|iPad/.test(ua)&&/Safari/.test(ua)&&!/CriOS|FxiOS/.test(ua)&&!st&&!seen){{var b=document.getElementById('ios');b.hidden=false;
document.getElementById('iosx').onclick=function(){{b.hidden=true;try{{localStorage.setItem(k,'1')}}catch(e){{}}}}}}}})();
</script>
</body>
</html>
"""


def short_addr(a):
    parts = (a or "").split()
    return " ".join(parts[:2]) if parts else "-"


def fmt_date(x):
    v = d(x)
    return f"{v:%m.%d}" if v else "-"


def row_html(it, link_prefix):
    r = it["d"]
    cls, lab = it["status"]
    units = r.get("TOT_SUPLY_HSHLDCO")
    ppp = f"{round(it['ppp']):,}만원" if it.get("ppp") else "-"
    return (f'<tr data-region="{esc(it["region"])}"><td><a href="{link_prefix}{it["slug"]}.html"><b>{esc(r.get("HOUSE_NM"))}</b></a>'
            f'<div class="small muted">{esc(it["kind"])}</div></td>'
            f'<td>{esc(short_addr(r.get("HSSPLY_ADRES")))}</td>'
            f'<td>{fmt_date(r.get("SPSPLY_RCEPT_BGNDE"))}</td>'
            f'<td>{fmt_date(r.get("GNRL_RNK1_CRSPAREA_RCPTDE") or r.get("RCEPT_BGNDE") or r.get("SUBSCRPT_RCEPT_BGNDE"))}</td>'
            f'<td>{fmt_date(r.get("PRZWNER_PRESNATN_DE"))}</td>'
            f'<td>{esc(units) + "세대" if units else "-"}</td>'
            f'<td>{ppp}</td>'
            f'<td><span class="b b-{cls}">{esc(lab)}</span></td></tr>')


TABLE_HEAD = ('<div class="tbl"><table><thead><tr><th scope="col">단지명</th><th scope="col">위치</th><th scope="col">특별공급</th>'
              '<th scope="col">1순위</th><th scope="col">당첨 발표</th><th scope="col">공급</th><th scope="col">평당 분양가(최고)</th><th scope="col">상태</th></tr></thead><tbody>')


def build_index(items):
    live = [x for x in items if x["status"][0] != "done"]
    done = [x for x in items if x["status"][0] == "done"][:60]
    regions = sorted({x["region"] for x in live})
    pills = '<button type="button" class="on" data-r="">전체</button>' + "".join(f'<button type="button" data-r="{esc(r)}">{esc(r)}</button>' for r in regions)
    n_open = sum(1 for x in live if x["status"][0] == "open")
    body = f"""
<h1>이번 주 청약 일정과 분양가, 한 화면에서</h1>
<p class="lead">청약홈 분양공고를 매일 아침 정리합니다. 지금 접수 중인 단지 {n_open}곳, 접수 예정·발표 대기 단지 {len(live) - n_open}곳이 있습니다. 평당 분양가는 주택형별 최고 공급가를 공급면적으로 나눠 계산했습니다.</p>
{soon_bar(items, 'apt/')}
<div class="pills" role="group" aria-label="지역 선택">{pills}</div>
<h2 id="live" style="margin-top:8px">접수 중 · 예정 · 발표 대기</h2>
{TABLE_HEAD}{''.join(row_html(x, 'apt/') for x in live) or '<tr><td colspan="8">현재 진행 중인 공고가 없습니다.</td></tr>'}</tbody></table></div>
{ad_slot()}
<h2 id="done">최근 마감된 청약</h2>
{TABLE_HEAD}{''.join(row_html(x, 'apt/') for x in done)}</tbody></table></div>
<h2>날짜별로 보고 싶다면</h2>
<div class="card"><p style="margin:0 0 10px">특별공급·1순위 접수일과 당첨자 발표일을 달력 한 장에 모았습니다.</p><a href="calendar.html"><b>청약 달력 열기 →</b></a></div>
<h2>내 점수로 당첨될 수 있을까?</h2>
<div class="card"><p style="margin:0 0 10px">무주택 기간, 부양가족 수, 청약통장 가입 기간만 고르면 84점 만점 가점을 바로 계산합니다.</p><a href="calc.html"><b>청약 가점 계산기 열기 →</b></a></div>
<script>
document.querySelectorAll('.pills button').forEach(function(b){{b.addEventListener('click',function(){{
document.querySelectorAll('.pills button').forEach(function(x){{x.classList.remove('on')}});b.classList.add('on');var r=b.getAttribute('data-r');
document.querySelectorAll('#live + .tbl tbody tr').forEach(function(tr){{tr.style.display=(!r||tr.getAttribute('data-region')===r)?'':'none'}});}})}});
</script>
"""
    return page(f"{SITE_NAME} - 아파트 청약 일정·분양가·경쟁률 한눈에", "이번 주 아파트 청약 일정, 단지별 분양가와 평당가, 무순위 줍줍 공고, 경쟁률을 매일 정리합니다.", body, "")


def kv(rows):
    return '<div class="kv">' + "".join(f"<div>{esc(k)}</div><div>{v}</div>" for k, v in rows if v and v != "-") + "</div>"


# 신축 입주 준비 쿠팡 파트너스 상품 (2026-10-11 교체: 새집 입주자는 싼 것보다 좋은 것을 찾음 → 프리미엄 가전 위주)
AFF = [
 {
  "t": "로보락 S9 MaxV Ultra 직배수",
  "u": "신축은 직배수 배관 연결이 쉬워 물통 비울 일 없어요",
  "p": 1540000,
  "link": "https://link.coupang.com/a/hLDEAhWru0",
  "img": "https://thumbnail8.coupangcdn.com/thumbnails/remote/212x212ex/image/retail/images/134385707333821-b03213d0-6147-48ef-a441-a09008cdbfa2.jpg"
 },
 {
  "t": "LG 퓨리케어 오브제 AI 360° 알파UP",
  "u": "109㎡ 대형 거실까지, 새집 미세먼지·냄새 한 번에",
  "p": 1850290,
  "link": "https://link.coupang.com/a/hLDIa0KOIe",
  "img": "https://t2c.coupangcdn.com/thumbnails/remote/212x212ex/image/vendor_inventory/6a32/d231403ff458513e5eaac082e01bb90ee7da9810199dfc45ff94a868eca3.jpg"
 },
 {
  "t": "삼성 인피니트 AI 공기청정기",
  "u": "가스 탈취 필터로 새집증후군 냄새·유해가스 케어",
  "p": 1049000,
  "link": "https://link.coupang.com/a/hLEymNreRE",
  "img": "https://thumbnail12.coupangcdn.com/thumbnails/remote/212x212ex/image/retail/images/2026/09/08/18/5/dae0699a-d3e0-4ae2-b51d-2232477c2e0e.jpg"
 },
 {
  "t": "LG 스타일러 오브제컬렉션",
  "u": "새 드레스룸에 들이는 의류관리기, 방문설치",
  "p": 1204030,
  "link": "https://link.coupang.com/a/hLDICeL3RI",
  "img": "https://thumbnail2.coupangcdn.com/thumbnails/remote/212x212ex/image/retail/images/2026/02/02/9/0/cfafe4f4-982a-4865-ae38-3340244b194e.jpg"
 },
 {
  "t": "삼성 Bespoke 에어드레서",
  "u": "빌트인처럼 붙는 디자인, 상의 5벌 동시 관리",
  "p": 939550,
  "link": "https://link.coupang.com/a/hLDIQIV8N2",
  "img": "https://thumbnail15.coupangcdn.com/thumbnails/remote/212x212ex/image/retail/images/2025/04/16/12/4/fdc81716-073f-4866-8ef0-e79ec5e2240e.jpg"
 },
 {
  "t": "삼성 Bespoke 제트 AI 400W",
  "u": "자동 먼지비움 스테이션, 새 집 첫 청소기로",
  "p": 1390000,
  "link": "https://link.coupang.com/a/hLDI3IvJW8",
  "img": "https://thumbnail9.coupangcdn.com/thumbnails/remote/212x212ex/image/retail/images/2332178184722-2c42fbd6-c29f-41ad-97f1-f526d3f2d68d.jpg"
 }
]

def aff_html(slug):
    import hashlib
    k = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    n = len(AFF); start = k % n
    picks = [AFF[(start + i) % n] for i in range(4)]
    cards = "".join(
        f'<a class="card aff" href="{esc(a["link"])}" rel="sponsored nofollow noopener" target="_blank">'
        f'<img src="{esc(a["img"].replace("1000x1000ex", "230x230ex"))}" alt="{esc(a["t"])}" loading="lazy" width="72" height="72">'
        f'<span><b>{esc(a["t"])}</b><span class="small muted">{esc(a["u"])}</span><span class="small">{a["p"]//10000:,}만원대 · 쿠팡에서 보기</span></span></a>'
        for a in picks)
    return (f'<div class="grid">{cards}</div>'
            '<p class="small muted" style="margin-top:8px">이 게시물은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다. 가격은 변동될 수 있습니다.</p>')

def build_detail(it, items):
    r = it["d"]
    name = r.get("HOUSE_NM") or "단지"
    cls, lab = it["status"]
    sched = [
        ("모집공고일", fmt_full(r.get("RCRIT_PBLANC_DE"))),
        ("특별공급 접수", rng(r.get("SPSPLY_RCEPT_BGNDE"), r.get("SPSPLY_RCEPT_ENDDE"))),
        ("1순위 (해당지역)", rng(r.get("GNRL_RNK1_CRSPAREA_RCPTDE"), r.get("GNRL_RNK1_CRSPAREA_ENDDE"))),
        ("1순위 (기타지역)", rng(r.get("GNRL_RNK1_ETC_AREA_RCPTDE"), r.get("GNRL_RNK1_ETC_AREA_ENDDE"))),
        ("2순위", rng(r.get("GNRL_RNK2_CRSPAREA_RCPTDE"), r.get("GNRL_RNK2_ETC_AREA_ENDDE"))),
        ("청약 접수", rng(r.get("SUBSCRPT_RCEPT_BGNDE") or r.get("RCEPT_BGNDE"), r.get("SUBSCRPT_RCEPT_ENDDE") or r.get("RCEPT_ENDDE"))),
        ("당첨자 발표", fmt_full(r.get("PRZWNER_PRESNATN_DE"))),
        ("계약", rng(r.get("CNTRCT_CNCLS_BGNDE"), r.get("CNTRCT_CNCLS_ENDDE"))),
        ("입주 예정", ym(r.get("MVN_PREARNGE_YM"))),
    ]
    info = [
        ("위치", esc(r.get("HSSPLY_ADRES"))),
        ("공급 유형", esc(f"{it['kind']} · {r.get('HOUSE_DTL_SECD_NM') or ''}".strip(" ·"))),
        ("총 공급", f"{esc(r.get('TOT_SUPLY_HSHLDCO'))}세대" if r.get("TOT_SUPLY_HSHLDCO") else "-"),
        ("시행사", esc(r.get("BSNS_MBY_NM"))),
        ("시공사", esc(r.get("CNSTRCT_ENTRPS_NM"))),
        ("분양가 상한제", "적용" if r.get("PARCPRC_ULS_AT") == "Y" else ("미적용" if r.get("PARCPRC_ULS_AT") == "N" else "-")),
        ("문의", esc(r.get("MDHS_TELNO"))),
    ]
    mrows = []
    for m in it["mdl"]:
        try:
            ar = float(m.get("SUPLY_AR") or 0)
            amt = float(m.get("LTTOT_TOP_AMOUNT") or 0)
        except Exception:
            ar, amt = 0, 0
        p = f"{round(amt / (ar / PYEONG)):,}만원" if ar and amt else "-"
        mrows.append(f"<tr><td>{area_label(m.get('HOUSE_TY'))} <span class='small muted'>{esc(str(m.get('HOUSE_TY') or '').strip())}</span></td>"
                     f"<td>{ar:.2f}㎡</td><td>{esc(m.get('SUPLY_HSHLDCO') or '-')}</td><td>{esc(m.get('SPSPLY_HSHLDCO') or '-')}</td>"
                     f"<td>{won(amt) if amt else '-'}</td><td>{p}</td></tr>")
    mtable = ('<div class="tbl"><table><thead><tr><th>주택형</th><th>공급면적</th><th>일반공급</th><th>특별공급</th><th>최고 분양가</th><th>평당가</th></tr></thead><tbody>'
              + "".join(mrows) + "</tbody></table></div>") if mrows else '<p class="muted">주택형별 정보가 아직 등록되지 않았습니다.</p>'
    # 분석 문장(데이터로 계산한 비교)
    analysis = []
    if it.get("ppp") and it.get("region_avg"):
        diff = (it["ppp"] - it["region_avg"]) / it["region_avg"] * 100
        word = "높습니다" if diff > 0 else "낮습니다"
        analysis.append(f"이 단지의 평균 평당 분양가(최고가 기준)는 <b>{it['ppp']:,}만원</b>으로, 최근 {LOOKBACK_DAYS}일 동안 {esc(it['region'])}에서 공고된 아파트 평균({it['region_avg']:,}만원)보다 <b>{abs(diff):.1f}% {word}</b>.")
    elif it.get("ppp"):
        analysis.append(f"이 단지의 평균 평당 분양가(최고가 기준)는 <b>{it['ppp']:,}만원</b>입니다. 같은 지역 비교 대상이 부족해 지역 평균 비교는 생략했습니다.")
    if it["mdl"]:
        total_g = sum(int(m.get("SUPLY_HSHLDCO") or 0) for m in it["mdl"])
        total_s = sum(int(m.get("SPSPLY_HSHLDCO") or 0) for m in it["mdl"])
        if total_g + total_s:
            analysis.append(f"전체 {total_g + total_s:,}세대 중 특별공급이 {total_s:,}세대({total_s / (total_g + total_s) * 100:.0f}%), 일반공급이 {total_g:,}세대입니다.")
        small = [m for m in it["mdl"] if _ty(m) and _ty(m) <= 85]
        if small:
            analysis.append(f"전용 85㎡ 이하 주택형이 {len(small)}개 있습니다. 85㎡ 이하 민영주택은 가점제 비율이 높아 청약 가점이 중요합니다.")
    ctable = build_cmpet(it["cmp"])
    near = [x for x in items if x["region"] == it["region"] and x is not it][:6]
    near_html = "".join(f'<a class="card" href="{x["slug"]}.html"><div class="small muted">{esc(short_addr(x["d"].get("HSSPLY_ADRES")))}</div><b>{esc(x["d"].get("HOUSE_NM"))}</b><div class="small">{esc(x["status"][1])}</div></a>' for x in near)
    url = r.get("PBLANC_URL") or ""
    hp = r.get("HMPG_ADRES") or ""
    links = []
    if url.startswith("http"):
        links.append(f'<a href="{esc(url)}" rel="nofollow noopener" target="_blank">청약홈 입주자모집공고 원문 보기</a>')
    if hp.startswith("http"):
        links.append(f'<a href="{esc(hp)}" rel="nofollow noopener" target="_blank">분양 홈페이지</a>')
    body = f"""
<p class="small muted"><a href="../index.html">청약 일정</a> › {esc(it['region'])}</p>
<h1>{esc(name)} 청약 일정·분양가 <span class="b b-{cls}" style="vertical-align:middle">{esc(lab)}</span></h1>
<p class="lead">{esc(short_addr(r.get('HSSPLY_ADRES')))} · {esc(it['kind'])} · 공고일 {fmt_full(r.get('RCRIT_PBLANC_DE'))}</p>
<h2>청약 일정</h2>{kv(sched)}
{('<p style="margin:14px 0 0"><a class="btn" href="' + it['slug'] + '.ics" download>내 캘린더에 일정 추가</a> <span class="small muted">접수·발표 하루 전에 알림이 옵니다</span></p>') if events(it) else ''}
<h2>단지 정보</h2>{kv(info)}
<h2>주택형별 분양가</h2>{mtable}
<h2>한눈에 보는 분석</h2><div class="note">{'<br>'.join(analysis) or '분석할 주택형 정보가 아직 없습니다.'}</div>
<h2>신축 입주 준비<span class="tag">광고·제휴</span></h2>
{aff_html(it['slug'])}
{ad_slot()}
{('<h2>청약 경쟁률</h2>' + ctable) if ctable else ''}
<h2>원문 확인</h2><p>{' · '.join(links) or '청약홈(applyhome.co.kr)에서 단지명으로 검색해 공고 원문을 확인하세요.'}</p>
{('<h2>' + esc(it['region']) + ' 다른 청약</h2><div class="grid">' + near_html + '</div>') if near_html else ''}
"""
    desc = f"{name} 청약 일정(특별공급·1순위·당첨자 발표), 주택형별 분양가와 평당가, 경쟁률을 정리했습니다."
    return page(f"{name} 청약 일정·분양가·경쟁률 | {SITE_NAME}", desc, body, f"apt/{it['slug']}.html")


def _ty(m):
    try:
        return float(str(m.get("HOUSE_TY") or "").strip().rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    except Exception:
        return 0


def _ar(m):
    try:
        return float(m.get("SUPLY_AR") or 0)
    except Exception:
        return 0


def fmt_full(x):
    v = d(x)
    return f"{v:%Y.%m.%d}" if v else "-"


def rng(a, b):
    va, vb = d(a), d(b)
    if not va:
        return "-"
    if vb and vb != va:
        return f"{va:%Y.%m.%d} ~ {vb:%m.%d}"
    return f"{va:%Y.%m.%d}"


def ym(x):
    s = str(x or "")
    return f"{s[:4]}년 {int(s[4:6])}월" if len(s) >= 6 and s[:6].isdigit() else "-"


RANK = {"1": "1순위", "2": "2순위"}


def build_cmpet(rows):
    if not rows:
        return ""
    out = []
    for c in rows:
        out.append(f"<tr><td>{area_label(c.get('HOUSE_TY'))}</td><td>{RANK.get(str(c.get('SUBSCRPT_RANK_CODE')), esc(c.get('SUBSCRPT_RANK_CODE')))}</td>"
                   f"<td>{esc(c.get('RESIDE_SENM'))}</td><td>{esc(c.get('SUPLY_HSHLDCO') or '-')}</td><td>{esc(c.get('REQ_CNT') or '-')}</td><td>{esc(c.get('CMPET_RATE') or '-')}</td></tr>")
    return ('<div class="tbl"><table><thead><tr><th>주택형</th><th>순위</th><th>거주 구분</th><th>공급</th><th>접수</th><th>경쟁률</th></tr></thead><tbody>'
            + "".join(out) + "</tbody></table></div><p class='small muted'>(△N)은 미달 세대 수입니다.</p>")


def build_calc():
    def opts(pairs):
        return '<option value="">선택하세요</option>' + "".join(f'<option value="{v}">{esc(t)}</option>' for t, v in pairs)
    noh = [("주택 소유 중 (0점)", 0), ("1년 미만", 2)] + [(f"{y}년 이상 ~ {y + 1}년 미만", 2 + 2 * y) for y in range(1, 15)] + [("15년 이상", 32)]
    fam = [(f"{n}명", 5 + 5 * n) for n in range(0, 6)] + [("6명 이상", 35)]
    acc = [("6개월 미만", 1), ("6개월 이상 ~ 1년 미만", 2)] + [(f"{y}년 이상 ~ {y + 1}년 미만", 2 + y) for y in range(1, 15)] + [("15년 이상", 17)]
    body = f"""
<h1>청약 가점 계산기 (84점 만점)</h1>
<p class="lead">민영주택 일반공급 가점제 기준입니다. 무주택 기간 32점, 부양가족 35점, 청약통장 가입 기간 17점을 더해 계산합니다.</p>
<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
<form class="card calc" onsubmit="return false">
<label for="a">무주택 기간</label><select id="a">{opts(noh)}</select>
<label for="b">부양가족 수 (본인 제외)</label><select id="b">{opts(fam)}</select>
<label for="c">청약통장 가입 기간</label><select id="c">{opts(acc)}</select>
</form>
<div class="card" style="background:#F9FAFB"><div class="muted">내 청약 가점</div><div><span class="score" id="s">-</span> <span class="muted">/ 84점</span></div>
<div class="small" id="d" style="margin-top:8px">세 항목을 모두 고르면 점수가 나옵니다.</div></div>
</div>
{ad_slot()}
<h2>점수 계산 기준</h2>
<div class="note">
<b>무주택 기간</b>: 만 30세가 된 날(30세 전에 혼인했다면 혼인신고일)부터 계산합니다. 1년 미만 2점, 이후 1년마다 2점씩 늘어 15년 이상이면 32점입니다.<br>
<b>부양가족</b>: 본인을 뺀 수입니다. 0명 5점에서 1명마다 5점씩 늘어 6명 이상이면 35점입니다.<br>
<b>청약통장 가입 기간</b>: 6개월 미만 1점, 6개월~1년 2점, 이후 1년마다 1점씩 늘어 15년 이상이면 17점입니다.<br>
<span class="small muted">세부 인정 기준(직계존속 3년 이상 동일 세대 등)은 입주자모집공고를 따릅니다.</span>
</div>
<script>
function v(id){{var x=document.getElementById(id).value;return x===''?null:+x}}
function up(){{var a=v('a'),b=v('b'),c=v('c');if(a===null||b===null||c===null){{return}}var t=a+b+c;document.getElementById('s').textContent=t;
document.getElementById('d').textContent='무주택 '+a+'점 + 부양가족 '+b+'점 + 통장 '+c+'점';}}
['a','b','c'].forEach(function(i){{document.getElementById(i).addEventListener('change',up)}});
</script>
"""
    return page(f"청약 가점 계산기 - 무주택·부양가족·통장 점수 계산 | {SITE_NAME}", "청약 가점을 84점 만점 기준으로 바로 계산합니다. 무주택 기간, 부양가족 수, 청약통장 가입 기간 점수표 포함.", body, "calc.html")


def build_about():
    body = f"""<h1>{SITE_NAME} 서비스 소개</h1>
<p>{SITE_NAME}는 한국부동산원 청약홈이 공공데이터포털에 공개하는 분양정보를 매일 받아, 단지별 청약 일정과 주택형별 분양가·평당가, 경쟁률을 보기 쉽게 정리하는 사이트입니다.</p>
<p>평당 분양가는 주택형별 최고 공급금액을 공급면적(3.3㎡ 기준)으로 나눈 값의 평균이며, 같은 시·도에서 최근 {LOOKBACK_DAYS}일 동안 공고된 아파트 평균과 비교합니다. 자동으로 정리된 정보이므로 실제 청약 전에는 반드시 청약홈의 입주자모집공고 원문을 확인하세요.</p>
<p>문의: hello@sehucalc.com</p>"""
    return page(f"서비스 소개 | {SITE_NAME}", f"{SITE_NAME} 서비스 소개와 데이터 출처", body, "about.html")


def build_privacy():
    body = f"""<h1>개인정보처리방침</h1>
<p>{SITE_NAME}는 회원가입이 없으며 이름·연락처 등 개인정보를 수집하지 않습니다. 청약 가점 계산기에 입력한 값은 브라우저 안에서만 계산되고 서버로 전송되지 않습니다.</p>
<p>이 사이트는 Google 애드센스 광고를 게재할 수 있으며, Google 등 제3자 광고 사업자는 쿠키를 사용해 이용자의 이전 방문 기록을 바탕으로 광고를 표시할 수 있습니다. 이용자는 Google 광고 설정에서 맞춤 광고를 끌 수 있습니다.</p>
<p>일부 링크는 제휴 링크이며, 이를 통해 구매·상담이 이루어지면 일정 수수료를 받을 수 있습니다.</p>
<p>시행일: {TODAY:%Y년 %m월 %d일}</p>"""
    return page(f"개인정보처리방침 | {SITE_NAME}", "개인정보처리방침", body, "privacy.html")


MANIFEST = {
    "name": "청약레이더 - 아파트 청약 일정·분양가",
    "short_name": "청약레이더",
    "description": "아파트 청약 일정, 분양가, 경쟁률, 청약 달력을 매일 정리합니다.",
    "lang": "ko",
    "start_url": "/?source=pwa",
    "scope": "/",
    "display": "standalone",
    "background_color": "#FFFFFF",
    "theme_color": "#1B64DA",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/icon-mask-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
    "shortcuts": [
        {"name": "청약 달력", "url": "/calendar.html"},
        {"name": "가점 계산기", "url": "/calc.html"},
    ],
}

SW = """const C='cy-%s';
const PRE=['/','/index.html','/calendar.html','/calc.html','/assets/style.css','/offline.html'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(PRE)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{const r=e.request;if(r.method!=='GET'||new URL(r.url).origin!==location.origin)return;
e.respondWith(fetch(r,{cache:'no-cache'}).then(res=>{if(res.ok){const cp=res.clone();caches.open(C).then(c=>c.put(r,cp))}return res})
.catch(()=>caches.match(r).then(m=>m||(r.mode==='navigate'?caches.match('/offline.html'):Response.error()))))});
"""


def write_pwa():
    import shutil
    (OUT / "manifest.webmanifest").write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "sw.js").write_text(SW % TODAY.isoformat(), encoding="utf-8")
    body = '<h1>인터넷 연결이 끊겼어요</h1><p class="lead">연결되면 최신 청약 일정이 다시 보입니다. 이전에 열어 본 페이지는 오프라인에서도 볼 수 있어요.</p><p><a class="btn" href="/">다시 시도</a></p>'
    (OUT / "offline.html").write_text(page(f"오프라인 | {SITE_NAME}", "인터넷 연결이 끊겼습니다.", body, "offline.html"), encoding="utf-8")
    st = ROOT / "static"
    if st.exists():
        for f in st.iterdir():
            shutil.copy2(f, OUT / f.name)


def main():
    global KEY
    KEY = load_key()
    items = enrich(collect())
    (OUT / "apt").mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "style.css").write_text(CSS.strip(), encoding="utf-8")
    (OUT / "index.html").write_text(build_index(items), encoding="utf-8")
    (OUT / "calc.html").write_text(build_calc(), encoding="utf-8")
    (OUT / "calendar.html").write_text(build_calendar(items), encoding="utf-8")
    (OUT / "about.html").write_text(build_about(), encoding="utf-8")
    (OUT / "privacy.html").write_text(build_privacy(), encoding="utf-8")
    urls = ["", "calendar.html", "calc.html", "about.html"]
    for it in items:
        (OUT / "apt" / f"{it['slug']}.html").write_text(build_detail(it, items), encoding="utf-8")
        urls.append(f"apt/{it['slug']}.html")
        if events(it):
            (OUT / "apt" / f"{it['slug']}.ics").write_bytes(build_ics(it).encode("utf-8"))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{SITE_URL}/{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>" for u in urls]
    sm.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    write_pwa()
    print(f"완료: 단지 {len(items)}개, 페이지 {len(urls) + 1}개 → {OUT}")


if __name__ == "__main__":
    main()
