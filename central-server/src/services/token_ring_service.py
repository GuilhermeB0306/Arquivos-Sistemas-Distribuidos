import time
import threading
import logging
import grpc
from src.config.settings import Config
import storage_pb2
import storage_pb2_grpc

logger = logging.getLogger("TokenRing")

class TokenRingService:
    # Controle do Token Ring para exclusao mutua na escrita
    def __init__(self):
        self.server_id = Config.SERVER_ID
        self.next_node = Config.NEXT_NODE_ADDRESS
        self.has_token = False
        self.token_sequence = 0
        self.in_critical_section = False
        self.waiting_writers = 0

        self.condition = threading.Condition()

    def start_background_worker(self):
        worker_thread = threading.Thread(target=self._token_circulation_loop, daemon=True)
        worker_thread.start()

        if Config.INITIAL_TOKEN_HOLDER:
            logger.info(f"[{self.server_id}] Inicia com o TOKEN. Aguardando servidores...")
            time.sleep(4)
            self.receive_token(sequence_number=1, from_server="BOOTSTRAP")

    def receive_token(self, sequence_number: int, from_server: str):
        with self.condition:
            self.has_token = True
            self.token_sequence = sequence_number
            if self.waiting_writers > 0:
                logger.info(
                    f"[{self.server_id}] TOKEN #{sequence_number} recebido de {from_server}. "
                    f"Escritas na fila: {self.waiting_writers}"
                )
            else:
                logger.info(f"[{self.server_id}] TOKEN #{sequence_number} recebido de {from_server} (fila vazia)")
            self.condition.notify_all()

    def enter_critical_section(self, operation_desc: str):
        with self.condition:
            self.waiting_writers += 1
            logger.info(f"[{self.server_id}] Pedido de escrita ({operation_desc}). Aguardando TOKEN...")
            while not self.has_token or self.in_critical_section:
                self.condition.wait()

            self.waiting_writers -= 1
            self.in_critical_section = True
            logger.info(f"[{self.server_id}] Entrou na regiao critica ({operation_desc}) com TOKEN #{self.token_sequence}")

    def exit_critical_section(self, operation_desc: str):
        with self.condition:
            self.in_critical_section = False
            logger.info(f"[{self.server_id}] Saiu da regiao critica ({operation_desc})")
            self.condition.notify_all()

    def _token_circulation_loop(self):
        while True:
            should_pass = False
            seq_to_pass = 0

            with self.condition:
                if self.has_token and not self.in_critical_section and self.waiting_writers == 0:
                    should_pass = True
                    seq_to_pass = self.token_sequence + 1

            if should_pass:
                time.sleep(Config.TOKEN_HOLD_TIME_SEC)

                with self.condition:
                    if self.has_token and not self.in_critical_section and self.waiting_writers == 0:
                        if self._send_token_to_next_node(seq_to_pass):
                            self.has_token = False
                        else:
                            self.condition.notify_all()
                    else:
                        continue
            else:
                time.sleep(0.2)

    def _send_token_to_next_node(self, next_seq: int) -> bool:
        try:
            with grpc.insecure_channel(self.next_node) as channel:
                stub = storage_pb2_grpc.TokenRingServiceStub(channel)
                response = stub.PassToken(
                    storage_pb2.TokenMessage(
                        sequence_number=next_seq,
                        from_server=self.server_id
                    ),
                    timeout=2.5
                )
                return response.received
        except grpc.RpcError:
            logger.warning(
                f"[{self.server_id}] Vizinho ({self.next_node}) offline. Mantendo TOKEN localmente..."
            )
            time.sleep(1.5)
            return False
