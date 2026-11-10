# CasePath as one service: the case API, the case worker's workspace and the agent core.
#   docker build -t casepath .                       (BASE_IMAGE and PIP_INDEX_URL can point to internal mirrors;
#     behind a firewall that re-signs TLS add --secret id=ca,src=<its CA bundle>; the bundle is not kept in the image)
#   docker run -p 8080:8080 -v casepath-data:/data --env-file <settings> casepath
# Settings come from the environment (see deploy/workspace/env.example and docs/DEPLOYMENT.md); none are baked in.
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}
ARG PIP_INDEX_URL=
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    CASEPATH_DATA_DIR=/data CASEPATH_WORKFLOW_CATALOGUE=/app/catalogue CASEPATH_PORT=8080
WORKDIR /app
COPY . /src
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi \
 && pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} "/src[azure]" \
 && mkdir -p /app/catalogue /data \
 && if [ -d /src/catalogue ]; then cp /src/catalogue/*.json /app/catalogue/; fi \
 && if [ -d /src/benchmark ]; then cp -r /src/benchmark /app/benchmark; fi \
 && rm -rf /src \
 && useradd --system --uid 10001 --home /app casepath && chown -R casepath /data
USER 10001
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"CASEPATH_PORT\",\"8080\")}/api/health',timeout=4)"
CMD ["sh", "-c", "exec python -m casepath serve --host 0.0.0.0 --port ${CASEPATH_PORT}"]
