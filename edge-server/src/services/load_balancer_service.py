import threading
import logging
from typing import List
from src.config.settings import Config

logger = logging.getLogger("LoadBalancer")

class RoundRobinLoadBalancer:
    """
    Camada de Serviço (Balanceamento de Carga):
    Implementa o algoritmo Round-Robin de forma Thread-Safe (com Lock)
    para distribuir uniformemente as requisições entre os Servidores Centrais.
    """
    def __init__(self, servers: List[str] = None):
        self.servers = servers or Config.CENTRAL_SERVERS
        self._current_index = 0
        self._total_requests = 0
        self._lock = threading.Lock()

    def get_next_server(self, operation: str) -> str:
        """Retorna o próximo Servidor Central na fila circular (Round-Robin)."""
        with self._lock:
            target = self.servers[self._current_index]
            self._total_requests += 1
            req_num = self._total_requests
            self._current_index = (self._current_index + 1) % len(self.servers)

        logger.info(
            f"⚖️ [LoadBalancer] Requisição #{req_num} ({operation}) -> Roteada para [{target}]"
        )
        return target
