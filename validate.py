"""实测验证：对候选代理真的发一次请求，看通不通、实际延迟多少。
只验证，不登录、不传账号。目标：http://httpbin.org/ip，超时 5 秒。
输出 proxies_best.json / proxies_best.txt：只留验证通过的，按实测延迟排序。
"""
import json, time, requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

def check(p):
    url = f"http://{p['ip']}:{p['port']}"
    proxies = {"http": url, "https": url}
    t0 = time.time()
    try:
        r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=5)
        if r.status_code == 200 and "origin" in r.text:
            return {**p, "verified": True, "real_latency_ms": round((time.time()-t0)*1000),
                    "verified_at": datetime.now(timezone.utc).isoformat()}
    except Exception:
        pass
    return None

if __name__ == "__main__":
    d = json.load(open("proxies_cn.json"))
    ps = d["proxies"]
    # 候选：质量分前 250 + 无延迟的随机 150（89ip 为主），共 400 个
    import random
    random.seed(12)
    top = ps[:250]
    rest = [p for p in ps[250:] if p.get("latency_ms") is None]
    sample = random.sample(rest, min(150, len(rest)))
    cand = top + sample
    print(f"验证候选 {len(cand)} 个（前250 + 无延迟抽样150）...")
    t0 = time.time()
    ok = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        for res in ex.map(check, cand):
            if res:
                ok.append(res)
    ok.sort(key=lambda x: x["real_latency_ms"])
    print(f"通过 {len(ok)}/{len(cand)}，用时 {time.time()-t0:.1f}s")
    for p in ok[:15]:
        print(f"  http://{p['ip']}:{p['port']} {p.get('city','')} {p.get('anonymity','')} 实测{p['real_latency_ms']}ms 来源{p['source']}")
    out = {"updated_at": datetime.now(timezone.utc).isoformat(), "total": len(ok),
           "checked": len(cand), "country": "CN", "protocols": ["http", "https"],
           "note": "实测通过 httpbin.org/ip 的中国 HTTP 代理，按实测延迟排序",
           "proxies": ok}
    with open("proxies_best.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open("proxies_best.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(f"http://{p['ip']}:{p['port']}" for p in ok) + ("\n" if ok else ""))
    print(f"已写 proxies_best.json/txt：{len(ok)} 个")
