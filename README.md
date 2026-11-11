# 中国免费代理 API（HTTP/HTTPS 专版）

只做中国境内 HTTP/HTTPS 代理，目标 1000 个，按质量排序（高匿优先、延迟低优先）。

## 稳定 API 链接（链接不变，数据更新）
质量优先，推荐先用下面这个“最好”版，只有 68 个左右，都是高匿 + 低延迟：

- 最好版纯文本：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_best.txt`
- 最好版 JSON：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_best.json`

好代理版（全部高匿，数量大）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_good.txt`

完整版（每 /24 网段只留最好一个，没有重复段）：
推到 GitHub `mht94210/proxy-api` 后，用 jsDelivr 访问，国内一般能打开：

- 纯文本，每行 `http://ip:port`：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.txt`
- JSON，带国家/城市/匿名度/延迟/质量分：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.json`

## 本次实测（2026-11-12 00:19 CST）
- 中国 HTTP 共 **1050 个**，高匿 305 个
- 来源：89ip（2000 条里用 APNIC 中国 IP 段筛出 699 个真中国 IP）、站大爷 146、快代理 120、Geonode-CN + ProxyScrape-CN 47、云代理 30、Proxora-CN 20、齐云 15
- 注意：89ip 直出接口里约 64% 是国外 IP，必须用 APNIC 过滤，不能直接当中国 IP 用。

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
```bash
# cron 每 2 小时跑一次
0 */2 * * * cd /path/to/proxy-api && .venv/bin/python fetch_daily.py >> fetch.log 2>&1
```
推到 GitHub 后 jsDelivr 缓存约数小时到 12 小时，可用 `https://purge.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.txt` 清缓存。

## 重要提醒
免费代理存活很短（几小时就失效），仅供学习测试，**绝不能用于登录、支付、重要账号**。
