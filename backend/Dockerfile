FROM python:3.12-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_EXTRA_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
WORKDIR /workspace/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --progress-bar off \
    --index-url "$PIP_INDEX_URL" \
    --extra-index-url "$PIP_EXTRA_INDEX_URL" \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt
COPY backend/app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
