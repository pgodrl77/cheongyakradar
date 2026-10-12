# -*- coding: utf-8 -*-
"""청약콕 계산기 모음(2026-10-12): 취득세·DSR 한도·중도금대출 이자·청약통장 납입.
경쟁 사이트(ireumkuk.co.kr '청약콕') 벤치마킹 — 금융 키워드 계산기는 애드센스 단가가 높고 검색 유입이 큼.
모두 브라우저 안에서만 계산(서버 전송 없음). 주소 ?p=분양가(만원) 로 값을 미리 채울 수 있음(단지 페이지에서 연결).
기준(2026-10-12 확인):
- 취득세: 1주택 6억 이하 1%, 6~9억 (가액(억)×2/3−3)%, 9억 초과 3%. 조정대상지역 2주택 8%·3주택 이상 12%,
  비조정 3주택 8%·4주택 이상 12%. 지방교육세 표준 = 취득세율×0.1, 중과 0.4%. 농특세 85㎡ 초과 0.2%(중과 8%→0.6%, 12%→1.0%).
  생애최초 12억 이하 최대 200만원 감면.
- 스트레스 DSR(2026 하반기): 수도권·규제지역 주담대 3.0%p, 지방 주담대 0.75%p(2단계 연말까지 유지). 은행권 DSR 40%.
- 청약통장 월 납입 인정액 25만원(2024.11~).
"""

TOOLS = [
    ("calc.html", "청약 가점 계산기", "무주택·부양가족·통장 기간으로 84점 만점 가점 계산"),
    ("tax.html", "취득세 계산기", "6~9억 누진 구간, 다주택 중과, 지방교육세·농특세, 생애최초 감면까지"),
    ("dsr.html", "DSR 대출 한도 계산기", "2026 하반기 스트레스 금리(수도권 3.0%p·지방 0.75%p) 반영"),
    ("interest.html", "중도금대출 이자 계산기", "분양가·회차·금리로 이자후불제 이자와 납부 일정 계산"),
    ("bankbook.html", "청약통장 납입 시뮬레이터", "월 25만원 인정액 기준 저축총액과 지역별 예치금 충족 여부"),
    ("rate.html", "경쟁률·당첨 가점 커트라인", "최근 단지별 최저 당첨 가점과 내 점수로 당첨권 확인"),
    ("price.html", "평당 분양가 랭킹", "최근 분양 단지 평당가 순위와 시·도 평균"),
    ("move.html", "손 없는 날 이사 달력", "이사 길일과 입주 일정 맞추기"),
]

COMMON_JS = r"""
function $(i){return document.getElementById(i)}
function nv(i){var x=$(i);if(!x)return 0;var v=parseFloat(String(x.value).replace(/,/g,''));return isNaN(v)?0:v}
function man(v){v=Math.round(v);var neg=v<0;v=Math.abs(v);var e=Math.floor(v/10000),m=v%10000;var s=e?(e+'억'+(m?' '+m.toLocaleString()+'만원':'원')):(m.toLocaleString()+'만원');return (neg?'-':'')+s}
function wonf(v){return Math.round(v).toLocaleString()+'원'}
(function(){try{var p=new URLSearchParams(location.search).get('p');if(p&&$('p')){$('p').value=Math.round(+p)}}catch(e){}})();
"""

CSS = """
.calc input[type=number],.calc input[type=month]{width:100%;height:44px;border:1px solid #D1D6DB;border-radius:8px;padding:0 10px;font:inherit;background:#fff}
.calc .row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.calc .chk{display:flex;align-items:center;gap:8px;font-weight:400;margin-top:14px}
.res .big{font-size:32px;font-weight:700;color:#1B64DA;line-height:1.3}
.res .kv{margin-top:12px}
.ok{color:#0B7A3E;font-weight:700}.ng{color:#C4161C;font-weight:700}
.toolgrid .card b{display:block;margin-bottom:6px}
tr.win td{background:#E9F8EE}tr.lose td{color:#8B95A1}
.myscore{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 12px}.myscore input{width:110px;height:40px;border:1px solid #D1D6DB;border-radius:8px;padding:0 10px;font:inherit}
.rk{font-weight:700;color:#1B64DA;width:36px}
"""

TRUST = '<p class="small muted" style="margin-top:10px">입력한 값은 브라우저 안에서만 계산되며 서버로 전송되지 않습니다. 결과는 참고용이며 실제 세금·대출 조건은 관계기관과 금융회사에서 확인하세요.</p>'


