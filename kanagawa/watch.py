#!/usr/bin/env python3
"""
神奈川 本免学科试验 空位监控 —— GitHub Actions 云端版（只监控，不下单）
数据来源：神奈川県電子申請システム 里「運転免許学科試験」的各个手続き（每个手続き = 一个受验日+时间段）。
每次运行：搜索 -> 翻页收集全部手続き -> 过滤出名称含 NAME_KEYWORDS（默认 中国語/外国語）的 ->
  1) 在日志里写出「目前能约到的最晚日期」
  2) 有新出现的、早于 TARGET_DATE 的手続き就推送到 ntfy
DISCOVER=1 时不过滤，把所有搜到的手続き名都打印出来，用来确认中文考试在页面上怎么标注。
"""
import os
import re
import json
import datetime as dt
import urllib.request
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

START_URL = "https://dshinsei.e-kanagawa.lg.jp/140007-u/offer/offerList_initDisplay.action"
KEYWORD = os.environ.get("SEARCH_KEYWORD", "運転免許学科試験")
NAME_KEYWORDS = [k for k in os.environ.get("NAME_KEYWORDS", "中国語,外国語").split(",") if k]  # 任意一个命中即可
TARGET_DATE = os.environ.get("TARGET_DATE", "2027-12-31")   # 只提醒这天之前的
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
DISCOVER = os.environ.get("DISCOVER", "") == "1"
MAX_PAGES = 30
STATE_FILE = "state/kanagawa.json"
JST = ZoneInfo("Asia/Tokyo")


def push(title, msg, priority="high"):
    print(f"[推送] {title}: {msg}")
    if not NTFY_TOPIC:
        print("未设置 NTFY_TOPIC，跳过推送")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"),
        headers={"Title": title.encode("utf-8"), "Click": START_URL, "Priority": priority})
    urllib.request.urlopen(req, timeout=15)


def norm(s):
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789")).replace("\u3000", " ")


def parse_date(text, today):
    text = norm(text)
    m = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})", text)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(\d{1,2})月\s*(\d{1,2})日", text) or re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", text)
    if m:
        mon, day = int(m[1]), int(m[2])
        year = today.year + (1 if mon < today.month - 1 else 0)
        try:
            return dt.date(year, mon, day)
        except ValueError:
            return None
    return None


def snap(page, name):
    os.makedirs("debug", exist_ok=True)
    page.screenshot(path=f"debug/{name}.png", full_page=True)
    with open(f"debug/{name}.html", "w", encoding="utf-8") as f:
        f.write(page.content())


JS_ROWS = """
() => [...document.querySelectorAll('tr')]
  .filter(tr => tr.querySelector('a, input[type=button], input[type=submit]'))
  .map(tr => tr.innerText.replace(/[ \\t]+/g, ' ').replace(/\\n+/g, ' | ').trim())
  .filter(t => t.length > 0)
"""


def collect(page):
    page.goto(START_URL, wait_until="networkidle", timeout=60000)
    snap(page, "p0_start")
    # 首页没有搜索框：先点「オンライン申請手続き」进入手续检索页
    page.locator('.common-button:has-text("オンライン申請手続き")').first.click()
    page.wait_for_load_state("networkidle")
    snap(page, "p0b_search")
    box = page.locator('input[type=text]:visible').first
    box.fill(KEYWORD)
    btn = page.locator('input[value*="検索"], button:has-text("検索"), a:has-text("検索")')
    btn.first.click()
    page.wait_for_load_state("networkidle")
    rows, seen = [], set()
    for i in range(MAX_PAGES):
        snap(page, f"p{i + 1}")
        got = page.evaluate(JS_ROWS)
        new = [r for r in got if r not in seen]
        for r in new:
            seen.add(r)
            rows.append(r)
        print(f"第{i + 1}页: {len(got)} 行（新增 {len(new)}）")
        nxt = page.locator('a:has-text("次へ"), a:has-text("次のページ"), input[value*="次"], a:has-text(">")')
        if nxt.count() == 0 or not nxt.first.is_visible() or not new:
            break
        nxt.first.click()
        page.wait_for_load_state("networkidle")
    return rows


def main():
    if os.path.exists("TEST_PUSH"):
        push("测试推送", "神奈川本免监控已连接成功", priority="default")
    os.makedirs("state", exist_ok=True)
    try:
        notified = set(json.load(open(STATE_FILE)))
    except Exception:
        notified = set()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ja-JP", timezone_id="Asia/Tokyo")
        try:
            rows = collect(page)
        finally:
            browser.close()

    today = dt.datetime.now(JST).date()
    target = dt.date.fromisoformat(TARGET_DATE)
    print(f"共收集 {len(rows)} 条手続き")
    if DISCOVER or not rows:
        for r in rows:
            print("  ", r)
    hits = [(parse_date(r, today), r) for r in rows if any(k in r for k in NAME_KEYWORDS)]
    print(f"名称含 {NAME_KEYWORDS} 的: {len(hits)} 条")
    dated = sorted([(d, r) for d, r in hits if d], key=lambda x: x[0])
    for d, r in dated:
        print("  ", d, r)
    if dated:
        print(f"==> 目前能约到的最晚日期: {dated[-1][0]}；最早: {dated[0][0]}")
    now = dt.datetime.now(JST).strftime("%m/%d %H:%M")
    fresh = [(d, r) for d, r in dated if today < d < target]
    new = [(d, r) for d, r in fresh if r not in notified]
    if new:
        push("神奈川本免学科（中文/外国语）有新场次！",
             "、".join(d.strftime("%m/%d") for d, _ in new) + " 点开去预约")
    else:
        print(f"{now} 没有新场次")
    json.dump(sorted({r for _, r in fresh}), open(STATE_FILE, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
