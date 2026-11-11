#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在山东服务器上实测代理是否真的能用。

只用标准库，不用装任何东西。跑法（服务器上）：
    python validate_server.py
    python validate_server.py --source https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.txt
    python validate_server.py --in proxies_cn.txt --out-dir C:\\proxycheck

逻辑：对每个代理 GET http://httpbin.org/ip，8 秒超时。
  - 通 = 返回 200 且带 origin；记真实延迟。
  - 匿名度：origin == 代理 IP -> 高匿；origin 里出现本机 IP -> 透明；其他 -> 普匿。
只把通的写进 verified_*.txt/json，不通的一个都不进。
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

TEST_URL = "http://httpbin.org/ip"
TIMEOUT = 8
THREADS = 30


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")


def get_server_ip():
    """本机直连出口 IP，用来判断代理是不是透明。"""
    try:
        data = json.loads(fetch_text(TEST_URL))
        return data.get("origin", "").split(",")[0].strip()
    except Exception:
        return ""


def check_one(args):
    ip, port, server_ip = args
    t0 = time.time()
    proxy_url = f"http://{ip}:{port}"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
    req = urllib.request.Request(TEST_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None
            data = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return None
    origin = (data.get("origin") or "").split(",")[0].strip()
    if not origin:
        return None
    ms = int((time.time() - t0) * 1000)
    if origin == ip:
        anon = "elite"
    elif server_ip and server_ip in origin:
        anon = "transparent"
    else:
        anon = "anonymous"
    return {"ip": ip, "port": int(port), "latency_ms": ms,
            "anonymity": anon, "origin": origin}


def main():
    global TIMEOUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default=None, help="本地 proxies_cn.txt")
    ap.add_argument("--source", default="https://cdn.jsdelivr.net/gh/mht94210/proxy-api@main/proxies_cn.txt")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--threads", type=int, default=THREADS)
    ap.add_argument("--timeout", type=int, default=TIMEOUT)
    args = ap.parse_args()
    TIMEOUT = args.timeout

    if args.infile:
        text = open(args.infile, encoding="utf-8").read()
    else:
        print("下载列表 ...", flush=True)
        text = fetch_text(args.source)
    pairs = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)", text)
    pairs = list(dict.fromkeys(pairs))
    print(f"待测 {len(pairs)} 个", flush=True)

    server_ip = get_server_ip()
    print(f"本机出口 IP: {server_ip or '(直连失败，只测通不通)'}", flush=True)

    t0 = time.time()
    ok = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as ex:
        for res in ex.map(check_one, [(ip, int(p), server_ip) for ip, p in pairs]):
            if res:
                ok.append(res)
    ok.sort(key=lambda x: (x["latency_ms"] is None, x["latency_ms"]))
    elite = [p for p in ok if p["anonymity"] == "elite"]
    best = [p for p in ok if p["latency_ms"] is not None and p["latency_ms"] < 2000
            and (p["anonymity"] == "elite" or p["latency_ms"] < 300)]
    # 最好版：每 /24 只留最快的一个
    seen, best_dedup = set(), []
    for p in best:
        net = ".".join(p["ip"].split(".")[:3])
        if net in seen:
            continue
        seen.add(net)
        best_dedup.append(p)
    # 全通版也按 /24 去重
    seen, ok_dedup = set(), []
    for p in ok:
        net = ".".join(p["ip"].split(".")[:3])
        if net in seen:
            continue
        seen.add(net)
        ok_dedup.append(p)

    os.makedirs(args.out_dir, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())
    for name, lst in (("verified_working", ok_dedup), ("verified_best", best_dedup)):
        with open(os.path.join(args.out_dir, name + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in lst) + ("\n" if lst else ""))
        with open(os.path.join(args.out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"updated_at": now, "total": len(lst), "country": "CN",
                       "protocols": ["http", "https"],
                       "definition": "服务器实测通的才进；不通的不进",
                       "proxies": lst}, f, ensure_ascii=False, indent=1)

    print(f"结果：待测 {len(pairs)}，通 {len(ok)}（去重后 {len(ok_dedup)}），"
          f"高匿 {len(elite)}，最好版 {len(best_dedup)}，用时 {time.time()-t0:.0f} 秒", flush=True)
    print("最快 10 个：", flush=True)
    for p in ok_dedup[:10]:
        print(f"  http://{p['ip']}:{p['port']} {p['latency_ms']}ms {p['anonymity']}", flush=True)


if __name__ == "__main__":
    main()
