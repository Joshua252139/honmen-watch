import os, json
from playwright.sync_api import sync_playwright
URL = "https://license-renew.tokyo-madoguchi-yoyaku.com/police-pref-tokyo/index_000.html"
os.makedirs("debug", exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(locale="ja-JP", timezone_id="Asia/Tokyo")
    pg.goto(URL, wait_until="networkidle", timeout=60000)
    pg.screenshot(path="debug/tokyo_00.png", full_page=True)
    open("debug/tokyo_00.html", "w", encoding="utf-8").write(pg.content())
    links = pg.evaluate("() => [...document.querySelectorAll('a,button,input[type=button],input[type=submit]')].map(e => ({t:(e.innerText||e.value||'').trim().slice(0,60), h:e.href||e.getAttribute('onclick')||''}))")
    json.dump(links, open("debug/tokyo_links.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("title:", pg.title(), "url:", pg.url, "links:", len(links))
    b.close()