def _layout(form, result, cid):
    return (f'<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">'
            f'<form class="card calc" id="{cid}" onsubmit="return false">{form}</form>'
            f'<div class="card res" style="background:#F9FAFB">{result}</div></div>')


def _others(cur):
    return ('<h2>다른 청약 계산기</h2><div class="grid toolgrid">' +
            "".join(f'<a class="card" href="{u}"><b>{t} →</b><span class="small muted">{d}</span></a>' for u, t, d in TOOLS if u != cur) + "</div>")


def build_tools(page, esc, ad_slot, SITE_NAME):
    cards = "".join(f'<a class="card" href="{u}"><b>{esc(t)} →</b><span class="small muted">{esc(d)}</span></a>' for u, t, d in TOOLS)
    body = f"""<h1>청약 계산기 모음</h1>
<p class="lead">청약 가점부터 취득세, 대출 한도, 중도금 이자까지 청약 전후에 필요한 계산을 한곳에 모았습니다. 모두 무료이고 회원가입이 필요 없습니다.</p>
<div class="grid toolgrid">{cards}</div>
{TRUST}
{ad_slot()}"""
    return page(f"청약 계산기 모음 - 가점·취득세·DSR·중도금 이자 | {SITE_NAME}",
                "청약 가점, 아파트 취득세, 스트레스 DSR 대출 한도, 중도금대출 이자, 청약통장 예치금을 무료로 계산하세요.", body, "tools.html")


def build_tax(page, esc, ad_slot, SITE_NAME, cpa):
    form = """
<label for="p">취득가액(분양가 + 발코니·옵션, 만원)</label><input id="p" type="number" inputmode="numeric" placeholder="예: 65000 (6억 5천만원)">
<label for="n">취득 후 보유 주택 수</label><select id="n"><option value="1">1주택(무주택자가 첫 집)</option><option value="2">2주택</option><option value="3">3주택</option><option value="4">4주택 이상</option></select>
<label for="rg">조정대상지역 여부</label><select id="rg"><option value="0">비조정지역</option><option value="1">조정대상지역(서울 강남3구·용산 등)</option></select>
<label class="chk"><input type="checkbox" id="big"> 전용면적 85㎡ 초과</label>
<label class="chk"><input type="checkbox" id="first"> 생애최초 주택 구입(12억 이하 최대 200만원 감면)</label>
"""
    result = """<div class="muted">예상 취득세 합계</div><div class="big" id="tot">-</div><div class="small" id="rate"></div>
<div class="kv" id="det" hidden></div>"""
    js = r"""
function calc(){var p=nv('p');if(!p){$('tot').textContent='-';$('det').hidden=true;$('rate').textContent='';return}
var n=+$('n').value,rg=$('rg').value==='1',big=$('big').checked,first=$('first').checked;
var heavy=rg?(n==2?8:(n>=3?12:0)):(n==3?8:(n>=4?12:0)),tr,edu,ag;
if(heavy){tr=heavy;edu=0.4;ag=big?(heavy==8?0.6:1.0):0}
else{tr=p<=60000?1:(p<=90000?Math.round((p/10000*2/3-3)*100)/100:3);edu=tr*0.1;ag=big?0.2:0}
var t=p*tr/100,e=p*edu/100,a=p*ag/100,cut=0;
if(first&&n==1&&p<=120000){cut=Math.min(t,200)}
var sum=t-cut+e+a;
$('tot').textContent=man(sum);
$('rate').textContent='취득세율 '+tr+'%'+(heavy?' (다주택 중과)':'')+' · 실효 세율 '+(sum/p*100).toFixed(2)+'%';
var h='<div>취득세</div><div>'+man(t)+'</div>';if(cut)h+='<div>생애최초 감면</div><div>-'+man(cut)+'</div>';
h+='<div>지방교육세</div><div>'+man(e)+'</div><div>농어촌특별세</div><div>'+(a?man(a):'없음(85㎡ 이하)')+'</div><div>합계</div><div><b>'+man(sum)+'</b></div>';
$('det').innerHTML=h;$('det').hidden=false}
document.querySelectorAll('#f input,#f select').forEach(function(x){x.addEventListener('input',calc);x.addEventListener('change',calc)});calc();
"""
    body = f"""<p class="small muted"><a href="tools.html">청약 계산기</a> › 취득세</p>
<h1>아파트 취득세 계산기 (2026년 기준)</h1>
<p class="lead">분양가에 발코니 확장비·옵션을 더한 금액을 넣으면 취득세·지방교육세·농어촌특별세를 한 번에 계산합니다. 6~9억 구간 누진세율과 다주택 중과, 생애최초 감면을 반영했습니다.</p>
{_layout(form, result, "f")}
{TRUST}
{ad_slot()}
<h2>2026년 주택 취득세율</h2>
<div class="tbl"><table style="min-width:520px"><thead><tr><th>구분</th><th>취득세</th><th>지방교육세</th><th>농특세(85㎡ 초과)</th></tr></thead><tbody>
<tr><td>1주택 6억 이하</td><td>1%</td><td>0.1%</td><td>0.2%</td></tr>
<tr><td>1주택 6억 초과~9억 이하</td><td>1.01~2.99% (가액(억)×2/3−3)</td><td>취득세율의 1/10</td><td>0.2%</td></tr>
<tr><td>1주택 9억 초과</td><td>3%</td><td>0.3%</td><td>0.2%</td></tr>
<tr><td>조정 2주택 · 비조정 3주택</td><td>8%</td><td>0.4%</td><td>0.6%</td></tr>
<tr><td>조정 3주택 이상 · 비조정 4주택 이상</td><td>12%</td><td>0.4%</td><td>1.0%</td></tr>
</tbody></table></div>
<div class="note" style="margin-top:12px">분양 아파트는 <b>잔금일(또는 등기일 중 빠른 날)</b>이 취득일이고, 그날부터 60일 안에 신고·납부해야 합니다. 일시적 2주택(종전 주택을 기한 안에 처분)은 1주택 세율이 적용될 수 있고, 생애최초 감면은 3개월 안 전입·3년 실거주 등 요건을 어기면 추징됩니다.</div>
{cpa(["move"], "잔금일 맞춰 이사 준비")}
{_others("tax.html")}
<script>{COMMON_JS}{js}</script>"""
    return page(f"취득세 계산기 2026 - 아파트 분양 취득세·지방교육세 | {SITE_NAME}",
                "2026년 아파트 취득세를 계산합니다. 6~9억 누진 구간, 조정대상지역 다주택 중과, 지방교육세·농특세, 생애최초 200만원 감면 반영.", body, "tax.html")


