FROM python:3.11-slim

WORKDIR /app

# Instala as dependências (gRPC e Protobuf)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o arquivo .proto e gera os stubs gRPC em Python automaticamente no build
COPY proto/ ./proto/
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=. \
    --grpc_python_out=. \
    ./proto/storage.proto

# Copia o código-fonte organizado em camadas
COPY src/ ./src/

# Garante que os logs do Python apareçam em tempo real no Docker
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
