# 中国免费代理 API（HTTP/HTTPS 专版）

只做中国境内 HTTP/HTTPS 代理。**链接里的每一个 IP 都是山东服务器实测通的，不通的一个都不放进来。**

## 稳定 API 链接（链接不变，数据更新）

- 最好版（实测通 + 延迟低，19 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_best.txt`
- 好代理版（实测通 + 高匿，66 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_good.txt`
- 完整版（实测通的全部，85 个，每 /24 网段只留一个，没有重复段）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.txt`

JSON 版把 `.txt` 换成 `.json` 就行，带国家/延迟/匿名度/实测时间。

备用链接（jsDelivr 打不开时用）：
`https://ghfast.top/https://raw.githubusercontent.com/mht94210/proxy-api/main/proxies_cn.txt`

如果打开还是旧的版本，按 Ctrl+F5 强制刷新一次（浏览器会把旧版本存 7 天）。

## 服务器实测结果（2026-11-12 01:28 CST，山东服务器）
- 抓了 923 个中国 HTTP 代理，实测 **85 个通（9.2%），高匿 66 个，最好版 19 个**，最快 266ms
- 之前按上游数据排的“最好版 115 个”大部分其实已经死了——免费代理死得很快，只看上游数据不靠谱
- 每 2 小时重新抓、重新测，只把通的放进链接

## 来源
站大爷、快代理（15 页）、89ip（2000 条里用 APNIC 中国 IP 段筛出真中国 IP）、云代理（10 页）、齐云、HProxy、Proxifly、SpeedX、monosans。台湾 IP 已去掉。

## 本地 API（FastAPI）
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python fetcher_cn.py   # 抓一次，生成 proxies_raw_cn.json / proxies_raw_cn.txt（未实测原始池）
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```
- `GET /api/status` - 总数、更新时间
- `GET /api/proxies?protocol=http&limit=100` - 列表 JSON
- `GET /api/proxy/random?protocol=http` - 随机一个
- `GET /api/proxies.txt?protocol=http&limit=100` - 纯文本
- `GET /docs` - 交互文档

## 每 2 小时更新
抓取每 2 小时跑一次（`fetch_daily.py`，只写原始池），实测在山东服务器上跑（`validate_server.py` / `server_pipeline.py`），通的才推上 GitHub，推完自动清 jsDelivr 缓存，链接马上更新。

## 重要提醒
免费代理存活很短（几小时就失效），仅供学习测试，**绝不能用于登录、支付、重要账号**。
