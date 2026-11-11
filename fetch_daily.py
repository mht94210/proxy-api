#!/usr/bin/env python3
"""每 2 小时跑一次：中国境内 HTTP/HTTPS 代理抓取 -> 更新 proxies.json / proxies_cn.json / proxies_cn.txt / proxies_best.*"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from fetcher_cn import fetch_all_cn
result = fetch_all_cn()
for name in ("proxies.json", "proxies_cn.json"):
    with open(name, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
with open("proxies_cn.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in result["proxies"]) + "\n")
# 质量优先版：高匿 + 延迟<2000ms，或延迟<300ms，按延迟排序
best, seen = [], set()
for p in result["proxies"]:
    lat = p.get("latency_ms")
    if lat is None:
        continue
    if (p.get("anonymity") == "elite" and lat < 2000) or lat < 300:
        key = (p["ip"], p["port"])
        if key not in seen:
            seen.add(key); best.append(p)
best.sort(key=lambda x: x["latency_ms"])
with open("proxies_best.json", "w", encoding="utf-8") as f:
    json.dump({"updated_at": result["updated_at"], "total": len(best), "country": "CN",
               "protocols": ["http", "https"],
               "definition": "高匿 + 延迟<2000ms，或延迟<300ms；按延迟从低到高排序",
               "proxies": best}, f, ensure_ascii=False, indent=1)
with open("proxies_best.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in best) + ("\n" if best else ""))
print(f"OK CN HTTP {result['total']} proxies, best {len(best)}, updated {result['updated_at']}")
