# ── Stage 1: generate Pydantic models from OpenAPI spec ──────────────────────
FROM python:3.12-slim AS codegen

WORKDIR /codegen

RUN pip install --no-cache-dir datamodel-code-generator==0.26.4

COPY openapi/ openapi/
COPY generate.sh .

RUN bash generate.sh


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=codegen /codegen/app/generated/ app/generated/

COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
