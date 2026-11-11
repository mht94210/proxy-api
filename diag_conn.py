# -*- coding: utf-8 -*-
"""诊断服务器到快代理的连通性：DNS、TCP、HTTP、HTTPS 各是什么错。"""
import socket, urllib.request, ssl

host = "www.kuaidaili.com"
try:
    ip = socket.gethostbyname(host)
    print("DNS OK:", ip, flush=True)
except Exception as e:
    print("DNS FAIL:", type(e).__name__, str(e)[:120], flush=True)
    ip = None
if ip:
    for port in (80, 443):
        s = socket.socket()
        s.settimeout(10)
        try:
            s.connect((ip, port))
            print(f"TCP {port} OK", flush=True)
        except Exception as e:
            print(f"TCP {port} FAIL:", type(e).__name__, str(e)[:120], flush=True)
        finally:
            s.close()
    for url in ("http://www.kuaidaili.com/free/inha/1/", "https://www.kuaidaili.com/free/inha/1/"):
        for ctx_name, ctx in (("verify", None), ("no-verify", ssl._create_unverified_context())):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                    body = r.read()
                    print(f"{url} [{ctx_name}] OK {r.status} {len(body)} bytes", flush=True)
            except Exception as e:
                print(f"{url} [{ctx_name}] FAIL:", type(e).__name__, str(e)[:120], flush=True)
