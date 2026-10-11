"""이사 손 없는 날(길일) 달력 페이지. data/sonless.json(음력 9·10·19·20·29·30일) 을 읽어 만든다.
손 없는 날 데이터는 korean_lunar_calendar 로 미리 계산해 둔 것(2026~2028)."""
import datetime as dt
import json
import pathlib

WD = "월화수목금토일"


def load():
    p = pathlib.Path(__file__).parent / "data" / "sonless.json"
    return {dt.date.fromisoformat(k): v for k, v in json.loads(p.read_text(encoding="utf-8")).items()}


def build(today, page, esc, ad_slot, site_name, aff_html=None, cpa_html=None):
    days = load()
    start = today.replace(day=1)
    months = []
    y, m = start.year, start.month
    for _ in range(12):
        months.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    nxt = [d for d in sorted(days) if d >= today][:6]
    wk = ' · <span class="b b-soon">주말</span>'
    soon = "".join(
        f'<li><b>{d:%m월 %d일}({WD[d.weekday()]})</b> <span class="muted small">음력 {esc(days[d])}</span>'
        f'{wk if d.weekday() >= 5 else ""}</li>' for d in nxt)
    blocks = []
    for (yy, mm) in months:
        ds = [d for d in sorted(days) if d.year == yy and d.month == mm]
        if not ds:
            continue
        rows = "".join(
            f'<tr><td>{d:%m.%d}({WD[d.weekday()]})</td><td>음력 {esc(days[d])}</td>'
            f'<td>{"주말 — 예약 경쟁·요금 높음" if d.weekday() >= 5 else ("평일 — 비교적 여유" if d.weekday() < 4 else "금요일")}</td></tr>'
            for d in ds)
        blocks.append(f'<h3 id="m{yy}{mm:02d}">{yy}년 {mm}월 손 없는 날</h3>'
                      f'<div class="tbl"><table style="min-width:420px"><thead><tr><th>날짜</th><th>음력</th><th>참고</th></tr></thead><tbody>{rows}</tbody></table></div>')
    y1, y2 = months[0][0], months[-1][0]
    yr = f"{y1}" if y1 == y2 else f"{y1}·{y2}"
    body = f"""
<p class="small muted"><a href="index.html">청약 일정</a> › 이사 날짜</p>
<h1>손 없는 날 달력 {yr} — 이사·입주 길일 한눈에</h1>
<p class="lead">손 없는 날은 음력으로 끝자리가 9·0인 날(9·10·19·20·29·30일)입니다. 한 달에 6일 안팎이라 이삿짐센터 예약이 몰리고 요금도 오르는 편이니, 입주 날짜가 정해졌다면 일찍 예약하는 것이 좋습니다.</p>
<h2>가장 가까운 손 없는 날</h2>
<ul class="note" style="list-style:none;padding-left:18px">{soon}</ul>
{cpa_html(["move", "clean"], "손 없는 날 이사, 견적부터 먼저") if cpa_html else ''}
{ad_slot()}
<h2>월별 손 없는 날</h2>
{''.join(blocks)}
<h2>입주 날짜 잡을 때 같이 보면 좋은 것</h2>
<ul>
<li><b>입주 지정 기간:</b> 신축 아파트는 보통 입주 지정 기간(대개 45~60일)이 정해져 있고, 기간이 지나면 관리비·잔금 연체 이자가 붙을 수 있습니다. 손 없는 날이라도 지정 기간 안인지 먼저 확인하세요.</li>
<li><b>엘리베이터·이사 예약:</b> 신축 단지는 관리사무소에 엘리베이터 사용 예약을 해야 하는 곳이 많고, 손 없는 날·주말은 먼저 마감됩니다.</li>
<li><b>요금:</b> 같은 거리라도 손 없는 날·주말·월말은 이사 요금이 더 붙는 경우가 많습니다. 날짜에 얽매이지 않는다면 평일 일반일이 가장 저렴합니다.</li>
<li><b>잔금·대출 실행일:</b> 잔금 대출 실행일과 이사 날짜가 엇갈리지 않게 은행과 날짜를 맞춰 두세요.</li>
</ul>
<p class="small muted">손 없는 날은 민속 풍습이며, 음력 날짜는 한국천문연구원 음양력 기준으로 계산했습니다.</p>
<h2>신축 입주 준비<span class="tag">광고·제휴</span></h2>
{aff_html('moveday') if aff_html else ''}
"""
    title = f"손 없는 날 {yr} 이사 길일 달력 — 월별 날짜·음력 | {site_name}"
    desc = f"{yr}년 손 없는 날(이사 길일)을 월별로 정리했습니다. 음력 9·10·19·20·29·30일, 주말 여부와 입주 날짜 잡을 때 확인할 점."
    return page(title, desc, body, "move.html")
