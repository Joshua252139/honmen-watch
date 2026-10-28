import os, json
from playwright.sync_api import sync_playwright
URL = "https://license-renew.tokyo-madoguchi-yoyaku.com/police-pref-tokyo/index_000.html"
STEPS = json.load(open("probe/steps.json", encoding="utf-8"))
CLICKABLES = """() => [...document.querySelectorAll('*')].filter(e => {
  const s = getComputedStyle(e); return (s.cursor === 'pointer' || e.onclick || e.tagName==='A' || e.tagName==='BUTTON' || e.tagName==='SELECT' || (e.tagName==='INPUT' && e.type!=='hidden'))
    && e.offsetParent !== null && e.innerText !== undefined;
}).map(e => ({tag:e.tagName, t:(e.innerText||e.value||e.name||'').trim().replace(/\\s+/g,' ').slice(0,80)})).filter(x => x.t)"""
os.makedirs("debug", exist_ok=True)
def cap(pg, n):
    pg.screenshot(path=f"debug/tokyo_{n:02d}.png", full_page=True)
    open(f"debug/tokyo_{n:02d}.html", "w", encoding="utf-8").write(pg.content())
    seen, out = set(), []
    for x in pg.evaluate(CLICKABLES):
        k = (x["tag"], x["t"])
        if k not in seen: seen.add(k); out.append(x)
    json.dump(out, open(f"debug/tokyo_{n:02d}_click.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(n, pg.url, len(out))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(locale="ja-JP", timezone_id="Asia/Tokyo")
    logs = []
    pg.context.on("console", lambda m: logs.append(f"console {m.type}: {m.text}"))
    pg.context.on("response", lambda r: logs.append(f"resp {r.status} {r.url}") if "tokyo-madoguchi" in r.url else None)
    pg.goto(URL, wait_until="networkidle", timeout=60000); cap(pg, 0)
    for i, text in enumerate(STEPS, 1):
        try:
            loc = pg.get_by_text(text, exact=True).first
            with pg.context.expect_page(timeout=5000) as newp:
                loc.click()
            pg = newp.value
        except Exception:
            pass
        pg.wait_for_load_state("networkidle"); cap(pg, i)
    pg.wait_for_timeout(5000); cap(pg, 9)
    print("TEXT:", pg.evaluate("() => document.body.innerText")[:1500])
    try:
        js = pg.evaluate("async () => (await fetch('/police-pref-tokyo/01/js/MKAYMA001MessagesJa.js')).text()")
        import re
        for m in re.findall(r".{0,40}M340.{0,200}", js): print("MSG:", m)
        open("debug/messages.js","w",encoding="utf-8").write(js)
    except Exception as e: print("msgfetch", e)
    print("\n".join(logs[-60:]))
    b.close()
