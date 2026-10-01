# ==========================================
# 價值投資選股 App - 生產級 Dockerfile
# ==========================================
FROM python:3.12-slim

# 設定環境變數：禁用字節碼、無緩衝輸出、設定時區為台北
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Taipei \
    PORT=8000 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# 安裝基礎依賴套件 (curl 用於 Docker 健康檢查, tzdata 設定時區)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 建立非 root 安全執行使用者
RUN groupadd -r appgroup && useradd -r -g appgroup -d ${APP_HOME} -s /sbin/nologin appuser

# 安裝 Python 套件依賴
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 複製專案程式碼與配置
COPY . .

# 建立並配置持久化資料目錄權限
RUN mkdir -p ${APP_HOME}/data && \
    chown -R appuser:appgroup ${APP_HOME}

# 切換為安全非特權使用者
USER appuser

# 開放 FastAPI 服務連接埠
EXPOSE 8000

# 宣告持久化儲存卷 (保持 SQLite 資料庫與日誌持久化)
VOLUME ["/app/data"]

# 容器健康檢查 (每 30 秒向 /health 發送請求)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 啟動應用程式
CMD ["python", "run.py"]
