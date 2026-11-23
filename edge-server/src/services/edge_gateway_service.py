from src.infrastructure.grpc_client import CentralGrpcClient
from src.services.load_balancer_service import RoundRobinLoadBalancer

class EdgeGatewayService:
    """
    Camada de Serviço (Gateway):
    Coordena a seleção do servidor central pelo Load Balancer
    e executa a tradução de protocolo (REST HTTP -> gRPC).
    """
    def __init__(self, load_balancer: RoundRobinLoadBalancer, grpc_client: CentralGrpcClient):
        self.load_balancer = load_balancer
        self.grpc_client = grpc_client

    def handle_upload(self, filename: str, content: bytes, client_id: str) -> dict:
        target_server = self.load_balancer.get_next_server(f"UPLOAD '{filename}'")
        return self.grpc_client.upload_file(
            target_server=target_server,
            filename=filename,
            content=content,
            client_id=client_id
        )

    def handle_download(self, filename: str) -> dict:
        target_server = self.load_balancer.get_next_server(f"DOWNLOAD '{filename}'")
        return self.grpc_client.download_file(
            target_server=target_server,
            filename=filename
        )

    def handle_list_files(self) -> dict:
        target_server = self.load_balancer.get_next_server("LIST_FILES")
        return self.grpc_client.list_files(target_server=target_server)
