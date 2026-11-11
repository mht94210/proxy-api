#!/usr/bin/env python3
"""每 2 小时跑一次：抓取中国境内 HTTP/HTTPS 代理原始池，写 proxies_raw_cn.*。
注意：公开链接（proxies_cn / proxies_best / proxies_good）只放服务器实测通的，
本脚本不碰它们——实测在山东服务器上跑，通的才由那边（或 Muse）写进公开文件。
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from fetcher_cn import fetch_all_cn
result = fetch_all_cn()
with open("proxies_raw_cn.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)
with open("proxies_raw_cn.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in result["proxies"]) + "\n")
print(f"OK raw CN HTTP {result['total']} proxies (1 per /24), updated {result['updated_at']} (unverified pool, NOT published)")
