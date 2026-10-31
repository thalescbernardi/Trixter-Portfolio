# Executor dos e-mails. A configuração entra em execução, por --config ou TRIXTER_CONFIG.
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL -o /tmp/packages-microsoft-prod.deb https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-envios.txt .
RUN pip install --no-cache-dir -r requirements-envios.txt

COPY executar_envios.py .
COPY trixter ./trixter
COPY sql ./sql

RUN useradd --create-home --uid 10001 trixter \
    && chown -R trixter:trixter /app
USER trixter

ENTRYPOINT ["python", "executar_envios.py"]
CMD ["--enviar"]
