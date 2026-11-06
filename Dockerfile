FROM python:3.12-slim
# git: the agent clones, commits and pushes. curl/procps/iproute2: the shell tools an agent reaches for.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates procps iproute2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY static ./static
EXPOSE 8000
CMD ["uvicorn", "server:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
