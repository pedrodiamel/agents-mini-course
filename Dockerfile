FROM python:3.11-slim-bookworm

WORKDIR /app

# Sem .pyc: o /app e um bind mount do repo do host, e o container roda como root —
# sem isso os __pycache__ gerados ficam com owner root na arvore do usuario.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Node e necessario para o `npx @modelcontextprotocol/inspector` da aula 06.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    byobu \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

#CMD ["python", "demo_ollama.py"]
