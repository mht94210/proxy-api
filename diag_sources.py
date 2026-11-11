# -*- coding: utf-8 -*-
"""在服务器上试几个 VM 上没成的新源：66ip、西拉、ihuan、openproxy、FineProxy。"""
import urllib.request, ssl, re, json
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def get(url, timeout=20):
    for ctx in (None, ssl._create_unverified_context()):
        try:
            req = urllib.request.Request(url, headers=H)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            continue
    return ""

# 66ip: http://www.66ip.cn/nmtq.php?getnum=300&isp=0&anonymity=0&start=&ports=&export=&ipaddress=&area=1&proxytype=0&api=66ip
for name, url, pat in [
    ("66ip", "http://www.66ip.cn/nmtq.php?getnum=300&isp=0&anonymity=0&start=&ports=&export=&ipaddress=&area=1&proxytype=0&api=66ip", r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)"),
    ("xiladaili", "http://www.xiladaili.com/gaoni/", r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)"),
    ("ihuan", "https://ip.ihuan.me/", r"(\d{1,3}(?:\.\d{1,3}){3})</a></td><td>(\d+)</td>"),
    ("openproxy", "https://openproxy.space/list/http", r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)"),
    ("fineproxy", "https://fineproxy.org/en/free-proxy/", r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)"),
]:
    t = get(url)
    rows = re.findall(pat, t or "")
    print(f"{name}: bytes={len(t or '')} rows={len(rows)}", flush=True)
