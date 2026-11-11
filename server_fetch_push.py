#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""山东服务器上的全自动流水线（不测版）：每 2 小时 抓取 -> 直接推上 GitHub。

只用标准库。跑法（服务器上，C:\\proxycheck\\）：
    python server_fetch_push.py --dry-run   # 只抓不推，写本地文件，测服务器能抓多少
    python server_fetch_push.py --push      # 抓完推上 GitHub（令牌读 github_token.txt）
令牌是细粒度 PAT，只给 mht94210/proxy-api 一个仓库的 Contents 读写权限。
推送用 GitHub contents API（api.github.com 服务器能通）；jsDelivr 清缓存
服务器调不通，会失败但不影响推送，忽略即可。
"""
import argparse
import base64
import bisect
import json
import os
import re
import ssl
import sys
import time
import urllib.request
import urllib.error

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
REPO = "mht94210/proxy-api"
BRANCH = "main"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github_token.txt")
PUSH_FILES = ["proxies_cn.txt", "proxies_cn.json", "proxies.json",
              "proxies_best.txt", "proxies_best.json",
              "proxies_good.txt", "proxies_good.json"]


def get(url, timeout=20):
    # 服务器出口会对部分 HTTPS 做中间人拦截（自签证书），先正常试，证书失败
    # 再用不校验重试——抓的是公开代理列表，不涉敏感数据。
    for ctx in (None, ssl._create_unverified_context()):
        try:
            req = urllib.request.Request(url, headers=H)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            continue
    return ""


# ---------------- 中国 IP 过滤（APNIC 段表，cn_ranges.json 须在同目录） ----------------
_CN_RANGES = None


def load_cn_ranges():
    global _CN_RANGES
    if _CN_RANGES is not None:
        return _CN_RANGES
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cn_ranges.json")
    raw = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    try:
        _CN_RANGES = json.loads(raw) if raw else []
    except Exception:
        _CN_RANGES = []
    print(f"  APNIC CN 段: {len(_CN_RANGES)}", flush=True)
    return _CN_RANGES


def is_cn(ip):
    ranges = load_cn_ranges()
    if not ranges:
        return False
    parts = ip.split(".")
    try:
        a = (int(parts[0]) << 24) | (int(parts[1]) << 16) | (int(parts[2]) << 8) | int(parts[3])
    except Exception:
        return False
    starts = [r[0] for r in ranges]
    i = bisect.bisect_right(starts, a) - 1
    return i >= 0 and ranges[i][0] <= a <= ranges[i][1]


def norm(ip, port, city="", anon="", lat=None, source=""):
    try:
        port = int(port)
    except Exception:
        return None
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip or "") or not (1 <= port <= 65535):
        return None
    return {"ip": ip, "port": port, "protocol": "http", "country": "中国",
            "country_code": "CN", "city": city, "anonymity": anon,
            "latency_ms": lat, "source": source, "verified_by_source": True}


# ---------------- 抓取 ----------------

def fetch_kuaidaili():
    # 服务器出口会限流快代理（HTTP 567）：只抓前 5 页、放慢到 1 秒/页，超了就停
    out = []
    for path in ("inha", "intr"):
        for page in range(1, 6):
            url = (f"https://www.kuaidaili.com/free/{path}/{page}/" if page > 1
                   else f"https://www.kuaidaili.com/free/{path}/")
            t = get(url)
            pairs = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})</td>\s*<td[^>]*>(\d+)</td>", t)
            if not pairs:
                print(f"  kuaidaili {path} p{page} 空（可能被限流），停抓该源", flush=True)
                break
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
            time.sleep(1.0)
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
        for page in range(1, 31):
            t = get(f"http://www.ip3366.net/free/?stype={stype}&page={page}")
            for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})</td>\s*<td[^>]*>(\d+)</td>", t):
                out.append({"ip": ip, "port": int(port), "city": "", "anonymity": "elite",
                            "latency_ms": None, "source": "ip3366"})
            time.sleep(0.2)
    print(f"  ip3366: {len(out)}", flush=True)
    return out


def fetch_qiyunip():
    out = []
    for p in range(1, 9):
        url = "https://www.qiyunip.com/freeProxy/" if p == 1 else f"https://www.qiyunip.com/freeProxy/{p}.html"
        t = get(url)
        rows = re.findall(r"<tr><th>(\d{1,3}(?:\.\d{1,3}){3})</th><th>(\d+)</th><th>(高匿|普匿|透明)?</th><th>(https?)?</th><th>([^<]{0,30})</th><th>([\d.]+)</th>", t)
        for ip, port, anon, _typ, loc, speed in rows:
            try:
                lat = float(speed) * 1000
            except Exception:
                lat = None
            o = norm(ip, port, city=loc.strip(), anon="elite" if anon == "高匿" else anon, lat=lat, source="qiyunip")
            if o:
                out.append(o)
        time.sleep(0.2)
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


def fetch_proxora():
    out = []
    try:
        data = json.loads(get("https://api.proxora.io/api/tools/free-proxies?country=CN") or "{}")
        for d in data.get("items", []):
            if str(d.get("protocol", "")).lower() != "http":
                continue
            o = norm(d.get("host"), d.get("port"), city=d.get("city", ""),
                     anon=d.get("anonymity", ""), lat=d.get("latency_ms"), source="proxora-cn")
            if o:
                out.append(o)
    except Exception:
        pass
    print(f"  proxora-cn: {len(out)}", flush=True)
    return out


def fetch_global():
    out = []
    t = get("https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=protocolipport&format=text&country=cn&timeout=5000")
    for m in re.finditer(r"(?:https?://)?(\d{1,3}(?:\.\d{1,3}){3}):(\d+)", t):
        o = norm(m.group(1), m.group(2), anon="elite", source="proxyscrape-cn")
        if o:
            out.append(o)
    try:
        data = json.loads(get("https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&country=CN") or "{}")
        for d in data.get("data", []):
            protos = [str(x).lower() for x in (d.get("protocols") or [])]
            if not any(p in ("http", "https") for p in protos):
                continue
            o = norm(d.get("ip"), d.get("port"), city=d.get("city", ""),
                     anon=d.get("anonymityLevel", ""), lat=d.get("latency"), source="geonode-cn")
            if o:
                out.append(o)
    except Exception:
        pass
    print(f"  global-cn: {len(out)}", flush=True)
    return out


def fetch_ihuan():
    out = []
    t = get("https://ip.ihuan.me/")
    for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})</a></td><td>(\d+)</td>", t):
        o = norm(ip, port, anon="", source="ihuan")
        if o:
            out.append(o)
    print(f"  ihuan: {len(out)}", flush=True)
    return out


def fetch_github_lists():
    # GitHub raw 在服务器上打不开（TLS 被重置），大概率 0 条，无害，留着以防万一
    out = []
    for url, src in (("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt", "proxifly-cn"),
                     ("https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", "speedx-cn"),
                     ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "monosans-cn")):
        t = get(url)
        for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)", t):
            if is_cn(ip):
                o = norm(ip, port, anon="", source=src)
                if o:
                    out.append(o)
    print(f"  github-lists: {len(out)}", flush=True)
    return out


# ---------------- 质量排序 / 去重（与 fetcher_cn.py 同定义） ----------------

def quality_score(p):
    anon = (p.get("anonymity") or "").lower()
    s = 30 if anon in ("elite", "高匿") else (10 if anon in ("anonymous", "普匿") else 0)
    lat = p.get("latency_ms")
    if lat is not None:
        try:
            s += max(0, 30 - float(lat) / 100)
        except Exception:
            pass
    return s


def dedupe_by_subnet(proxies):
    seen, out = set(), []
    for p in proxies:
        s = ".".join(p["ip"].split(".")[:3])
        if s in seen:
            continue
        seen.add(s)
        out.append(p)
    return out


def select_good(proxies):
    cand = [p for p in proxies if p.get("anonymity") == "elite"]
    cand.sort(key=lambda x: (-x.get("quality", 0), x["latency_ms"] is None, x["latency_ms"] or 99999))
    return dedupe_by_subnet(cand)


def select_best(proxies):
    cand = [p for p in proxies if p.get("latency_ms") is not None
            and ((p.get("anonymity") == "elite" and p["latency_ms"] < 2000) or p["latency_ms"] < 300)]
    cand.sort(key=lambda x: x["latency_ms"])
    return dedupe_by_subnet(cand)


# ---------------- 推送（GitHub contents API + jsDelivr 清缓存） ----------------

def read_token():
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        return tok
    if os.path.exists(TOKEN_FILE):
        return open(TOKEN_FILE, encoding="utf-8").read().strip()
    return ""


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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    t0 = time.time()

    print("抓取中 ...", flush=True)
    all_items = []
    for fn in (fetch_kuaidaili, fetch_zdaye, fetch_89ip, fetch_ip3366,
               fetch_qiyunip, fetch_hproxy, fetch_proxora, fetch_global,
               fetch_ihuan, fetch_github_lists):
        try:
            all_items.extend(fn())
        except Exception as e:
            print(f"  {fn.__name__} 失败: {e}", flush=True)
    seen = {}
    for p in all_items:
        key = (p["ip"], p["port"])
        if key not in seen:
            seen[key] = p
        else:
            old = seen[key]
            if p.get("latency_ms") and not old.get("latency_ms"):
                old["latency_ms"] = p["latency_ms"]
            if p.get("city") and not old.get("city"):
                old["city"] = p["city"]
            if p["source"] not in old["source"]:
                old["source"] += "," + p["source"]
    proxies = list(seen.values())
    for p in proxies:
        p["quality"] = round(quality_score(p), 1)
    proxies.sort(key=lambda x: (-x["quality"], x["latency_ms"] is None, x["latency_ms"] or 99999))
    proxies = dedupe_by_subnet(proxies)
    best = select_best(proxies)
    good = select_good(proxies)
    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())
    print(f"抓完：完整 {len(proxies)}，好代理 {len(good)}，最好版 {len(best)}，用时 {time.time()-t0:.0f} 秒", flush=True)

    result = {"updated_at": now, "total": len(proxies), "by_protocol": {"http": len(proxies)},
              "country": "CN", "protocols": ["http", "https"],
              "warning": "中国境内 HTTP/HTTPS 免费代理，每 /24 网段只留一个，仅供学习测试，勿用于登录/支付/重要账号。免费代理存活很短，每 2 小时更新一次。",
              "proxies": proxies}
    with open(os.path.join(args.out_dir, "proxies_cn.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out_dir, "proxies.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out_dir, "proxies_cn.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in proxies) + "\n")
    with open(os.path.join(args.out_dir, "proxies_good.json"), "w", encoding="utf-8") as f:
        json.dump({"updated_at": now, "total": len(good), "country": "CN",
                   "protocols": ["http", "https"],
                   "definition": "全部高匿；每 /24 只留一个", "proxies": good}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out_dir, "proxies_good.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in good) + ("\n" if good else ""))
    with open(os.path.join(args.out_dir, "proxies_best.json"), "w", encoding="utf-8") as f:
        json.dump({"updated_at": now, "total": len(best), "country": "CN",
                   "protocols": ["http", "https"],
                   "definition": "高匿 + 延迟<2000ms，或延迟<300ms；每 /24 只留一个", "proxies": best}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out_dir, "proxies_best.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in best) + ("\n" if best else ""))

    if args.dry_run or not args.push:
        print("只写本地文件，不推送。", flush=True)
        return
    token = read_token()
    if not token:
        print("没有令牌（github_token.txt / GITHUB_TOKEN），不推送。", flush=True)
        return
    msg = f"auto: 2h refresh cn={len(proxies)} best={len(best)} good={len(good)} ({now})"
    for name in PUSH_FILES:
        p = os.path.join(args.out_dir, name)
        sha = github_push(token, name, open(p, "rb").read(), msg)
        print(f"  已推 {name} commit {sha[:7]}", flush=True)
    for name in ("proxies_cn.txt", "proxies_best.txt", "proxies_good.txt"):
        purge_jsdelivr(name)
    print("推送完成（jsDelivr 清缓存服务器上调不通，忽略，缓存自己会过期）。", flush=True)


if __name__ == "__main__":
    main()
