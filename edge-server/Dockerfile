FROM python:3.11-slim

WORKDIR /app

# Instala Flask, gRPC e Protobuf
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Compila o contrato .proto para gerar os stubs gRPC do cliente
COPY proto/ ./proto/
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=. \
    --grpc_python_out=. \
    ./proto/storage.proto

# Copia o código-fonte do Servidor de Borda em camadas
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
