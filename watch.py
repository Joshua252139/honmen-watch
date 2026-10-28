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


JS_FIND = """
(marks) => {
  const out = [];
  for (const table of document.querySelectorAll('table')) {
    const rows = [...table.rows];
    if (!rows.length) continue;
    const header = [...rows[0].cells].map(c => c.innerText.trim());
    rows.forEach((row) => {
      [...row.cells].forEach((cell, ci) => {
        const t = cell.innerText.trim();
        const alt = [...cell.querySelectorAll('img')].map(i => i.alt || '').join(' ');
        const s = t + ' ' + alt;
        if (marks.some(m => s.includes(m))) {
          out.push({cell: s, colHead: header[ci] || '', rowHead: row.cells[0].innerText.trim()});
        }
      });
    });
  }
  return out;
}
"""


def snap(page, name):
    os.makedirs("debug", exist_ok=True)
    page.screenshot(path=f"debug/{name}.png", full_page=True)
    with open(f"debug/{name}.html", "w", encoding="utf-8") as f:
        f.write(page.content())


def go_to_calendar(page):
    page.goto(URL, wait_until="networkidle", timeout=60000)
    snap(page, "01_detail")
    for label in ["予約する", "日時を選択", "日時選択", "空き状況", "予約日時", "次へ"]:
        for loc in (page.get_by_role("button", name=re.compile(label)),
                    page.get_by_role("link", name=re.compile(label))):
            if loc.count() > 0:
                loc.first.click()
                page.wait_for_load_state("networkidle")
                snap(page, "02_calendar")
                return


def check(page):
    today = dt.datetime.now(JST).date()
    target = dt.date.fromisoformat(TARGET_DATE)
    go_to_calendar(page)
    found = set()
    for i in range(10):
        for hit in page.evaluate(JS_FIND, AVAILABLE_MARKS):
            d = parse_date(hit["colHead"], today) or parse_date(hit["rowHead"], today)
            if d and today < d < target:
                found.add(d)
        nxt = page.get_by_role("button", name=re.compile("次|翌|>")).or_(
              page.get_by_role("link", name=re.compile("次の|翌週|次週|>")))
        if nxt.count() == 0 or not nxt.first.is_enabled():
            break
        nxt.first.click()
        page.wait_for_load_state("networkidle")
        snap(page, f"03_page{i + 1}")
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
