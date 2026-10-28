# 埼玉 本免学科试验 空位监控

监控埼玉县警「教習所卒業・普通一種」学科试验的网上预约日历，一旦出现比你现有预约**更早**的空位，就推送到手机（ntfy）。

**只监控、不自动预约。** 收到推送后请自己去预约：先确认新日期能选，再取消旧预约，然后马上重新预约。埼玉县警规定一人只能有一个预约，重复预约会导致全部作废。

- 运行在 GitHub Actions 上，免费，不需要开着电脑
- 每 10 分钟检查一次，只在日本时间 6:00～24:00 运行
- 默认只看「1回目（初めて） 日本語」这一行

## 设置步骤（约 10 分钟）

1. **手机装 ntfy App**，点「+」订阅一个别人猜不到的名字，比如 `taro-honmen-5831`。
2. **注册 GitHub**，右上角「+」→「New repository」，名字随意，选 **Public**，创建。
3. 在新仓库页面点「uploading an existing file」，把本压缩包解压后的**全部文件**拖进去（包括 `.github` 文件夹；如果拖不进隐藏文件夹，见下方说明），点「Commit changes」。
4. 仓库「Settings → Secrets and variables → Actions」：
   - **Secrets** 标签 → New repository secret：Name `NTFY_TOPIC`，值填第 1 步的订阅名
   - **Variables** 标签 → New repository variable：Name `TARGET_DATE`，值填你现在约到的日期，格式 `2026-11-19`
5. 打开仓库的「Actions」标签，如果提示启用，点启用。之后会自动运行。

> 上传 `.github` 文件夹：Mac 的 Finder 默认不显示以点开头的文件夹，按 `Cmd + Shift + .` 就能显示。也可以在 GitHub 上点「Add file → Create new file」，文件名输入 `.github/workflows/watch.yml`，把里面的内容粘贴进去。

## 测试推送

在仓库根目录新建一个名为 `TEST_PUSH` 的空文件并提交，下一次运行会发一条「测试推送」到手机。确认收到后把这个文件删掉。

## 改了预约日期之后

去「Settings → Secrets and variables → Actions → Variables」把 `TARGET_DATE` 改成新日期即可。

## 查看运行情况

- 「Actions」标签里能看到每次运行的记录
- 每次运行的日志和页面截图会放在仓库的 `debug` 分支（`run.log` 和 `debug/` 文件夹）

## 自定义

- **第 2 次以后受验、或用外语受验**：改 `watch.py` 里的 `ROW_KEYWORDS`，比如 `["2回目", "日本語"]` 或 `["1回目", "外国語"]`。
- **检查频率**：改 `.github/workflows/watch.yml` 里的 `cron`。别改得太频繁，GitHub 定时任务本身也会偶尔延迟几分钟。

## 停止监控

「Actions」标签 → 左侧选 `honmen-watch` → 右上角「···」→「Disable workflow」。