def build_dsr(page, esc, ad_slot, SITE_NAME):
    form = """
<label for="inc">연소득(세전, 만원)</label><input id="inc" type="number" inputmode="numeric" placeholder="예: 6000">
<label for="oth">기존 대출의 1년 원리금 상환액(만원)</label><input id="oth" type="number" inputmode="numeric" placeholder="없으면 0" value="0">
<div class="row2"><div><label for="r">대출 금리(%)</label><input id="r" type="number" step="0.01" value="4.2"></div>
<div><label for="y">만기(년)</label><select id="y"><option>30</option><option>40</option><option>20</option><option>10</option></select></div></div>
<label for="ar">주택 지역</label><select id="ar"><option value="3.0">수도권·규제지역 (스트레스 3.0%p)</option><option value="0.75">지방 (스트레스 0.75%p)</option></select>
<label for="lim">DSR 한도</label><select id="lim"><option value="40">은행권 40%</option><option value="50">2금융권 50%</option></select>
"""
    result = """<div class="muted">스트레스 DSR 적용 최대 대출 가능액</div><div class="big" id="amt">-</div><div class="small" id="sub"></div>
<div class="kv" id="det" hidden></div>"""
    js = r"""
function pv(m,ry,yrs){var i=ry/100/12,n=yrs*12;return i?m*(1-Math.pow(1+i,-n))/i:m*n}
function pmt(P,ry,yrs){var i=ry/100/12,n=yrs*12;return i?P*i/(1-Math.pow(1+i,-n)):P/n}
function calc(){var inc=nv('inc');if(!inc){$('amt').textContent='-';$('det').hidden=true;$('sub').textContent='';return}
var room=(inc*nv('lim')/100-nv('oth'))/12,r=nv('r'),y=+$('y').value,s=+$('ar').value;
if(room<=0){$('amt').textContent='0원';$('sub').textContent='기존 대출 상환액이 이미 DSR 한도를 넘었습니다.';$('det').hidden=true;return}
var a=pv(room,r+s,y),b=pv(room,r,y);
$('amt').textContent=man(a);$('sub').textContent='스트레스 금리 '+(r+s).toFixed(2)+'%로 심사 · 실제 상환은 '+r+'% 기준';
$('det').innerHTML='<div>스트레스 없을 때</div><div>'+man(b)+'</div><div>스트레스로 줄어든 금액</div><div>-'+man(b-a)+'</div><div>월 상환 가능액</div><div>'+man(room)+'</div><div>한도 대출 시 실제 월 상환</div><div>'+man(pmt(a,r,y))+' (원리금균등)</div>';$('det').hidden=false}
document.querySelectorAll('#f input,#f select').forEach(function(x){x.addEventListener('input',calc);x.addEventListener('change',calc)});calc();
"""
    body = f"""<p class="small muted"><a href="tools.html">청약 계산기</a> › DSR 한도</p>
<h1>DSR 대출 한도 계산기 (2026 하반기 스트레스 DSR)</h1>
<p class="lead">연소득과 기존 대출을 넣으면 스트레스 금리를 더한 심사 금리로 주택담보대출 최대 한도를 역산합니다. 잔금대출을 얼마나 받을 수 있을지 미리 가늠해 보세요.</p>
{_layout(form, result, "f")}
{TRUST}
{ad_slot()}
<h2>2026년 하반기 스트레스 DSR 기준</h2>
<div class="kv"><div>수도권·규제지역 주담대</div><div>스트레스 금리 <b>3.0%p</b> 가산</div><div>지방 주담대</div><div>0.75%p 가산 (2단계, 2026년 말까지 유지)</div><div>기타 대출</div><div>1.5%p (신용대출은 잔액 1억원 초과 시)</div><div>DSR 한도</div><div>은행권 40%, 2금융권 50%</div></div>
<div class="note" style="margin-top:12px">DSR 한도와 별개로 <b>LTV(주택가격 대비 대출 비율)</b>와 정부 대책에 따른 주담대 총액 상한이 함께 걸립니다. 분양 아파트 잔금대출은 감정가·KB시세 기준으로 다시 심사되니, 실제 한도는 은행 상담으로 확인하세요. 스트레스 금리는 매년 6월·12월에 다시 정해집니다.</div>
{_others("dsr.html")}
<script>{COMMON_JS}{js}</script>"""
    return page(f"DSR 대출 한도 계산기 - 2026 스트레스 DSR 반영 | {SITE_NAME}",
                "연소득으로 주택담보대출 최대 한도를 계산합니다. 2026년 하반기 스트레스 DSR(수도권·규제지역 3.0%p, 지방 0.75%p) 반영.", body, "dsr.html")


