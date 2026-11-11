FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py fetcher_cn.py fetcher.py ./
# 构建时先抓一次中国 HTTP 代理，容器启动后由定时任务每 2 小时再跑 fetcher_cn.py 更新 proxies.json
RUN python fetcher_cn.py || echo "initial fetch failed, will retry on start"
CMD ["sh", "-c", "python fetcher_cn.py; uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
