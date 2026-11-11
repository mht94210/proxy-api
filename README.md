# 中国免费代理 API（HTTP/HTTPS 专版）

只做中国境内 HTTP/HTTPS 代理，每 /24 网段只留一个，没有重复段。每 2 小时自动更新一次。

## 稳定 API 链接（链接不变，数据每 2 小时更新）

**主链接（国内直连，实时最新，推荐）：**
- 完整版：`http://36.133.123.236:8000/proxies_cn.txt`
- 最好版（高匿 + 低延迟）：`http://36.133.123.236:8000/proxies_best.txt`
- 好代理版（全部高匿）：`http://36.133.123.236:8000/proxies_good.txt`

JSON 版把 `.txt` 换成 `.json` 就行，带国家/城市/匿名度/延迟。

备用链接（GitHub 镜像，和主链接内容一样）：
- `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.txt`
- `https://ghfast.top/https://raw.githubusercontent.com/mht94210/proxy-api/main/proxies_cn.txt`

如果打开 jsDelivr 还是旧的版本，按 Ctrl+F5 强制刷新一次（浏览器会把旧版本存 7 天；jsDelivr 自身缓存约 12 小时，主链接不受影响）。

## 服务器实测版（另外的链接，数量少但每个都测通过）
山东服务器实测过一轮：923 个里 85 个通，最好 19 个。想要实测过的用这几个：

- 实测完整版（85 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/verified_working.txt`
- 实测最好版（19 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/verified_best.txt`
- 实测好代理版（66 个，高匿）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/verified_good.txt`

## 来源
站大爷、快代理、89ip（2000 条里用 APNIC 中国 IP 段筛出真中国 IP）、云代理、齐云、HProxy、Proxora、Geonode、ProxyScrape、ihuan。台湾 IP 已去掉。服务器自己每 2 小时抓一次、直接推上 GitHub，不经过实测。

## 本地 API（FastAPI）
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python fetcher_cn.py   # 抓一次，生成 proxies_cn.json / proxies_cn.txt
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```
- `GET /api/status` - 总数、更新时间
- `GET /api/proxies?protocol=http&limit=100` - 列表 JSON
- `GET /api/proxy/random?protocol=http` - 随机一个
- `GET /api/proxies.txt?protocol=http&limit=100` - 纯文本
- `GET /docs` - 交互文档

## 每 2 小时更新
山东服务器上的定时任务每 2 小时跑 `server_fetch_push.py --push`：抓取 → 直接推上 GitHub → 主链接（服务器 8000 端口）实时就是最新的。

## 重要提醒
免费代理存活很短（几小时就失效），仅供学习测试，**绝不能用于登录、支付、重要账号**。
