"""청약콕 주간 영상 → 네이버 클립(청약콕 전용 네이버 아이디) 업로드.
(2026-10-12) 사용:
  python cy_clip.py login            # 처음 한 번: 청약콕 아이디로 로그인(창이 뜸, 로그인 상태 유지 켜고 IP보안 OFF)
  python cy_clip.py check            # 로그인 확인
  python cy_clip.py [auto] [--date YYYY-MM-DD]   # clips/cy-<date>-weekly.mp4 를 클립으로 올림(auto 는 월요일 KST 만)
- 살림템 클립(@sallimtemlab, pgodrl77)과 브랜드를 섞지 않으려고 전용 크롬 프로필 %LOCALAPPDATA%\\naver-cy-profile 을 쓴다.
- 설명 = clip.py 가 만든 cy-<date>-weekly.json 의 desc + 해시태그(300자), 카테고리 경제, AI 활용 표시 켬(나레이션이 AI 음성).
- 기록: clips/cy_clip_log.txt, clips/cy_clip_done.json
"""
import datetime as dt, json, os, pathlib, re, sys, time
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
CLIPS = ROOT / "clips"
PROFILE = os.path.join(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home())), "naver-cy-profile")
STATE = CLIPS / "cy_naver_state.json"
LOG = CLIPS / "cy_clip_log.txt"
DONE = CLIPS / "cy_clip_done.json"
KST = dt.timezone(dt.timedelta(hours=9))
CAT1 = "경제"
CLIPS.mkdir(exist_ok=True)


def log(*a):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        print(line, flush=True)
    except Exception:
        pass


def open_ctx(p, headless=True):
    ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=headless, locale="ko-KR",
        args=["--disable-blink-features=AutomationControlled", "--start-maximized"], no_viewport=not headless)
    if STATE.exists() and not any(c["name"] == "NID_AUT" for c in ctx.cookies("https://naver.com")):
        try:
            ctx.add_cookies(json.loads(STATE.read_text(encoding="utf-8"))["cookies"])
        except Exception as e:
            log("cookie restore warn", e)
    return ctx


def save_state(ctx):
    try:
        if any(c["name"] == "NID_AUT" for c in ctx.cookies("https://naver.com")):
            ctx.storage_state(path=str(STATE))
    except Exception as e:
        log("state save warn", e)


def logged_in(page):
    page.goto("https://clipcreators.naver.com/web/dashboard", wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    return "nidlogin" not in page.url and "clipcreators" in page.url, page.url


def login():
    """창을 띄워 사용자가 직접 로그인. 로그인되면(클립 크리에이터 화면 도달) 상태 저장 후 닫힘. 최대 30분."""
    with sync_playwright() as p:
        ctx = open_ctx(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login?mode=form&url=https%3A%2F%2Fclipcreators.naver.com%2Fweb%2Fdashboard",
                  wait_until="commit")
        ok = False
        end = time.time() + 1800
        while time.time() < end:
            try:
                page.wait_for_timeout(2000)
                if "clipcreators.naver.com" in page.url and "nid.naver.com" not in page.url:
                    ok = True
                    break
            except Exception:
                break
        if ok:
            page.wait_for_timeout(5000)
            save_state(ctx)
        log("login", "OK" if ok else "TIMEOUT", page.url[:80] if ok else "")
        ctx.close()


def upload(mp4, text):
    with sync_playwright() as p:
        ctx = open_ctx(p, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            ok, url = logged_in(page)
            if not ok:
                raise RuntimeError("청약콕 네이버 로그인이 필요함 → python cy_clip.py login (" + url[:60] + ")")
            page.goto("https://clipcreators.naver.com/web/upload", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.set_input_files("input[type=file]", str(mp4))
            page.wait_for_url(re.compile(r"/web/draft/\d+"), timeout=120000)
            draft = page.url
            page.wait_for_timeout(4000)
            ta = page.locator("textarea[class*='ClipDetailForm_textarea']")
            ta.click()
            ta.fill(text)
            page.keyboard.type(" ")
            page.keyboard.press("Backspace")
            page.click("button[class*='dropdownPrimar']")
            page.wait_for_timeout(800)
            page.locator("button[class*='dropdownOption']", has_text=CAT1).first.click()
            page.wait_for_timeout(800)
            try:
                page.click("button[class*='dropdownSecond']")
                page.wait_for_timeout(800)
                opts = page.locator("button[class*='dropdownOption']:visible")
                if opts.count():
                    opts.first.click()
            except Exception:
                pass
            tg = page.locator("button[class*='Toggle_toggle']").nth(0)  # AI 활용 설정
            if "toggleOn" not in (tg.get_attribute("class") or ""):
                tg.click()
                page.wait_for_timeout(700)
            sub = page.locator("button[class*='ClipDetailForm_submitBtn']")
            end = time.time() + 600
            while time.time() < end:
                if sub.is_enabled() and page.locator("button[class*='coverSelecte']").count():
                    break
                page.wait_for_timeout(3000)
            else:
                raise RuntimeError("인코딩/등록 버튼 대기 시간 초과 " + draft)
            sub.click()
            page.wait_for_timeout(3000)
            if page.locator("text=동영상 처리중").count():
                page.locator("button:visible, a:visible", has_text="확인").first.click(force=True)
                page.wait_for_timeout(2000)
                log("  인코딩 끝나면 자동 등록되는 상태로 접수")
            else:
                end = time.time() + 120
                while time.time() < end and "/web/draft/" in page.url:
                    page.wait_for_timeout(2000)
                if "/web/draft/" in page.url:
                    page.screenshot(path=str(CLIPS / "cy_fail.png"), full_page=True)
                    raise RuntimeError("등록 후에도 초안 화면 그대로 " + draft)
            save_state(ctx)
            return draft
        except Exception:
            try:
                page.screenshot(path=str(CLIPS / "cy_error.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            ctx.close()


def main():
    a = sys.argv
    if "login" in a:
        return login()
    if "check" in a:
        with sync_playwright() as p:
            ctx = open_ctx(p)
            try:
                ok, url = logged_in(ctx.pages[0] if ctx.pages else ctx.new_page())
                if ok:
                    save_state(ctx)
                log("check", "로그인됨" if ok else "로그인 필요", url[:80])
            finally:
                ctx.close()
        return
    day = dt.date.fromisoformat(a[a.index("--date") + 1]) if "--date" in a else dt.datetime.now(KST).date()
    if "auto" in a and day.weekday() != 0:
        print("cy_clip: not Monday KST, skip")
        return
    mp4 = CLIPS / f"cy-{day.isoformat()}-weekly.mp4"
    meta = CLIPS / f"cy-{day.isoformat()}-weekly.json"
    if not mp4.exists() or not meta.exists():
        log("영상 없음:", mp4.name)
        return
    done = json.loads(DONE.read_text(encoding="utf-8")) if DONE.exists() else {}
    if mp4.name in done:
        log("이미 올림:", mp4.name)
        return
    m = json.loads(meta.read_text(encoding="utf-8"))
    text = (m["title"] + "\n\n" + m["desc"] + "\n\n" + " ".join(m["tags"][:5]))[:300]
    log("업로드 시작", mp4.name)
    draft = upload(mp4, text)
    done[mp4.name] = {"draft": draft, "at": time.strftime("%Y-%m-%d %H:%M")}
    DONE.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    log("업로드 완료", mp4.name, draft)


if __name__ == "__main__":
    main()
