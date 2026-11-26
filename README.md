# Sistema Distribuido de Armazenamento de Exames e Laudos Hospitalares

Projeto desenvolvido para a disciplina de **Desenvolvimento de Sistemas de Informacao Distribuidos** (UFMT - Instituto de Computacao).

## Integrantes
- Dirceu Joao de Souza Moraes
- Guilherme Borges dos Santos
- Guimel de Alencar Santana
- Josue de Oliveira da Silva Jorge

---

## Sobre o Projeto

O sistema simula uma infraestrutura distribuida para armazenamento seguro e tolerante a falhas de exames e laudos hospitalares. A arquitetura utiliza **4 containers Docker** que se comunicam via **REST** (camada externa) e **gRPC com Protocol Buffers** (rede interna).

### Principais Tecnicas Utilizadas
1. **Autenticacao Stateless (JWT):** O servidor de borda autentica usuarios via token JWT sem armazenar sessao em memoria.
2. **Fatiamento de Arquivos (File Sharding):** Cada arquivo enviado no upload e dividido exatamente ao meio (`part1` e `part2`). Cada metade e armazenada em um servidor central diferente, distribuindo o volume de dados e garantindo privacidade (nenhum servidor central possui o documento completo sozinho).
3. **Balanceamento de Carga (Round-Robin):** O servidor de borda distribui as requisicoes circularmente entre `central-1` e `central-2`.
4. **Validacao de Duplicidade via Soma SHA-256 nos Workers:** Antes de gravar, worker threads de cada servidor central calculam o hash SHA-256 da sua respectiva metade. O sistema verifica a soma dos dois hashes (`combined_file_sha256`) no banco para bloquear arquivos duplicados sem gerar falso positivo caso apenas 50% do arquivo seja parecido.
5. **Exclusao Mutua Distribuida (Token Ring):** Os servidores `central-1` e `central-2` passam um Token continuamente em anel via gRPC. Um servidor so pode gravar sua fatia, atualizar o banco SQLite de metadados (Regiao Critica) e replicar para o backup quando estiver com o Token. Operacoes de leitura (download e listagem) sao livres de Token.
6. **Redundancia e Tolerancia a Falhas (Failover):** Toda fatia gravada pelos servidores centrais e replicada via gRPC para o `server-backup`. Se `central-1` ou `central-2` cair, o servidor de borda busca automaticamente a metade faltante no `server-backup` durante o download.

---

## Arquitetura dos Containers

| Container | Porta | Tecnologia | Funcao |
| :--- | :--- | :--- | :--- |
| `edge-server` | `8080` (REST) | FastAPI + Swagger + gRPC Client | Gateway REST, Auth JWT, Fatiamento (50%/50%), Load Balancer Round-Robin e Failover. |
| `central-1` | `50051` (gRPC) | Python gRPC + Threading + SQLite | Servidor Central 1 (Pool de 10 Worker Threads + 1 Thread do Token Ring). |
| `central-2` | `50052` (gRPC) | Python gRPC + Threading + SQLite | Servidor Central 2 (Pool de 10 Worker Threads + 1 Thread do Token Ring). |
| `server-backup` | `50053` (gRPC) | Python gRPC | Servidor de redundancia que guarda copias das partes 1 e 2 para Failover. |

---

## Estrutura de Pastas

```text
.
├── docker-compose.yml
├── relatorio.tex
├── storage_data/                # Volume mapeado com as fatias salvas e banco SQLite
│   ├── central-1/               # Guarda metade 1 dos arquivos (.part1)
│   ├── central-2/               # Guarda metade 2 dos arquivos (.part2)
│   ├── server-backup/           # Guarda copias redundantes (.part1 e .part2)
│   ├── metadata_chunks.db       # Banco SQLite (Mapa de ponteiros dos chunks)
│   └── catalog.json             # Espelho em JSON do banco SQLite
├── edge-server/                 # Servidor de Borda (FastAPI + Load Balancer + gRPC Client)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── proto/storage.proto
│   └── src/
│       ├── config/
│       ├── schemas/
│       ├── routes/
│       ├── controllers/
│       ├── services/
│       ├── infrastructure/
│       └── main.py
├── central-server/              # Servidores Centrais 1 e 2 (gRPC + Workers SHA-256 + Token Ring)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── proto/storage.proto
│   └── src/
│       ├── config/
│       ├── domain/
│       ├── controllers/
│       ├── services/
│       ├── infrastructure/
│       └── main.py
└── server-backup/               # Servidor de Redundancia / Backup (gRPC)
    ├── Dockerfile
    ├── requirements.txt
    ├── proto/storage.proto
    └── src/
        ├── config/
        ├── domain/
        ├── controllers/
        ├── services/
        ├── infrastructure/
        └── main.py
```

---

## Como Executar

1. Certifique-se de que o **Docker Desktop** esta aberto e em execucao.
2. No terminal, na pasta raiz do projeto, execute:

```bash
docker compose up --build
```

3. Acesse o **Swagger UI** no navegador:
   - [http://localhost:8080/docs](http://localhost:8080/docs)

---

## Roteiro Rapido de Teste (Apresentacao)

1. **Gerar Token JWT:**
   - No Swagger, abra a rota `POST /api/auth/login`, clique em **Try it out** e **Execute**.
   - Copie o valor do `access_token` retornado.
   - Clique no botao **Authorize** (cadeado no topo da pagina), cole o token e confirme.

2. **Fazer Upload de Arquivo (Fatiamento + Token Ring + Backup):**
   - Na rota `POST /api/upload`, selecione um arquivo (ex: um PDF de laudo/exame) e clique em **Execute**.
   - Verifique na pasta `storage_data/` que o arquivo foi dividido em `central-1/` e `central-2/`, replicado em `server-backup/` e registrado em `catalog.json`.

3. **Testar Bloqueio de Duplicidade (Soma SHA-256):**
   - Tente enviar o mesmo arquivo novamente na rota `POST /api/upload`.
   - O sistema retornara status `409 Conflict` informando que a soma dos hashes SHA-256 das duas partes ja existe no banco.

4. **Testar Tolerancia a Falhas (Failover):**
   - Em outro terminal, desligue um dos servidores centrais:
     ```bash
     docker stop central-2
     ```
   - No Swagger, va na rota `GET /api/download/{filename}`, informe o nome do arquivo enviado e faca o download.
   - O `edge-server` detectara que o `central-2` esta offline, buscara a parte faltante automaticamente no `server-backup` e entregara o arquivo completo sem perda de dados.
   - Para religar o servidor:
     ```bash
     docker start central-2
     ```
