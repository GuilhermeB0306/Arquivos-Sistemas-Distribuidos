import time
import threading
import logging
import grpc
from src.config.settings import Config
import storage_pb2
import storage_pb2_grpc

logger = logging.getLogger("TokenRing")

class TokenRingService:
    """
    Camada de Serviço: Gerencia o algoritmo de Exclusão Mútua Distribuída (Token Ring).
    Controla uma Thread dedicada em background para circular o Token e sincroniza
    as Threads trabalhadoras que precisam entrar na Região Crítica (Upload/Escrita).
    """
    def __init__(self):
        self.server_id = Config.SERVER_ID
        self.next_node = Config.NEXT_NODE_ADDRESS
        self.has_token = False
        self.token_sequence = 0
        self.in_critical_section = False
        self.waiting_writers = 0

        # Condição para sincronizar as threads de upload com a chegada do Token
        self.condition = threading.Condition()

    def start_background_worker(self):
        """Inicia a Thread do Token Ring."""
        worker_thread = threading.Thread(target=self._token_circulation_loop, daemon=True)
        worker_thread.start()

        if Config.INITIAL_TOKEN_HOLDER:
            logger.info(f"[{self.server_id}] Configurado como detentor inicial do TOKEN. Aguardando anel subir...")
            time.sleep(4)
            self.receive_token(sequence_number=1, from_server="BOOTSTRAP")

    def receive_token(self, sequence_number: int, from_server: str):
        """Chamado quando o Token chega via gRPC do servidor vizinho."""
        with self.condition:
            self.has_token = True
            self.token_sequence = sequence_number
            if self.waiting_writers > 0:
                logger.info(
                    f"🟢 [{self.server_id}] TOKEN #{sequence_number} recebido de {from_server}! "
                    f"Há {self.waiting_writers} escrita(s) aguardando na fila!"
                )
            else:
                logger.info(f"🔄 [{self.server_id}] TOKEN #{sequence_number} recebido de {from_server} (fila vazia).")
            # Acorda as threads que estão aguardando o Token para gravar arquivos
            self.condition.notify_all()

    def enter_critical_section(self, operation_desc: str):
        """
        Bloqueia a thread de Upload até que este servidor possua o Token
        e nenhuma outra thread local esteja na Região Crítica.
        """
        with self.condition:
            self.waiting_writers += 1
            logger.info(f"⏳ [{self.server_id}] Pedido de escrita ({operation_desc}). Aguardando TOKEN...")
            while not self.has_token or self.in_critical_section:
                self.condition.wait()

            self.waiting_writers -= 1
            self.in_critical_section = True
            logger.info(f"🔒 [{self.server_id}] ENTROU NA REGIÃO CRÍTICA ({operation_desc}) com TOKEN #{self.token_sequence}")

    def exit_critical_section(self, operation_desc: str):
        """Libera a Região Crítica após concluir a escrita."""
        with self.condition:
            self.in_critical_section = False
            logger.info(f"🔓 [{self.server_id}] SAIU DA REGIÃO CRÍTICA ({operation_desc})")
            self.condition.notify_all()

    def _token_circulation_loop(self):
        """
        Thread que monitora a posse do Token.
        Quando não há mais escritas locais pendentes ou em andamento, repassa o Token ao próximo nó do anel.
        """
        while True:
            should_pass = False
            seq_to_pass = 0

            with self.condition:
                if self.has_token and not self.in_critical_section and self.waiting_writers == 0:
                    should_pass = True
                    seq_to_pass = self.token_sequence + 1

            if should_pass:
                # Segura brevemente o token quando ocioso para os logs ficarem legíveis na apresentação
                time.sleep(Config.TOKEN_HOLD_TIME_SEC)

                with self.condition:
                    # Verifica novamente após o sleep se alguma thread pediu escrita nesse meio tempo
                    if self.has_token and not self.in_critical_section and self.waiting_writers == 0:
                        if self._send_token_to_next_node(seq_to_pass):
                            self.has_token = False
                    else:
                        continue
            else:
                time.sleep(0.2)

    def _send_token_to_next_node(self, next_seq: int) -> bool:
        """Faz a chamada gRPC PassToken() para o próximo Servidor Central do anel."""
        try:
            with grpc.insecure_channel(self.next_node) as channel:
                stub = storage_pb2_grpc.TokenRingServiceStub(channel)
                response = stub.PassToken(
                    storage_pb2.TokenMessage(
                        sequence_number=next_seq,
                        from_server=self.server_id
                    ),
                    timeout=3.0
                )
                return response.received
        except grpc.RpcError as e:
            logger.warning(f"⚠️ [{self.server_id}] Vizinho ({self.next_node}) ainda indisponível para receber Token. Tentando novamente...")
            time.sleep(1.5)
            return False
