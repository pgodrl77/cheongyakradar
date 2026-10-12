"""사이트 검색(2026-10-11): 정적 사이트라 search.json 을 받아 브라우저에서 바로 거름.
- 모든 페이지 상단 검색창(입력하면 바로 아래에 최대 8개), Enter → search.html?q= 전체 결과
- 단지명·주소·지역·시공사·공급유형을 띄어쓰기 무시하고 모든 낱말이 들어간 단지만
"""
import json

JS = r"""
(function(){
var f=document.getElementById('sf'),q=document.getElementById('q'),box=document.getElementById('sres'),D=null,P=null;
function norm(s){return String(s||'').toLowerCase().replace(/\s+/g,'')}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function load(){if(!P)P=fetch('/search.json').then(function(r){return r.json()}).then(function(d){D=d.map(function(x){x.h=norm([x.n,x.a,x.r,x.b,x.k].join(' '));return x});return D});return P}
function find(v){var t=String(v||'').trim().toLowerCase().split(/\s+/).filter(Boolean).map(norm);if(!t.length)return[];
var o=D.filter(function(x){return t.every(function(w){return x.h.indexOf(w)>=0})});
o.sort(function(a,b){var an=norm(a.n).indexOf(t[0])>=0?0:1,bn=norm(b.n).indexOf(t[0])>=0?0:1;return an-bn||a.o-b.o});return o}
function row(x){return '<a href="/apt/'+x.u+'.html"><span class="b b-'+x.c+'">'+esc(x.s)+'</span> <b>'+esc(x.n)+'</b><span class="small muted"> '+esc(x.r)+(x.d?' · '+esc(x.d):'')+'</span></a>'}
window.cySearch={load:load,find:find,row:row,esc:esc};
if(!q)return;
q.addEventListener('focus',load);
q.addEventListener('input',function(){var v=q.value;if(!v.trim()){box.hidden=true;return}
load().then(function(){var o=find(v);box.innerHTML=o.length?o.slice(0,8).map(row).join('')+(o.length>8?'<a class="all" href="/search.html?q='+encodeURIComponent(v)+'">검색 결과 '+o.length+'건 모두 보기</a>':''):'<div class="none">"'+esc(v)+'"에 맞는 단지가 없습니다</div>';box.hidden=false})});
document.addEventListener('click',function(e){if(!f.contains(e.target))box.hidden=true});
q.addEventListener('keydown',function(e){if(e.key==='Escape')box.hidden=true});
})();
"""

CSS = """
.srch{position:relative;max-width:560px;margin:14px auto 0}
.srch form{display:flex;gap:8px}
.srch input{flex:1;min-width:0;height:44px;border:1px solid #D1D6DB;border-radius:10px;padding:0 14px;font:inherit;font-size:15px;background:#fff;color:#191F28}
.srch input:focus{outline:none;border-color:#1B64DA;box-shadow:0 0 0 3px #E8F3FF}
.srch button{height:44px;padding:0 16px;border:0;border-radius:10px;background:#1B64DA;color:#fff;font:inherit;font-weight:700;cursor:pointer}
.sres{position:absolute;left:0;right:0;top:50px;z-index:20;background:#fff;border:1px solid #E5E8EB;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.08);overflow:hidden}
.sres a,.sres .none{display:block;padding:10px 14px;border-top:1px solid #F2F4F6;color:#191F28;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sres a:first-child{border-top:0}.sres a:hover{background:#F9FAFB}.sres .all{color:#1B64DA;font-weight:500}.sres .none{color:#8B95A1}
.slist a{display:block;padding:12px 0;border-bottom:1px solid #F2F4F6;color:#191F28;text-decoration:none}
"""


def bar(up):
    return (f'<div class="wrap"><div class="srch" id="sf"><form action="{up}search.html" role="search">'
            '<input id="q" name="q" type="search" placeholder="단지명·지역 검색 (예: 부천, 롯데캐슬, 행복주택)" autocomplete="off" aria-label="청약 단지 검색">'
            '<button type="submit">검색</button></form><div id="sres" class="sres" hidden></div></div></div>')


def index(items, short_addr, fmt_date):
    out = []
    for i, it in enumerate(items):
        r = it["d"]
        nx = None
        out.append({"n": r.get("HOUSE_NM") or "", "a": r.get("HSSPLY_ADRES") or "", "r": it.get("region") or "",
                    "b": r.get("CNSTRCT_ENTRPS_NM") or "", "k": it.get("kind") or "",
                    "s": it["status"][1], "c": it["status"][0], "u": it["slug"], "o": i,
                    "d": short_addr(r.get("HSSPLY_ADRES"))})
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


PAGE_BODY = """
<h1>청약 단지 검색</h1>
<p class="lead" id="sq">단지명이나 지역을 입력해 보세요.</p>
<div class="slist" id="sl"></div>
<script>
(function(){var v=new URLSearchParams(location.search).get('q')||'',S=window.cySearch,q=document.getElementById('q');if(q)q.value=v;
if(!v.trim()||!S)return;S.load().then(function(){var o=S.find(v);
document.getElementById('sq').textContent='"'+v+'" 검색 결과 '+o.length+'건';
document.getElementById('sl').innerHTML=o.length?o.map(S.row).join(''):'<p class="muted">맞는 단지가 없습니다. 지역 이름(예: 수원, 세종)이나 단지 이름 일부로 다시 검색해 보세요.</p>'})})();
</script>
"""
