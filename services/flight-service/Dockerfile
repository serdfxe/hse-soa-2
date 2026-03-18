# Stage 1: generate protobuf code
FROM python:3.12-slim AS codegen

RUN pip install --no-cache-dir grpcio-tools==1.67.1 protobuf==5.28.3

WORKDIR /build
COPY proto/flight.proto proto/flight.proto

RUN mkdir -p app/generated && \
    python -m grpc_tools.protoc \
        -I proto \
        --python_out=app/generated \
        --grpc_python_out=app/generated \
        proto/flight.proto && \
    sed -i 's/^import flight_pb2/from app.generated import flight_pb2/' app/generated/flight_pb2_grpc.py


# Stage 2: runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=codegen /build/app/generated app/generated

COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh && \
    adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 50051

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
