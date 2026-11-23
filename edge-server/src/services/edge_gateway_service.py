import logging
import grpc
from concurrent import futures
from src.config.settings import Config
from src.infrastructure.grpc_client import CentralGrpcClient
from src.services.load_balancer_service import RoundRobinLoadBalancer

logger = logging.getLogger("EdgeGateway")

class EdgeGatewayService:
    """
    Camada de Serviço (Gateway + Fatiamento de Arquivos + Failover para Redundância):
    1. No UPLOAD: Divide o arquivo ao meio (Parte 1 e Parte 2), envia para central-1 e central-2,
       que replicam para o 'server-backup'.
    2. No DOWNLOAD: Tenta buscar cada metade no Servidor Central primário.
       Se o Servidor Central estiver OFFLINE (ex: docker stop central-2), aciona o FAILOVER
       automático e busca a metade faltante no 'server-backup'!
    """
    def __init__(self, load_balancer: RoundRobinLoadBalancer, grpc_client: CentralGrpcClient):
        self.load_balancer = load_balancer
        self.grpc_client = grpc_client
        self.backup_server = Config.BACKUP_SERVER_ADDRESS

    def handle_upload(self, filename: str, content: bytes, client_id: str) -> dict:
        original_size = len(content)
        midpoint = original_size // 2

        part1_bytes = content[:midpoint]
        part2_bytes = content[midpoint:]

        chunks_to_send = [
            (1, f"{filename}.part1", part1_bytes),
            (2, f"{filename}.part2", part2_bytes),
        ]

        logger.info(
            f"✂️ [Sharding] Arquivo '{filename}' ({original_size} bytes) dividido ao meio: "
            f"Parte 1 ({len(part1_bytes)}B) e Parte 2 ({len(part2_bytes)}B)"
        )

        tasks = []
        for part_num, chunk_name, chunk_bytes in chunks_to_send:
            target_server = self.load_balancer.get_next_server(f"UPLOAD {chunk_name}")
            tasks.append((target_server, part_num, chunk_name, chunk_bytes))

        chunk_results = []
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_part = {
                executor.submit(
                    self.grpc_client.save_chunk,
                    target_server,
                    filename,
                    part_num,
                    2,
                    chunk_name,
                    chunk_bytes,
                    original_size,
                    client_id
                ): part_num
                for target_server, part_num, chunk_name, chunk_bytes in tasks
            }
            for future in futures.as_completed(future_to_part):
                chunk_results.append(future.result())

        chunk_results.sort(key=lambda x: x["part_number"])

        return {
            "success": True,
            "filename": filename,
            "original_size": original_size,
            "total_parts": 2,
            "uploaded_by": client_id,
            "message": "Arquivo dividido ao meio, salvo nos 2 Servidores Centrais e replicado no Server-Backup!",
            "chunks": chunk_results
        }

    def _query_file_map_with_failover(self, filename: str) -> dict:
        """Tenta consultar o Mapa de Chunks nos servidores centrais; se falhar, consulta o server-backup."""
        primary = self.load_balancer.get_next_server(f"GET_MAP '{filename}'")
        try:
            return self.grpc_client.get_file_map(target_server=primary, original_filename=filename)
        except grpc.RpcError:
            logger.warning(
                f"⚠️ [Failover Metadados] Servidor {primary} offline! Consultando Mapa no Backup ({self.backup_server})..."
            )
            return self.grpc_client.get_file_map(target_server=self.backup_server, original_filename=filename)

    def handle_download(self, filename: str) -> dict:
        file_map = self._query_file_map_with_failover(filename=filename)

        if not file_map.get("found"):
            return {
                "found": False,
                "filename": filename,
                "message": f"Arquivo '{filename}' não encontrado no Banco de Metadados.",
                "handled_by_central": file_map.get("handled_by_central", "unknown")
            }

        chunks_info = sorted(file_map["chunks"], key=lambda c: c["part_number"])
        reassembled = bytearray()
        fetched_from = []

        # Busca cada metade no Servidor Central Primário; se estiver caído, faz FAILOVER para o server-backup!
        for chunk in chunks_info:
            primary_addr = chunk["server_grpc_address"]
            backup_addr = chunk.get("backup_server_address") or self.backup_server
            chunk_name = chunk["chunk_filename"]
            part_num = chunk["part_number"]

            try:
                chunk_resp = self.grpc_client.get_chunk(target_server=primary_addr, chunk_filename=chunk_name)
                if not chunk_resp["found"]:
                    raise RuntimeError(f"Chunk ausente no primário {primary_addr}")
                reassembled.extend(chunk_resp["content"])
                fetched_from.append(f"Parte {part_num} de {chunk['server_id']}")
            except Exception as e:
                logger.warning(
                    f"🚑 [FAILOVER] Servidor primário [{primary_addr}] indisponível para '{chunk_name}'! "
                    f"Recuperando cópia redundante em [{backup_addr}]..."
                )
                backup_resp = self.grpc_client.get_chunk(target_server=backup_addr, chunk_filename=chunk_name)
                if not backup_resp["found"]:
                    return {
                        "found": False,
                        "filename": filename,
                        "message": f"Fatia '{chunk_name}' indisponível tanto no primário quanto no backup!",
                        "handled_by_central": backup_addr
                    }
                reassembled.extend(backup_resp["content"])
                fetched_from.append(f"Parte {part_num} de {backup_resp['handled_by_central']}")

        logger.info(
            f"🧩 [Reassembly] Arquivo '{filename}' ({len(reassembled)} bytes) remontado com sucesso! ({', '.join(fetched_from)})"
        )

        return {
            "found": True,
            "filename": filename,
            "content": bytes(reassembled),
            "handled_by_central": " + ".join(fetched_from),
            "message": "Arquivo remontado com sucesso (Tolerante a Falhas)."
        }

    def handle_list_files(self) -> dict:
        target_server = self.load_balancer.get_next_server("LIST_FILES")
        try:
            return self.grpc_client.list_files(target_server=target_server)
        except grpc.RpcError:
            logger.warning(
                f"⚠️ [Failover Listagem] Servidor {target_server} offline! Listando via Backup ({self.backup_server})..."
            )
            return self.grpc_client.list_files(target_server=self.backup_server)