def build_interest(page, esc, ad_slot, SITE_NAME):
    form = """
<label for="p">분양가(만원)</label><input id="p" type="number" inputmode="numeric" placeholder="예: 65000">
<div class="row2"><div><label for="c">계약금 비율(%)</label><input id="c" type="number" value="10"></div>
<div><label for="m">중도금 비율(%)</label><input id="m" type="number" value="60"></div></div>
<div class="row2"><div><label for="k">중도금 회차</label><input id="k" type="number" value="6"></div>
<div><label for="r">중도금대출 금리(%)</label><input id="r" type="number" step="0.01" value="4.5"></div></div>
<label for="t">1회차 중도금부터 잔금(입주)까지 개월 수</label><input id="t" type="number" value="24">
<label for="ty">이자 조건</label><select id="ty"><option value="after">이자후불제(입주 때 한꺼번에)</option><option value="free">무이자(시행사 부담)</option><option value="pay">유이자(매달 납부)</option></select>
"""
    result = """<div class="muted">입주 때까지 쌓이는 중도금 이자</div><div class="big" id="int">-</div><div class="small" id="sub"></div>
<div class="kv" id="det" hidden></div>"""
    js = r"""
function calc(){var p=nv('p');if(!p){$('int').textContent='-';$('det').hidden=true;$('sub').textContent='';return}
var c=p*nv('c')/100,mid=p*nv('m')/100,k=Math.max(1,Math.round(nv('k'))),r=nv('r'),T=nv('t'),ty=$('ty').value,each=mid/k,iv=0,rows='';
for(var j=0;j<k;j++){var at=Math.round(T*j/k),left=T-at;iv+=each*r/100/12*left}
if(ty==="free")iv=0;
var bal=p-c-mid;
$('int').textContent=ty==='free'?'0원 (무이자)':man(iv);
$('sub').textContent=ty==='pay'?'매달 평균 '+man(iv/T)+'씩 나눠 냅니다':(ty==='after'?'잔금 낼 때 함께 냅니다':'');
$('det').innerHTML='<div>계약금 ('+nv('c')+'%)</div><div>'+man(c)+'</div><div>중도금 ('+nv('m')+'%, '+k+'회)</div><div>회당 '+man(each)+'</div><div>잔금</div><div>'+man(bal)+'</div><div>잔금 + 이자</div><div><b>'+man(bal+(ty==="after"?iv:0))+'</b></div><div>총 부담(이자 포함)</div><div>'+man(p+iv)+'</div>';$('det').hidden=false}
document.querySelectorAll('#f input,#f select').forEach(function(x){x.addEventListener('input',calc);x.addEventListener('change',calc)});calc();
"""
    body = f"""<p class="small muted"><a href="tools.html">청약 계산기</a> › 중도금대출 이자</p>
<h1>중도금대출 이자 계산기</h1>
<p class="lead">분양가와 중도금 회차, 금리를 넣으면 입주 때까지 쌓이는 중도금 이자와 계약금·잔금을 계산합니다. 단지 페이지에서 들어오면 분양가가 미리 채워집니다.</p>
{_layout(form, result, "f")}
{TRUST}
{ad_slot()}
<h2>중도금 이자, 이렇게 계산합니다</h2>
<div class="note">중도금은 보통 분양가의 60%를 4~6회로 나눠 내고, 회차마다 대출이 실행된 날부터 잔금일까지 이자가 붙습니다. 그래서 <b>먼저 낸 회차일수록 이자가 많고</b>, 이자후불제라면 이 이자를 잔금 때 한꺼번에 냅니다. 이 계산기는 회차를 고르게 나눠 단순 이자로 계산하므로, 실제 회차 날짜와 은행 금리는 입주자모집공고문과 대출 안내문으로 확인하세요.</div>
{_others("interest.html")}
<script>{COMMON_JS}{js}</script>"""
    return page(f"중도금대출 이자 계산기 - 이자후불제·잔금 계산 | {SITE_NAME}",
                "분양가, 중도금 회차, 금리로 이자후불제 중도금 이자와 계약금·잔금 납부액을 계산합니다.", body, "interest.html")


