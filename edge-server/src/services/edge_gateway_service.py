import hashlib
import logging
import grpc
from concurrent import futures
from src.config.settings import Config
from src.infrastructure.grpc_client import CentralGrpcClient
from src.services.load_balancer_service import RoundRobinLoadBalancer

logger = logging.getLogger("EdgeGateway")

class EdgeGatewayService:
    """
    Camada de Serviço (Gateway + Fatiamento + Validação Distribuída SHA-256 + Failover):
    1. No UPLOAD:
       - Etapa A (Cálculo Distribuído de SHA-256 nos Workers):
         Divide o arquivo ao meio (Parte 1 e Parte 2) e envia em paralelo para os Workers
         dos 2 Servidores Centrais calcularem o SHA-256 de cada metade (`ComputeChunkHash`).
       - Etapa B (Soma dos Hashes):
         Combina o SHA-256 da Parte 1 + SHA-256 da Parte 2 gerando o `combined_file_sha256`.
         Assim, se um arquivo novo tiver apenas 50% igual a outro, a soma será diferente e NÃO dará falso positivo!
       - Etapa C (Validação na Região Crítica com Token Ring + Gravação e Replicação):
         Envia as duas metades com o hash composto para os Servidores Centrais. Dentro do Token Ring,
         eles verificam se a soma dos hashes já existe no banco SQLite. Se já existir, bloqueia a duplicata!
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

        # Seleciona os servidores via Load Balancer (Round-Robin)
        tasks = []
        for part_num, chunk_name, chunk_bytes in chunks_to_send:
            target_server = self.load_balancer.get_next_server(f"UPLOAD {chunk_name}")
            tasks.append((target_server, part_num, chunk_name, chunk_bytes))

        # ETAPA 1: Cálculo Distribuído do SHA-256 nos Workers de cada Servidor Central em paralelo
        hash_results = {}
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_part = {
                executor.submit(
                    self.grpc_client.compute_chunk_hash,
                    target_server,
                    part_num,
                    chunk_name,
                    chunk_bytes
                ): part_num
                for target_server, part_num, chunk_name, chunk_bytes in tasks
            }
            for future in futures.as_completed(future_to_part):
                res = future.result()
                hash_results[res["part_number"]] = res

        part1_hash = hash_results[1]["chunk_sha256"]
        part2_hash = hash_results[2]["chunk_sha256"]

        # ETAPA 2: Soma dos Hashes (Hash Composto da Parte 1 + Parte 2)
        combined_raw = f"{part1_hash}:{part2_hash}".encode("utf-8")
        combined_file_sha256 = hashlib.sha256(combined_raw).hexdigest()

        logger.info(
            f"🔗 [Soma SHA-256] Hash Parte 1 ({hash_results[1]['calculated_by_server']}): {part1_hash[:12]}... + "
            f"Hash Parte 2 ({hash_results[2]['calculated_by_server']}): {part2_hash[:12]}... "
            f"=> Hash Composto Final: {combined_file_sha256[:16]}..."
        )

        # ETAPA 3: Validação de Duplicidade na Região Crítica (Token Ring), Gravação e Replicação
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
                    client_id,
                    hash_results[part_num]["chunk_sha256"],
                    combined_file_sha256
                ): part_num
                for target_server, part_num, chunk_name, chunk_bytes in tasks
            }
            for future in futures.as_completed(future_to_part):
                chunk_results.append(future.result())

        chunk_results.sort(key=lambda x: x["part_number"])

        # Adiciona metadados de qual worker thread calculou o hash de cada metade
        for c in chunk_results:
            p = c["part_number"]
            c["hash_worker_info"] = f"{hash_results[p]['calculated_by_server']} ({hash_results[p]['worker_thread']})"

        # Verifica se os Servidores Centrais detectaram duplicidade pela soma dos hashes SHA-256
        duplicate_detected = any(c["is_duplicate"] for c in chunk_results)
        if duplicate_detected:
            dup_of = next((c["duplicate_of_filename"] for c in chunk_results if c["duplicate_of_filename"]), "existente")
            return {
                "success": False,
                "is_duplicate": True,
                "duplicate_of_filename": dup_of,
                "filename": filename,
                "original_size": original_size,
                "total_parts": 2,
                "uploaded_by": client_id,
                "combined_file_sha256": combined_file_sha256,
                "message": (
                    f"🚫 Upload bloqueado por Duplicidade (SHA-256)! A soma das 2 metades deste arquivo "
                    f"é 100% idêntica ao arquivo '{dup_of}' já salvo nos servidores."
                ),
                "chunks": chunk_results
            }

        return {
            "success": True,
            "is_duplicate": False,
            "duplicate_of_filename": None,
            "filename": filename,
            "original_size": original_size,
            "total_parts": 2,
            "uploaded_by": client_id,
            "combined_file_sha256": combined_file_sha256,
            "message": (
                "Arquivo validado via Soma SHA-256 nos Workers (não duplicado), dividido ao meio, "
                "salvo nos 2 Servidores Centrais com Token Ring e replicado no Server-Backup!"
            ),
            "chunks": chunk_results
        }

    def _query_file_map_with_failover(self, filename: str) -> dict:
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
            except Exception:
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
