import threading
import logging
from typing import List
from src.config.settings import Config

logger = logging.getLogger("LoadBalancer")

class RoundRobinLoadBalancer:
    # Balanceador de carga Round-Robin
    def __init__(self, servers: List[str] = None):
        self.servers = servers or Config.CENTRAL_SERVERS
        self._current_index = 0
        self._total_requests = 0
        self._lock = threading.Lock()

    def get_next_server(self, operation: str) -> str:
        with self._lock:
            target = self.servers[self._current_index]
            self._total_requests += 1
            req_num = self._total_requests
            self._current_index = (self._current_index + 1) % len(self.servers)

        logger.info(
            f"[LoadBalancer] Requisicao #{req_num} ({operation}) -> [{target}]"
        )
        return target
