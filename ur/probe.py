import os, json, re
from playwright.sync_api import sync_playwright
os.makedirs("ur-debug", exist_ok=True)
NAMES = ["コンフォール川崎富士見", "リーデンスフォート横浜", "オルトヨコハマビュータワー", "ミラリオ鶴見小野", "ステラ月見ヶ丘"]
KEYS = ["川崎", "鶴見", "神奈川区", "横浜"]
out = {"pages": {}, "danchi": {}, "api": []}
def links(pg):
    return pg.evaluate("() => [...document.querySelectorAll('a')].map(a => [a.innerText.trim().replace(/\\s+/g,' '), a.href])")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(locale="ja-JP")
    pg.on("request", lambda r: out["api"].append([r.method, r.url, r.post_data]) if "api" in r.url else None)
    top = "https://www.ur-net.go.jp/chintai/kanto/kanagawa/"
    pg.goto(top, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(4000)
    pg.screenshot(path="ur-debug/top.png", full_page=True)
    L = links(pg); out["pages"][top] = L
    sub = [h for t, h in L if any(k in t for k in KEYS) and "ur-net.go.jp/chintai" in h][:12]
    for h in sub:
        try:
            pg.goto(h, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(4000)
            out["pages"][h] = links(pg)
        except Exception as e:
            out["pages"][h] = str(e)
    for page_links in out["pages"].values():
        if isinstance(page_links, str): continue
        for t, h in page_links:
            if re.search(r"/40_\d+\.html", h):
                for n in NAMES:
                    if n in t.replace(" ", ""):
                        out["danchi"][n] = h
    # open one danchi page to learn the room API
    for n, h in out["danchi"].items():
        pg.goto(h, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(4000)
        pg.screenshot(path=f"ur-debug/{n}.png", full_page=True)
        open(f"ur-debug/{n}.html", "w", encoding="utf-8").write(pg.content())
        break
    b.close()
json.dump(out, open("ur-debug/probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("found:", json.dumps(out["danchi"], ensure_ascii=False))
print("pages:", list(out["pages"].keys()))
print("api:", out["api"][:10])
