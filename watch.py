#!/usr/bin/env python3
"""
埼玉 本免学科试验（指定教習所卒業・普通一種）空位监控 —— GitHub Actions 云端版
每次运行只检查一次，发现比 TARGET_DATE 更早的空位就推送到 ntfy。只监控，不下单。
"""
import os
import re
import json
import datetime as dt
import urllib.request
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

TARGET_DATE = os.environ.get("TARGET_DATE", "2026-11-19")   # 现有预约日期
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")                # 从 GitHub Secrets 读取
URL = "https://apply.e-tumo.jp/menkyo-saitama-u/reserve/offerList_detail?tempSeq=121593"
AVAILABLE_MARKS = ["○", "◯", "△"]
STATE_FILE = "state/notified.json"
JST = ZoneInfo("Asia/Tokyo")


def push(title, msg, priority="high"):
    print(f"[推送] {title}: {msg}")
    if not NTFY_TOPIC:
        print("未设置 NTFY_TOPIC，跳过推送")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"),
        headers={"Title": title.encode("utf-8"), "Click": URL, "Priority": priority})
    urllib.request.urlopen(req, timeout=15)


def parse_date(text, today):
    m = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})", text)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(\d{1,2})[月/](\d{1,2})", text)
    if m:
        mon, day = int(m[1]), int(m[2])
        year = today.year + (1 if mon < today.month else 0)
        try:
            return dt.date(year, mon, day)
        except ValueError:
            return None
    return None


ROW_KEYWORDS = ["1回目", "日本語"]           # 只看「1回目（初めて） 日本語」这一行
UNAVAILABLE = {"時間外", "空き無"}           # 页面上 －、× 对应的标签

# 日期在 id=height_headday 的表头行；每个预约枠一行 id=height_auto_<名称>；
# 每格里是 <svg aria-label="空き無/時間外/...">
JS_FIND = """
() => {
  const head = document.getElementById('height_headday');
  if (!head) return {error: 'no header row', rows: []};
  const dates = [...head.cells].map(c => c.innerText.replace(/\\s+/g, ' ').trim());
  const rows = [];
  for (const tr of document.querySelectorAll('tr[id^="height_auto_"]')) {
    const label = tr.id.replace('height_auto_', '');
    const cells = [...tr.querySelectorAll('td')].map(td => {
      const svg = td.querySelector('[aria-label]');
      return svg ? svg.getAttribute('aria-label') : td.innerText.trim();
    });
    rows.push({label, cells});
  }
  return {dates, rows};
}
"""


def norm(s):
    # 全角数字转半角，去掉空白
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789")).replace("\u3000", "").replace(" ", "")


def snap(page, name):
    os.makedirs("debug", exist_ok=True)
    page.screenshot(path=f"debug/{name}.png", full_page=True)
    with open(f"debug/{name}.html", "w", encoding="utf-8") as f:
        f.write(page.content())


def check(page):
    today = dt.datetime.now(JST).date()
    target = dt.date.fromisoformat(TARGET_DATE)
    page.goto(URL, wait_until="networkidle", timeout=60000)
    found, labels_seen = set(), set()
    for i in range(6):  # 40天大约3页，多翻几次保险
        snap(page, f"page{i + 1}")
        data = page.evaluate(JS_FIND)
        if data.get("error"):
            raise RuntimeError("页面结构变了: " + data["error"])
        dates = [parse_date(d, today) for d in data["dates"]]
        for row in data["rows"]:
            if not all(k in norm(row["label"]) for k in ROW_KEYWORDS):
                continue
            for d, status in zip(dates, row["cells"]):
                labels_seen.add(status)
                if d and today < d < target and status not in UNAVAILABLE:
                    found.add(d)
        print(f"第{i + 1}页: {data['dates'][0] if data['dates'] else '?'} ~ "
              f"{data['dates'][-1] if data['dates'] else '?'}")
        if dates and dates[-1] and dates[-1] >= target:
            break
        nxt = page.locator('input[type=button][value*="2週後"]')
        if nxt.count() == 0 or not nxt.first.is_enabled() or not nxt.first.is_visible():
            break
        nxt.first.click()
        page.wait_for_load_state("networkidle")
    print("出现过的格子状态:", sorted(labels_seen))
    return sorted(found)


def main():
    os.makedirs("state", exist_ok=True)
    try:
        notified = set(json.load(open(STATE_FILE)))
    except Exception:
        notified = set()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ja-JP", timezone_id="Asia/Tokyo")
        try:
            dates = check(page)
        finally:
            browser.close()

    now = dt.datetime.now(JST).strftime("%m/%d %H:%M")
    keys = [str(d) for d in dates]
    if keys:
        print(f"{now} 发现更早空位: {keys}")
        new = [k for k in keys if k not in notified]
        if new:
            push("本免学科 有更早空位！",
                 "、".join(dt.date.fromisoformat(k).strftime("%m/%d") for k in new)
                 + " 有空位，点开去预约（先确认能选，再取消旧预约）")
        notified = set(keys)
    else:
        print(f"{now} 暂无比 {TARGET_DATE} 更早的空位")
        notified = set()
    json.dump(sorted(notified), open(STATE_FILE, "w"))


if __name__ == "__main__":
    main()
