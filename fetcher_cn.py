"""中国境内免费代理专版 v2：只留 HTTP/HTTPS，目标 1000 个，按质量排序
重要实测结论（2026-11-12）：
 - 89ip 直出接口 num=2000 能返回 2000 个，但只有约 36% 是真中国 IP，其余是国外，
   必须用 APNIC 中国 IPv4 段过滤，不能直接当中国 IP 用。
 - 站大爷 zdaye 25 页约 500 个，HTTP 约 87%；快代理、齐云、云代理都是中国站，可直接当 CN。
 - ProxyScrape-CN、Geonode-CN（86）、Proxora-CN（21）是源头已标 CN 的。
 - 最终只保留 protocol=http（HTTPS 归一为 http，HTTP 代理走 CONNECT 本来就能跑 HTTPS）。
"""
import json, re, time, math, ipaddress, requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 15

def get(u):
    try:
        r = requests.get(u, headers=H, timeout=TIMEOUT)
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text if r.status_code == 200 else ""
    except Exception as e:
        print(f"  fail {u}: {e}")
        return ""

_CN_NETS = None
def cn_nets():
    global _CN_NETS
    if _CN_NETS is not None:
        return _CN_NETS
    nets = []
    try:
        t = requests.get("https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest", headers=H, timeout=30).text
        for line in t.splitlines():
            p = line.split("|")
            if len(p) >= 7 and p[1] == "CN" and p[2] == "ipv4":
                prefix = 32 - int(math.log2(int(p[4])))
                nets.append(ipaddress.ip_network(f"{p[3]}/{prefix}", strict=False))
        nets = list(ipaddress.collapse_addresses(nets))
    except Exception as e:
        print(f"  APNIC download fail: {e}, 89ip CN filtering disabled")
        nets = []
    _CN_NETS = nets
    print(f"  APNIC CN nets: {len(nets)}")
    return nets

def is_cn(ip):
    nets = cn_nets()
    if not nets:
        return True
    try:
        a = ipaddress.ip_address(ip)
        return any(a in n for n in nets)
    except Exception:
        return False

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

def fetch_zdaye(pages=25):
    out = []
    for p in range(1, pages + 1):
        url = "https://www.zdaye.com/free/" if p == 1 else f"https://www.zdaye.com/free/{p}/"
        t = get(url)
        for m in re.finditer(r'proxy_ip">(\d{1,3}(?:\.\d{1,3}){3})</p><p class="proxy_port">Port[：:](\d+)', t):
            seg = t[m.start():m.start()+500]
            proto = "socks5" if "socks5" in seg.lower() else ("socks4" if "socks4" in seg.lower() else "http")
            if proto != "http":
                continue
            anon = "elite" if "高匿" in seg else ""
            city = ""
            cm = re.search(r'title="([^"]{0,30})"', seg)
            if cm:
                city = cm.group(1).strip()
            o = norm(m.group(1), m.group(2), city=city, anon=anon, source="zdaye")
            if o:
                out.append(o)
        time.sleep(0.2)
    print(f"  zdaye http: {len(out)}")
    return out

def fetch_kuaidaili():
    out = []
    for path in ("inha", "intr"):
        for page in range(1, 6):
            url = f"https://www.kuaidaili.com/free/{path}/{page}/" if page > 1 else f"https://www.kuaidaili.com/free/{path}/"
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
                o = norm(ip, port, city=loc, anon="elite", lat=lat, source="kuaidaili")
                if o:
                    out.append(o)
            time.sleep(0.2)
    print(f"  kuaidaili http: {len(out)}")
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
        o = norm(ip, port, city=loc.strip(), anon="elite" if anon == "高匿" else anon, lat=lat, source="qiyunip")
        if o:
            out.append(o)
    print(f"  qiyunip http: {len(out)}")
    return out

def fetch_89ip():
    out, total, cn_count = [], 0, 0
    t = get("http://www.89ip.cn/tqdl.html?api=1&num=2000&port=&address=&isp=")
    for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)", t):
        total += 1
        if not is_cn(ip):
            continue
        cn_count += 1
        o = norm(ip, port, anon="", source="89ip")
        if o:
            out.append(o)
    print(f"  89ip: {total} raw -> {cn_count} CN-filtered")
    return out

def fetch_ip3366():
    out = []
    for stype in (1, 2):
        t = get(f"http://www.ip3366.net/free/?stype={stype}")
        for ip, port in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})</td>\s*<td[^>]*>(\d+)</td>", t):
            o = norm(ip, port, anon="elite", source="ip3366")
            if o:
                out.append(o)
    print(f"  ip3366 http: {len(out)}")
    return out

def fetch_hproxy_cn():
    """HProxy 免费 API：country=CN & protocol=http，带匿名度/延迟/在线率。"""
    out = []
    try:
        data = json.loads(get("https://hproxy.com/api/proxy-list?format=json&country=CN&protocol=http") or "[]")
        for x in data:
            if x.get("country_code") != "CN":
                continue
            protos = x.get("protocols") or []
            if "http" not in [str(p).lower() for p in protos]:
                continue
            lat = x.get("latency_ms")
            try:
                lat = float(lat) if lat is not None else None
            except Exception:
                lat = None
            out.append(norm(x["ip"], int(x["port"]), x.get("city", "") or "",
                            (x.get("anonymity") or "").lower(), lat, "hproxy"))
    except Exception as e:
        print("  hproxy-cn fail:", e)
    print(f"  hproxy-cn http: {len(out)}")
    return out

