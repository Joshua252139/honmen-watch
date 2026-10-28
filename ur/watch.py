#!/usr/bin/env python3
"""
UR 团地空房监控：指定团地出现新的空房就推送到 ntfy。
直接调用 UR 官网页面自己用的空房查询接口（和浏览器打开团地页面时一样）。
"""
import os
import json
import urllib.parse
import urllib.request
import datetime as dt
from zoneinfo import ZoneInfo

# 名称: (支社, 团地编号, 识别号)  —— 来自 https://www.ur-net.go.jp/chintai/kanto/kanagawa/40_XXXX.html
DANCHI = {
    "コンフォール川崎富士見":   ("40", "412", "0"),
    "リーデンスフォート横浜":   ("40", "404", "0"),
    "オルトヨコハマビュータワー": ("40", "401", "0"),
    "ミラリオ鶴見小野":       ("40", "410", "0"),
    "ステラ月見ヶ丘":         ("40", "340", "0"),
}
API = "https://chintai.r6.ur-net.go.jp/chintai/api/bukken/detail/detail_bukken_room/"
DRY_RUN = os.path.exists("ur/DRY_RUN")  # 调试用：不推送、不保存状态
NTFY_TOPIC = "" if DRY_RUN else os.environ.get("NTFY_TOPIC", "")
NTFY_EMAIL = os.environ.get("NTFY_EMAIL", "")  # 同时发邮件（从 GitHub Secrets 读取）
STATE_FILE = "ur-state/seen.json"
JST = ZoneInfo("Asia/Tokyo")


def page_url(shisya, danchi, shikibetu):
    return f"https://www.ur-net.go.jp/chintai/kanto/kanagawa/{shisya}_{danchi}{shikibetu}.html"


def push(title, msg, click):
    print(f"[推送] {title}\n{msg}")
    if not NTFY_TOPIC:
        print("!! 没有读取到 NTFY_TOPIC 密钥，推送没有发出")
        return
    print(f"   推送到 topic: {NTFY_TOPIC[:4]}…{NTFY_TOPIC[-2:]}（长度 {len(NTFY_TOPIC)}）")
    headers = {"Title": title.encode("utf-8"), "Click": click, "Priority": "high", "Tags": "house"}
    if NTFY_EMAIL:
        headers["Email"] = NTFY_EMAIL
        msg = msg + "\n\n" + click
        print("   同时发送邮件")
    req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"), headers=headers)
    resp = urllib.request.urlopen(req, timeout=15)
    print("   ntfy 返回:", resp.status, resp.read().decode()[:200])


def fetch_rooms(shisya, danchi, shikibetu):
    rooms, page = [], 0
    while page < 20:
        form = {
            "rent_low": "", "rent_high": "", "floorspace_low": "", "floorspace_high": "",
            "shisya": shisya, "danchi": danchi, "shikibetu": shikibetu,
            "newBukkenRoom": "", "orderByField": "0", "orderBySort": "0",
            "pageIndex": str(page), "sp": "",
        }
        req = urllib.request.Request(
            API, data=urllib.parse.urlencode(form).encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://www.ur-net.go.jp",
                "Referer": page_url(shisya, danchi, shikibetu),
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            })
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        os.makedirs("ur-debug", exist_ok=True)
        with open(f"ur-debug/{danchi}_p{page}.json", "w", encoding="utf-8") as f:
            f.write(body)
        data = json.loads(body) if body.strip() not in ("", "null") else []
        if isinstance(data, dict):  # 以防返回的是包了一层的对象
            data = next((v for v in data.values() if isinstance(v, list)), [])
        if not data:
            break
        rooms.extend(data)
        total = int(data[0].get("allCount") or 0)
        if len(rooms) >= total:
            break
        page += 1
    return rooms


def g(room, *keys):
    for k in keys:
        v = room.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def room_id(room):
    return g(room, "id") or g(room, "name")


def describe(room):
    parts = [
        g(room, "name", "roomNmMain"),
        g(room, "type", "roomType"),
        g(room, "floorspace").replace("&#13217;", "㎡"),
        g(room, "rent", "rent_normal"),
        ("共益費" + g(room, "commonfee")) if g(room, "commonfee") else "",
    ]
    return " / ".join(p for p in parts if p)


def main():
    if os.path.exists("ur/TEST_PUSH"):
        push("UR 测试推送", "收到这条说明手机推送正常", "https://www.ur-net.go.jp/chintai/kanto/kanagawa/")
    os.makedirs("ur-state", exist_ok=True)
    try:
        seen = json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        seen = None  # 第一次运行
    first_run = seen is None
    seen = seen or {}
    now = dt.datetime.now(JST).strftime("%m/%d %H:%M")

    new_seen, summary = {}, []
    for name, (shisya, danchi, shikibetu) in DANCHI.items():
        try:
            rooms = fetch_rooms(shisya, danchi, shikibetu)
        except Exception as e:
            print(f"{name}: 查询失败 {e}")
            new_seen[name] = seen.get(name, [])  # 失败时保留旧状态，避免误报
            continue
        ids = [room_id(r) for r in rooms]
        new_seen[name] = ids
        old = set(seen.get(name, []))
        fresh = [r for r in rooms if room_id(r) not in old]
        print(f"{now} {name}: 空房 {len(rooms)} 间" + (f"，新增 {len(fresh)} 间" if fresh and not first_run else ""))
        for r in rooms:
            print("   ", describe(r))
        if rooms:
            summary.append(f"{name}: {len(rooms)}间")
        if fresh and not first_run:
            push(f"UR 有新空房：{name}",
                 "\n".join(describe(r) for r in fresh[:8]) + ("\n…" if len(fresh) > 8 else ""),
                 page_url(shisya, danchi, shikibetu))

    if first_run:
        push("UR 空房监控已开始",
             ("当前空房：\n" + "\n".join(summary)) if summary else "这5个团地目前都没有空房，有新空房会马上通知你",
             "https://www.ur-net.go.jp/chintai/kanto/kanagawa/")
    if not DRY_RUN:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(new_seen, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