def build_bankbook(page, esc, ad_slot, SITE_NAME, today):
    form = f"""
<label for="s">청약통장 가입 연월</label><input id="s" type="month" max="{today:%Y-%m}" value="{today.year - 3}-{today:%m}">
<label for="m">월 납입액(만원)</label><input id="m" type="number" value="25">
<label for="ar">청약할 지역</label><select id="ar"><option value="0">서울·부산</option><option value="1">기타 광역시</option><option value="2">그 밖의 시·군</option></select>
"""
    result = """<div class="muted">공공분양 인정 저축총액</div><div class="big" id="tot">-</div><div class="small" id="sub"></div>
<div class="kv" id="det" hidden></div>"""
    js = r"""
var DEP=[[300,600,1000,1500],[250,400,700,1000],[200,300,400,500]],LAB=['전용 85㎡ 이하','102㎡ 이하','135㎡ 이하','모든 면적'];
function calc(){var s=$('s').value;if(!s){return}var q=s.split('-'),t=new Date();var n=(t.getFullYear()-(+q[0]))*12+(t.getMonth()+1-(+q[1]))+1;if(n<1)n=1;
var m=nv('m'),pub=n*Math.min(m,25),pri=n*m,a=+$('ar').value,yrs=Math.floor(n/12),pt=n<6?1:(n<12?2:Math.min(17,2+yrs));
$('tot').textContent=man(pub);$('sub').textContent='납입 '+n+'회차 · 실제 납입액 '+man(pri)+' (월 25만원까지만 인정)';
var h='<div>통장 가입기간 가점</div><div>'+pt+'점 / 17점</div><div>1순위 기간</div><div>'+(n>=24?'<span class="ok">규제지역 포함 충족(24회 이상)</span>':(n>=12?'<span class="ok">수도권 충족</span> · 규제지역은 24회 필요':(n>=6?'<span class="ok">비수도권 충족</span> · 수도권은 12회 필요':'<span class="ng">아직 미충족</span>')))+'</div>';
for(var i=0;i<4;i++){var need=DEP[a][i];h+='<div>민영 예치금 '+LAB[i]+'</div><div>'+(pri>=need?'<span class="ok">충족</span>':'<span class="ng">'+man(need-pri)+' 부족</span>')+' (기준 '+man(need)+')</div>'}
$('det').innerHTML=h;$('det').hidden=false}
document.querySelectorAll('#f input,#f select').forEach(function(x){x.addEventListener('input',calc);x.addEventListener('change',calc)});calc();
"""
    body = f"""<p class="small muted"><a href="tools.html">청약 계산기</a> › 청약통장 납입</p>
<h1>청약통장 납입 시뮬레이터 — 저축총액·예치금 확인</h1>
<p class="lead">가입 연월과 월 납입액을 넣으면 공공분양에서 인정되는 저축총액(월 25만원 한도), 민영주택 지역별 예치금 충족 여부, 통장 가입기간 가점을 바로 보여 줍니다.</p>
{_layout(form, result, "f")}
{TRUST}
{ad_slot()}
<h2>민영주택 청약 예치금 기준</h2>
<div class="tbl"><table style="min-width:520px"><thead><tr><th>전용면적</th><th>서울·부산</th><th>기타 광역시</th><th>그 밖의 시·군</th></tr></thead><tbody>
<tr><td>85㎡ 이하</td><td>300만원</td><td>250만원</td><td>200만원</td></tr>
<tr><td>102㎡ 이하</td><td>600만원</td><td>400만원</td><td>300만원</td></tr>
<tr><td>135㎡ 이하</td><td>1,000만원</td><td>700만원</td><td>400만원</td></tr>
<tr><td>모든 면적</td><td>1,500만원</td><td>1,000만원</td><td>500만원</td></tr>
</tbody></table></div>
<div class="note" style="margin-top:12px">공공분양은 납입 횟수와 인정 금액(2024년 11월부터 월 25만원까지)으로 순위를 가리고, 민영주택은 모집공고일 전날까지 지역별 예치금이 들어 있으면 됩니다. 예치금은 입주자모집공고일 기준 <b>주민등록상 거주지</b>로 판단합니다.</div>
{_others("bankbook.html")}
<script>{COMMON_JS}{js}</script>"""
    return page(f"청약통장 납입 시뮬레이터 - 월 25만원 인정액·예치금 계산 | {SITE_NAME}",
                "청약통장 가입 연월과 월 납입액으로 공공분양 인정 저축총액, 민영주택 지역별 예치금 충족 여부, 통장 가점을 계산합니다.", body, "bankbook.html")