def fetch_monosans_cn():
    """monosans 全球 HTTP 列表，经 APNIC 中国段过滤。"""
    out = []
    try:
        for line in (get("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt") or "").splitlines():
            m = re.match(r"(\d+\.\d+\.\d+\.\d+):(\d+)", line.strip())
            if m and is_cn(m.group(1)):
                out.append(norm(m.group(1), int(m.group(2)), "", "", None, "monosans-cn"))
    except Exception as e:
        print("  monosans-cn fail:", e)
    print(f"  monosans-cn http: {len(out)}")
    return out

def fetch_proxora_cn():
    out = []
    try:
        r = requests.get("https://api.proxora.io/api/tools/free-proxies?country=CN", headers=H, timeout=TIMEOUT)
        for d in r.json().get("items", []):
            if str(d.get("protocol", "")).lower() != "http":
                continue
            o = norm(d.get("host"), d.get("port"), city=d.get("city", ""),
                     anon=d.get("anonymity", ""), lat=d.get("latency_ms"), source="proxora-cn")
            if o:
                out.append(o)
    except Exception as e:
        print(f"  proxora-cn fail: {e}")
    print(f"  proxora-cn http: {len(out)}")
    return out

def fetch_global_cn():
    out = []
    t = get("https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=protocolipport&format=text&country=cn&timeout=5000")
    for m in re.finditer(r"(?:https?://)?(\d{1,3}(?:\.\d{1,3}){3}):(\d+)", t):
        o = norm(m.group(1), m.group(2), anon="elite", source="proxyscrape-cn")
        if o:
            out.append(o)
    try:
        r = requests.get("https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&country=CN", headers=H, timeout=TIMEOUT)
        for d in r.json().get("data", []):
            protos = [str(x).lower() for x in (d.get("protocols") or [])]
            if not any(p in ("http", "https") for p in protos):
                continue
            o = norm(d.get("ip"), d.get("port"), city=d.get("city", ""),
                     anon=d.get("anonymityLevel", ""), lat=d.get("latency"), source="geonode-cn")
            if o:
                out.append(o)
    except Exception as e:
        print(f"  geonode-cn fail: {e}")
    print(f"  global-cn http: {len(out)}")
    return out

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

def subnet24(ip):
    return ".".join(str(ip).split(".")[:3])

def dedupe_by_subnet(proxies):
    """每 /24 网段只留最好一个（列表已按质量排过序，留第一个）。"""
    seen, out = set(), []
    for p in proxies:
        s = subnet24(p["ip"])
        if s in seen:
            continue
        seen.add(s)
        out.append(p)
    return out

def select_best(proxies, history_path="seen_best.json"):
    """质量优先版：高匿 + 延迟<2000ms，或延迟<300ms；每 /24 只留一个。
    注意：不排除上一轮的 IP——真正快的 IP 在各家源里本来就稳定，硬轮换只会把
    最快的换成更慢的。2 小时一次重抓本身就是更新：源里死了的自动消失，新出现的自动进来。"""
    cand = [p for p in proxies if p.get("latency_ms") is not None
            and ((p.get("anonymity") == "elite" and p["latency_ms"] < 2000) or p["latency_ms"] < 300)]
    cand.sort(key=lambda x: x["latency_ms"])
    return dedupe_by_subnet(cand)

def fetch_all_cn():
    all_items = []
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = [ex.submit(fn) for fn in (fetch_zdaye, fetch_kuaidaili, fetch_qiyunip, fetch_89ip, fetch_ip3366, fetch_proxora_cn, fetch_global_cn, fetch_hproxy_cn, fetch_monosans_cn)]
        for f in futs:
            try:
                all_items += f.result() or []
            except Exception as e:
                print("  source error:", e)
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
    # 全列表也按 /24 去重：每段只留最好一个，后面不再出现重复段
    proxies = dedupe_by_subnet(proxies)
    now = datetime.now(timezone.utc).isoformat()
    return {"updated_at": now, "total": len(proxies),
            "by_protocol": {"http": len(proxies)},
            "country": "CN", "protocols": ["http", "https"],
            "warning": "中国境内 HTTP/HTTPS 免费代理，每 /24 网段只留一个，仅供学习测试，勿用于登录/支付/重要账号。免费代理存活很短，每 2 小时更新一次。",
            "proxies": proxies}

if __name__ == "__main__":
    print("开始抓中国境内 HTTP/HTTPS 免费代理（每 /24 只留一个）...")
    t0 = time.time()
    r = fetch_all_cn()
    with open("proxies_cn.json", "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    with open("proxies.json", "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    with open("proxies_cn.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in r["proxies"]) + "\n")
    best = select_best(r["proxies"])
    with open("proxies_best.json", "w", encoding="utf-8") as f:
        json.dump({"updated_at": r["updated_at"], "total": len(best), "country": "CN",
                   "protocols": ["http", "https"],
                   "definition": "高匿 + 延迟<2000ms，或延迟<300ms；每 /24 只留一个",
                   "proxies": best}, f, ensure_ascii=False, indent=1)
    with open("proxies_best.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in best) + ("\n" if best else ""))
    print(f"完成：CN HTTP {r['total']} 个（已按 /24 去重），最好版 {len(best)} 个，用时 {time.time()-t0:.1f}s")
    for p in best[:10]:
        print(f"  http://{p['ip']}:{p['port']} {p.get('city','')} {p.get('anonymity','')} 延迟{p.get('latency_ms')}ms 质量{p['quality']} 来源{p['source']}")
