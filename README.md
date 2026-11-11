# 中国免费代理 API（HTTP/HTTPS 专版）

只做中国境内 HTTP/HTTPS 代理，每 /24 网段只留一个，没有重复段。

## 稳定 API 链接（链接不变，数据更新）

- 最好版（115 个，高匿 + 低延迟）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_best.txt`
- 好代理版（全部高匿，558 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_good.txt`
- 完整版（923 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.txt`

JSON 版把 `.txt` 换成 `.json` 就行，带国家/城市/匿名度/延迟。

备用链接（jsDelivr 打不开时用）：
`https://ghfast.top/https://raw.githubusercontent.com/mht94210/proxy-api/main/proxies_cn.txt`

如果打开还是旧的版本，按 Ctrl+F5 强制刷新一次（浏览器会把旧版本存 7 天）。

## 服务器实测版（另外的链接，数量少但每个都测通过）
山东服务器实测过一轮：923 个里 85 个通，最好 19 个。想要实测过的用这几个：

- 实测完整版（85 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/verified_working.txt`
- 实测最好版（19 个）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/verified_best.txt`
- 实测好代理版（66 个，高匿）：
  `https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/verified_good.txt`

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
抓取每 2 小时跑一次（`fetch_daily.py`，只写原始池 `proxies_raw_cn.*`），公开链接的数据更新时再推。

## 重要提醒
免费代理存活很短（几小时就失效），仅供学习测试，**绝不能用于登录、支付、重要账号**。
