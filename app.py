"""免费代理 API 服务 - FastAPI
启动：uvicorn app:app --host 0.0.0.0 --port 8000
数据文件 proxies.json 由 fetcher.py 每天生成；超过 24 小时未更新时接口会提示过期。
"""
import json, os, random, time
from datetime import datetime, timezone
from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

DATA_FILE = os.path.join(os.path.dirname(__file__), "proxies.json")
VERSION = "1.0.0-20261112"

app = FastAPI(title="免费代理 API", version=VERSION, description="每天聚合全网免费代理，HTTP/SOCKS4/SOCKS5，仅供学习测试")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_cache = {"mtime": 0, "data": None}

def load_data():
    try:
        mtime = os.path.getmtime(DATA_FILE)
    except OSError:
        return {"updated_at": None, "total": 0, "proxies": [], "by_protocol": {}, "per_source": {}}
    if _cache["data"] is None or mtime != _cache["mtime"]:
        with open(DATA_FILE, encoding="utf-8") as f:
            _cache["data"] = json.load(f)
        _cache["mtime"] = mtime
    return _cache["data"]

def filter_proxies(data, protocol="all", country="", limit=100):
    items = data.get("proxies", [])
    if protocol != "all":
        items = [p for p in items if p["protocol"] == protocol]
    if country:
        c = country.upper()
        items = [p for p in items if p.get("country_code", "").upper() == c or p.get("country", "").upper() == c]
    return items[:limit]

def stale_hours(data):
    if not data.get("updated_at"):
        return 999
    try:
        dt = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 999

@app.get("/")
def index():
    d = load_data()
    return {
        "name": "免费代理 API", "version": VERSION,
        "updated_at": d.get("updated_at"), "total": d.get("total"),
        "by_protocol": d.get("by_protocol"),
        "warning": "免费代理存活很短，仅供学习测试，勿用于登录/支付。",
        "endpoints": {
            "列表JSON": "/api/proxies?protocol=http&country=CN&limit=100",
            "随机一个": "/api/proxy/random?protocol=socks5",
            "纯文本": "/api/proxies.txt?protocol=http&limit=100",
            "状态": "/api/status",
            "文档": "/docs",
        },
    }

@app.get("/api/status")
def status():
    d = load_data()
    h = stale_hours(d)
    return {"version": VERSION, "updated_at": d.get("updated_at"), "total": d.get("total"),
            "by_protocol": d.get("by_protocol"), "per_source": d.get("per_source"),
            "stale_hours": round(h, 1), "fresh": h < 24}

@app.get("/api/proxies")
def proxies(protocol: str = Query("all", pattern="^(all|http|socks4|socks5)$"),
            country: str = "", limit: int = Query(100, ge=1, le=1000)):
    d = load_data()
    items = filter_proxies(d, protocol, country, limit)
    return {"updated_at": d.get("updated_at"), "total_in_pool": d.get("total"),
            "returned": len(items), "protocol": protocol, "country": country or "all",
            "proxies": [{"proxy": f"{p['protocol']}://{p['ip']}:{p['port']}",
                         "ip": p["ip"], "port": p["port"], "protocol": p["protocol"],
                         "country": p.get("country", ""), "country_code": p.get("country_code", ""),
                         "anonymity": p.get("anonymity", ""), "latency_ms": p.get("latency_ms"),
                         "source": p.get("source", "")} for p in items]}

@app.get("/api/proxy/random")
def random_proxy(protocol: str = Query("all", pattern="^(all|http|socks4|socks5)$"), country: str = ""):
    d = load_data()
    items = filter_proxies(d, protocol, country, 1000)
    if not items:
        return JSONResponse({"error": "no proxy in pool, try again later or run fetcher.py"}, status_code=503)
    p = random.choice(items[:200])  # 优先延迟低的前 200 个里随机
    return {"proxy": f"{p['protocol']}://{p['ip']}:{p['port']}",
            "ip": p["ip"], "port": p["port"], "protocol": p["protocol"],
            "country": p.get("country", ""), "country_code": p.get("country_code", ""),
            "latency_ms": p.get("latency_ms"), "source": p.get("source", "")}

@app.get("/api/proxies.txt", response_class=PlainTextResponse)
def proxies_txt(protocol: str = Query("all", pattern="^(all|http|socks4|socks5)$"),
                country: str = "", limit: int = Query(100, ge=1, le=1000)):
    d = load_data()
    items = filter_proxies(d, protocol, country, limit)
    return "\n".join(f"{p['protocol']}://{p['ip']}:{p['port']}" for p in items) + ("\n" if items else "")

@app.get("/health")
def health():
    return {"ok": True, "version": VERSION, "time": datetime.now(timezone.utc).isoformat()}
