#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""山东服务器上的全自动流水线：每 2 小时 抓取 -> 实测 -> 只把通的推上 GitHub。

只用标准库。跑法（服务器上，C:\\proxycheck\\）：
    python server_pipeline.py              # 抓 + 测，写 verified_*.txt/json 到 out-dir
    python server_pipeline.py --push       # 再推上 GitHub（需 GITHUB_TOKEN 环境变量）
    python server_pipeline.py --out-dir C:\\proxycheck

推送用 GitHub contents API（不用装 git），推完自动清 jsDelivr 缓存，
这样 @main 链接马上就是新内容。GITHUB_TOKEN 用细粒度 PAT，只给
mht94210/proxy-api 一个仓库的 Contents 读写权限。
没有 TOKEN 时只做抓+测，推送由 Muse 那边拉结果再推。
"""
import argparse
import base64
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
REPO = "mht94210/proxy-api"
BRANCH = "main"
OUT_FILES = ["verified_working.txt", "verified_working.json",
             "verified_best.txt", "verified_best.json"]


def get(url, timeout=20):
    # 服务器出口会对部分 HTTPS 做中间人拦截（自签证书），先正常试，证书失败
    # 再用不校验重试——抓的是公开代理列表，不涉敏感数据。
    import ssl
    for ctx in (None, ssl._create_unverified_context()):
        try:
            req = urllib.request.Request(url, headers=H)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            continue
    return ""


# ---------------- 中国 IP 过滤（APNIC 段表，存仓库里 cn_ranges.json） ----------------
import bisect

_CN_RANGES = None


def load_cn_ranges():
    global _CN_RANGES
    if _CN_RANGES is not None:
        return _CN_RANGES
    raw = ""
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cn_ranges.json")):
        raw = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cn_ranges.json"), encoding="utf-8").read()
    if not raw:
        raw = get(f"https://cdn.jsdelivr.net/gh/{REPO}@{BRANCH}/cn_ranges.json")
    try:
        _CN_RANGES = json.loads(raw) if raw else []
    except Exception:
        _CN_RANGES = []
    print(f"  APNIC CN 段: {len(_CN_RANGES)}", flush=True)
    return _CN_RANGES


def is_cn(ip):
    ranges = load_cn_ranges()
    if not ranges:
        return False  # 段表拿不到时宁可不要这批，也别把外国 IP 混进来
    parts = ip.split(".")
    try:
        a = (int(parts[0]) << 24) | (int(parts[1]) << 16) | (int(parts[2]) << 8) | int(parts[3])
    except Exception:
        return False
    starts = [r[0] for r in ranges]
    i = bisect.bisect_right(starts, a) - 1
    return i >= 0 and ranges[i][0] <= a <= ranges[i][1]


# ---------------- 抓取（与 fetcher_cn.py 同源，GitHub 列表走 jsDelivr 镜像） ----------------

def fetch_kuaidaili():
    out = []
    for path in ("inha", "intr"):
        for page in range(1, 16):
            url = (f"https://www.kuaidaili.com/free/{path}/{page}/" if page > 1
                   else f"https://www.kuaidaili.com/free/{path}/")
            t = get(url)
            pairs = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})</td>\s*<td[^>]*>(\d+)</td>", t)
            locs = re.findall(r"</td>\s*<td[^>]*>\s*(中国[^<]{0,40}|台湾省[^<]{0,20})\s*</td>\s*<td[^>]*>\s*([\d.]+)\s*</td>", t)
            for i, (ip, port) in enumerate(pairs):
                loc, lat = "", None
                if i < len(locs):
                    loc = locs[i][0].strip()
                    try:
                        lat = float(locs[i][1]) * 1000
                    except Exception:
                        lat = None
                if "台湾" in loc:
                    continue
                out.append({"ip": ip, "port": int(port), "city": loc,
                            "anonymity": "elite", "latency_ms": lat, "source": "kuaidaili"})
            time.sleep(0.2)
    print(f"  kuaidaili: {len(out)}", flush=True)
    return out


def fetch_zdaye():
    out = []
    for p in range(1, 26):
        url = "https://www.zdaye.com/free/" if p == 1 else f"https://www.zdaye.com/free/{p}/"
        t = get(url)
        for m in re.finditer(r'proxy_ip">(\d{1,3}(?:\.\d{1,3}){3})</p><p class="proxy_port">Port[：:](\d+)', t):
            seg = t[m.start():m.start() + 500]
            proto = "socks5" if "socks5" in seg.lower() else ("socks4" if "socks4" in seg.lower() else "http")
            if proto != "http":
                continue
            anon = "elite" if "高匿" in seg else ""
            city = ""
            cm = re.search(r'title="([^"]{0,30})"', seg)
            if cm:
                city = cm.group(1).strip()
            out.append({"ip": m.group(1), "port": int(m.group(2)), "city": city,
                        "anonymity": anon, "latency_ms": None, "source": "zdaye"})
        time.sleep(0.2)
    print(f"  zdaye: {len(out)}", flush=True)
    return out


def fetch_89ip():
    out = []
    t = get("http://www.89ip.cn/tqdl.html?api=1&num=2000&port=&address=&isp=")
    for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)", t):
        if not is_cn(ip):
            continue
        out.append({"ip": ip, "port": int(port), "city": "", "anonymity": "",
                    "latency_ms": None, "source": "89ip"})
    print(f"  89ip: {len(out)}", flush=True)
    return out


def fetch_ip3366():
    out = []
    for stype in (1, 2):
        for page in range(1, 11):
            t = get(f"http://www.ip3366.net/free/?stype={stype}&page={page}")
            for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})</td>\s*<td[^>]*>(\d+)</td>", t):
                out.append({"ip": ip, "port": int(port), "city": "", "anonymity": "elite",
                            "latency_ms": None, "source": "ip3366"})
            time.sleep(0.2)
    print(f"  ip3366: {len(out)}", flush=True)
    return out


def fetch_qiyunip():
    out = []
    t = get("https://www.qiyunip.com/freeProxy/")
    rows = re.findall(r"<tr><th>(\d{1,3}(?:\.\d{1,3}){3})</th><th>(\d+)</th><th>(高匿|普匿|透明)?</th><th>(https?)?</th><th>([^<]{0,30})</th><th>([\d.]+)</th>", t)
    for ip, port, anon, _typ, loc, speed in rows:
        try:
            lat = float(speed) * 1000
        except Exception:
            lat = None
        out.append({"ip": ip, "port": int(port), "city": loc.strip(),
                    "anonymity": "elite" if anon == "高匿" else (anon or ""),
                    "latency_ms": lat, "source": "qiyunip"})
    print(f"  qiyunip: {len(out)}", flush=True)
    return out


def fetch_hproxy():
    out = []
    try:
        data = json.loads(get("https://hproxy.com/api/proxy-list?format=json&country=CN&protocol=http") or "[]")
        for x in data:
            if x.get("country_code") != "CN":
                continue
            protos = x.get("protocols") or []
            if "http" not in [str(p).lower() for p in protos]:
                continue
            try:
                lat = float(x.get("latency_ms")) if x.get("latency_ms") is not None else None
            except Exception:
                lat = None
            out.append({"ip": x["ip"], "port": int(x["port"]), "city": x.get("city", "") or "",
                        "anonymity": (x.get("anonymity") or "").lower(),
                        "latency_ms": lat, "source": "hproxy"})
    except Exception:
        pass
    print(f"  hproxy: {len(out)}", flush=True)
    return out


def fetch_github_lists():
    """GitHub 上的免费列表，走 jsDelivr 镜像（国内能打开）。"""
    out = []
    for url in ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
                "https://cdn.jsdelivr.net/gh/TheSpeedX/PROXY-List@master/http.txt",
                "https://cdn.jsdelivr.net/gh/monosans/proxy-list@main/proxies/http.txt"):
        t = get(url)
        for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)", t):
            if not is_cn(ip):
                continue
            out.append({"ip": ip, "port": int(port), "city": "", "anonymity": "",
                        "latency_ms": None, "source": "github-list"})
    print(f"  github-lists: {len(out)}", flush=True)
    return out


# ---------------- 校验（与 validate_server.py 同逻辑，内联一份） ----------------

def check_one(args):
    ip, port, server_ip = args
    t0 = time.time()
    proxy_url = f"http://{ip}:{port}"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
    req = urllib.request.Request("http://httpbin.org/ip", headers=H)
    try:
        with opener.open(req, timeout=8) as r:
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
    return {"ip": ip, "port": int(port), "latency_ms": ms, "anonymity": anon}


def dedupe_by_subnet(items):
    seen, out = set(), []
    for p in items:
        net = ".".join(p["ip"].split(".")[:3])
        if net in seen:
            continue
        seen.add(net)
        out.append(p)
    return out


# ---------------- 推送（GitHub contents API + jsDelivr 清缓存） ----------------

def github_push(token, path, content_bytes, message):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "User-Agent": "proxy-api-pipeline"}
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            sha = json.loads(r.read().decode())["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    body = {"message": message, "content": base64.b64encode(content_bytes).decode(),
            "branch": BRANCH}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={**headers, "Content-Type": "application/json"},
                                 method="PUT")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())["commit"]["sha"]


def purge_jsdelivr(path):
    try:
        get(f"https://purge.jsdelivr.net/gh/{REPO}@{BRANCH}/{path}", timeout=20)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    t0 = time.time()

    print("抓取中 ...", flush=True)
    all_items = []
    for fn in (fetch_kuaidaili, fetch_zdaye, fetch_89ip, fetch_ip3366,
               fetch_qiyunip, fetch_hproxy, fetch_github_lists):
        try:
            all_items.extend(fn())
        except Exception as e:
            print(f"  {fn.__name__} 失败: {e}", flush=True)
    uniq = {}
    for p in all_items:
        uniq[(p["ip"], p["port"])] = p
    items = list(uniq.values())
    print(f"抓到 {len(items)} 个（去重后）", flush=True)

    try:
        server_ip = json.loads(get("http://httpbin.org/ip") or "{}").get("origin", "").split(",")[0].strip()
    except Exception:
        server_ip = ""
    print(f"本机出口 IP: {server_ip or '(直连失败)'}", flush=True)

    print("实测中 ...", flush=True)
    ok = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        for res in ex.map(check_one, [(p["ip"], p["port"], server_ip) for p in items]):
            if res:
                ok.append(res)
    ok.sort(key=lambda x: x["latency_ms"])
    ok_dedup = dedupe_by_subnet(ok)
    best = [p for p in ok if p["latency_ms"] is not None and p["latency_ms"] < 2000
            and (p["anonymity"] == "elite" or p["latency_ms"] < 300)]
    best_dedup = dedupe_by_subnet(best)
    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())
    for name, lst in (("verified_working", ok_dedup), ("verified_best", best_dedup)):
        with open(os.path.join(args.out_dir, name + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in lst) + ("\n" if lst else ""))
        with open(os.path.join(args.out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"updated_at": now, "total": len(lst), "country": "CN",
                       "protocols": ["http", "https"],
                       "definition": "服务器实测通的才进；不通的不进",
                       "proxies": lst}, f, ensure_ascii=False, indent=1)
    print(f"结果：待测 {len(items)}，通 {len(ok)}（去重后 {len(ok_dedup)}），"
          f"最好版 {len(best_dedup)}，用时 {time.time()-t0:.0f} 秒", flush=True)
    for p in ok_dedup[:10]:
        print(f"  http://{p['ip']}:{p['port']} {p['latency_ms']}ms {p['anonymity']}", flush=True)

    if args.push:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("没有 GITHUB_TOKEN，只写本地文件，不推送。", flush=True)
            return
        msg = f"auto: verified {len(ok_dedup)} working, best {len(best_dedup)} ({now})"
        for name in OUT_FILES:
            p = os.path.join(args.out_dir, name)
            sha = github_push(token, name, open(p, "rb").read(), msg)
            print(f"  已推 {name} commit {sha[:7]}", flush=True)
        for name in OUT_FILES:
            purge_jsdelivr(name)
        print("已清 jsDelivr 缓存，链接即时更新。", flush=True)


if __name__ == "__main__":
    main()