def build_terms(page, SITE_NAME, CONTACT_EMAIL):
    body = f"""<h1>이용약관</h1>
<h2>1. 목적</h2><p>이 약관은 {SITE_NAME}(이하 "사이트")가 제공하는 청약 일정·분양가·경쟁률 정보와 계산기 서비스의 이용 조건을 정합니다.</p>
<h2>2. 정보의 성격</h2><p>사이트의 정보는 한국부동산원 청약홈 등 공공데이터를 자동으로 정리한 참고 자료입니다. 공고 정정, 데이터 지연, 입력 오류가 반영되지 않을 수 있으며, 청약 신청 전에는 반드시 입주자모집공고문 원문을 확인해야 합니다.</p>
<h2>3. 계산기</h2><p>취득세·대출 한도·이자·가점 계산 결과는 입력값과 일반 기준으로 낸 추정치입니다. 실제 세액·대출 한도는 관할 지자체와 금융회사의 심사에 따라 달라집니다. 입력값은 이용자의 브라우저 안에서만 처리되며 서버에 저장되지 않습니다.</p>
<h2>4. 책임의 한계</h2><p>사이트 정보를 바탕으로 한 청약·투자·대출 판단과 그 결과에 대한 책임은 이용자에게 있습니다. 사이트는 정보의 정확성을 위해 노력하지만 완전성을 보증하지 않습니다.</p>
<h2>5. 광고와 제휴</h2><p>사이트에는 Google 애드센스 광고와 제휴 링크가 포함될 수 있으며, 제휴 링크는 "광고·제휴"로 표시합니다.</p>
<h2>6. 문의</h2><p>{CONTACT_EMAIL}</p>
<p class="small muted">시행일: 2026년 10월 12일</p>"""
    return page(f"이용약관 | {SITE_NAME}", f"{SITE_NAME} 이용약관", body, "terms.html")
