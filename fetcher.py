"""每天全网搜索免费代理IP：聚合多个公开免费源，去重，存 proxies.json
来源（全部免费、无需 key）：
 1. ProxyScrape v4 API + GitHub 镜像 (jsDelivr) - HTTP/HTTPS/SOCKS4/SOCKS5，带国家/延迟
 2. Proxifly GitHub - 每 5 分钟更新，TXT 按协议分片
 3. monosans/proxy-list GitHub - 每小时更新，TXT
 4. Proxora 公开 API - 已验证池，带国家/延迟/可用率
 5. Geonode 公开 API - 带国家/延迟/可用率
注意：免费代理存活很短，70-85% 在 2 小时内失效，仅 1% 左右能通过完整验证。
所以本服务只做“候选池 + 上游已验证标记”，不承诺每个都通，绝不能走登录/支付。
"""
import json, re, time, random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 proxy-api-fetcher/1.0"}
TIMEOUT = 15

def _get_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and r.text.strip():
            return r.text
    except Exception as e:
        print(f"  fail {url}: {e}")
    return ""

def _get_json(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  fail {url}: {e}")
    return None

def parse_txt(text, protocol, source):
    out = []
    for line in text.splitlines():
        line = line.strip()
        # http://1.2.3.4:8080 或 1.2.3.4:8080
        m = re.search(r"(?:(https?|socks[45])://)?(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})", line)
        if not m:
            continue
        proto = (m.group(1) or protocol).lower()
        if proto in ("https",):
            proto = "http"
        out.append({"ip": m.group(2), "port": int(m.group(3)), "protocol": proto,
                    "country": "", "country_code": "", "anonymity": "",
                    "latency_ms": None, "source": source, "verified_by_source": True})
    return out

def fetch_proxyscrape():
    """ProxyScrape JSON 镜像，带完整元数据"""
    data = _get_json("https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/all/data.json")
    out = []
    if isinstance(data, list):
        for d in data:
            out.append({"ip": d.get("ip"), "port": d.get("port"),
                        "protocol": str(d.get("protocol", "")).lower(),
                        "country": d.get("country", ""), "country_code": d.get("country_code", ""),
                        "anonymity": d.get("anonymity", ""), "latency_ms": d.get("latency_ms"),
                        "source": "proxyscrape", "verified_by_source": True})
    # 补 API 文本源（镜像若滞后）
    for proto in ("http", "socks4", "socks5"):
        txt = _get_text(f"https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol={proto}&proxy_format=protocolipport&format=text&timeout=5000")
        out += parse_txt(txt, proto, "proxyscrape-api")
    return out

def fetch_proxifly():
    out = []
    for proto in ("http", "socks4", "socks5"):
        txt = _get_text(f"https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/{proto}/data.txt")
        out += parse_txt(txt, proto, "proxifly")
    return out

def fetch_monosans():
    out = []
    for proto in ("http", "socks4", "socks5"):
        txt = _get_text(f"https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/{proto}.txt")
        out += parse_txt(txt, proto, "monosans")
    return out

def fetch_proxora():
    data = _get_json("https://api.proxora.io/api/tools/free-proxies")
    out = []
    items = data.get("items", []) if isinstance(data, dict) else []
    for d in items:
        out.append({"ip": d.get("host"), "port": d.get("port"),
                    "protocol": str(d.get("protocol", "http")).lower(),
                    "country": d.get("country", ""), "country_code": d.get("country_code", ""),
                    "anonymity": d.get("anonymity", ""), "latency_ms": d.get("latency_ms"),
                    "source": "proxora", "verified_by_source": True})
    return out

def fetch_geonode():
    data = _get_json("https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc")
    out = []
    items = data.get("data", []) if isinstance(data, dict) else []
    for d in items:
        protos = d.get("protocols") or ["http"]
        out.append({"ip": d.get("ip"), "port": int(d.get("port")) if str(d.get("port", "")).isdigit() else 0,
                    "protocol": str(protos[0]).lower(),
                    "country": d.get("country", ""), "country_code": d.get("country", ""),
                    "anonymity": d.get("anonymity", ""), "latency_ms": d.get("responseTime"),
                    "source": "geonode", "verified_by_source": True})
    return [x for x in out if x["ip"] and x["port"]]

SOURCES = [
    ("proxyscrape", fetch_proxyscrape),
    ("proxifly", fetch_proxifly),
    ("monosans", fetch_monosans),
    ("proxora", fetch_proxora),
    ("geonode", fetch_geonode),
]

def fetch_all():
    all_items, per_source = [], {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {name: ex.submit(fn) for name, fn in SOURCES}
        for name, fut in futs.items():
            try:
                items = fut.result() or []
            except Exception as e:
                print(f"  {name} error: {e}")
                items = []
            per_source[name] = len(items)
            print(f"  {name}: {len(items)}")
            all_items += items
    # 去重：ip:port+protocol 保留一条，合并 source
    seen = {}
    for p in all_items:
        if not p.get("ip") or not p.get("port"):
            continue
        key = (p["ip"], p["port"], p["protocol"])
        if key not in seen:
            seen[key] = p
        else:
            old = seen[key]
            if p.get("country") and not old.get("country"):
                old["country"] = p["country"]; old["country_code"] = p.get("country_code", "")
            if p.get("latency_ms") and not old.get("latency_ms"):
                old["latency_ms"] = p["latency_ms"]
            if p["source"] not in old["source"]:
                old["source"] += "," + p["source"]
    proxies = list(seen.values())
    # 排序：有延迟的按延迟升序，没延迟的放后面
    proxies.sort(key=lambda x: (x["latency_ms"] is None, x["latency_ms"] or 99999))
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "updated_at": now,
        "updated_at_cst": datetime.now().astimezone().isoformat(),
        "total": len(proxies),
        "per_source": per_source,
        "by_protocol": {pr: sum(1 for p in proxies if p["protocol"] == pr) for pr in ("http", "socks4", "socks5")},
        "warning": "免费代理存活很短，仅供学习测试，勿用于登录/支付/重要账号。",
        "proxies": proxies,
    }
    return result

if __name__ == "__main__":
    print("开始全网抓取免费代理...")
    t0 = time.time()
    result = fetch_all()
    with open("proxies.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"完成：{result['total']} 个去重代理，用时 {time.time()-t0:.1f}s，按协议 {result['by_protocol']}")
