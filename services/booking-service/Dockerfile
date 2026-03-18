# ── Stage 1: generate gRPC stubs from proto ───────────────────────────────────
FROM python:3.12-slim AS codegen

WORKDIR /codegen

RUN pip install --no-cache-dir grpcio-tools==1.67.1 protobuf==5.28.3

COPY proto/flight.proto proto/flight.proto

RUN mkdir -p app/generated && \
    python -m grpc_tools.protoc \
        -I proto \
        --python_out=app/generated \
        --grpc_python_out=app/generated \
        proto/flight.proto && \
    sed -i 's/^import flight_pb2/from app.generated import flight_pb2/' \
        app/generated/flight_pb2_grpc.py


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
