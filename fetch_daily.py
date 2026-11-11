#!/usr/bin/env python3
"""每 2 小时跑一次：中国境内 HTTP/HTTPS 代理抓取 -> 直接更新公开链接文件
proxies_cn / proxies_best / proxies_good（每 /24 只留一个，目标维持 1000 个左右）。
不做实测，按上游质量（高匿优先、延迟低优先）排序。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from fetcher_cn import fetch_all_cn, select_best, select_good
result = fetch_all_cn()
for name in ("proxies.json", "proxies_cn.json"):
    with open(name, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
with open("proxies_cn.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in result["proxies"]) + "\n")
best = select_best(result["proxies"])
good = select_good(result["proxies"])
with open("proxies_good.json", "w", encoding="utf-8") as f:
    json.dump({"updated_at": result["updated_at"], "total": len(good), "country": "CN",
               "protocols": ["http", "https"],
               "definition": "全部高匿；每 /24 只留一个",
               "proxies": good}, f, ensure_ascii=False, indent=1)
with open("proxies_good.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in good) + ("\n" if good else ""))
with open("proxies_best.json", "w", encoding="utf-8") as f:
    json.dump({"updated_at": result["updated_at"], "total": len(best), "country": "CN",
               "protocols": ["http", "https"],
               "definition": "高匿 + 延迟<2000ms，或延迟<300ms；每 /24 只留一个",
               "proxies": best}, f, ensure_ascii=False, indent=1)
with open("proxies_best.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in best) + ("\n" if best else ""))
print(f"OK CN HTTP {result['total']} proxies (1 per /24), good {len(good)}, best {len(best)}, updated {result['updated_at']}")
