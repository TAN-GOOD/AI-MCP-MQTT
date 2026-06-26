FROM python:3.11-slim

# 可选：通过 ARG 控制镜像源（默认使用官方 PyPI，海外用户无需改动；
# 国内用户构建时可通过 --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple 切换）
ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i ${PIP_INDEX_URL}

# 创建非 root 用户，提升容器安全性
RUN useradd -m -u 1000 app

COPY . .

# 确保工作目录及文件归属于 app 用户
RUN chown -R app:app /app

USER app

EXPOSE 8000

# 健康检查：每 30s 探测一次 /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
