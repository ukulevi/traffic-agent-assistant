# Harness Open Source cho mÃ´i trÆ°á»ng local

Cáº¥u hÃ¬nh nÃ y cháº¡y image chÃ­nh thá»©c cá»§a [Harness Open Source](https://github.com/harness/harness) tÃ¡ch biá»‡t vá»›i runtime STWI. Database vÃ  repository Ä‘Æ°á»£c giá»¯ trong cÃ¡c Docker named volume `stwi-harness-data` vÃ  `stwi-harness-git`. Cáº¥u hÃ¬nh máº·c Ä‘á»‹nh khÃ´ng cáº¥p quyá»n truy cáº­p Docker daemon cho Harness.

## Phase 3 integration services

`compose.phase3.yaml` chá»‰ dÃ nh cho integration test Qdrant/TimescaleDB trÃªn mÃ¡y
phÃ¡t triá»ƒn. NÃ³ bind service vÃ o loopback máº·c Ä‘á»‹nh, yÃªu cáº§u password/API key tá»«
private env file vÃ  khÃ´ng cÃ³ development password. Sao chÃ©p
`.env.phase3.example` thÃ nh má»™t tá»‡p private (khÃ´ng commit), thay toÃ n bá»™ giÃ¡ trá»‹
máº«u, rá»“i cháº¡y:

```powershell
docker compose --env-file <private-env-file> -f infra/harness/compose.phase3.yaml up -d
```

Sau khi service health, export `STWI_QDRANT_URL`, `STWI_QDRANT_API_KEY` vÃ 
`STWI_TSDB_DSN` tá»« cÃ¹ng private env file trÆ°á»›c khi cháº¡y test integration. ÄÃ¢y
khÃ´ng pháº£i cáº¥u hÃ¬nh production; khÃ´ng má»Ÿ bind address ra ngoÃ i loopback hoáº·c
Ä‘Æ°a secret vÃ o Git.

Äá»ƒ cháº¡y má»™t lÆ°á»£t kiá»ƒm thá»­ local khÃ´ng lÆ°u secret ra Ä‘Ä©a, dÃ¹ng runner sau. NÃ³
táº¡o credential ngáº«u nhiÃªn trong process, Ä‘á»£i cáº£ hai service healthy, cháº¡y test
real-adapter vÃ  máº·c Ä‘á»‹nh `down -v` trong `finally` ká»ƒ cáº£ khi test lá»—i:

```powershell
powershell -File scripts/infra/run_phase3_integration_harness.ps1 `
  -PythonPath <path-to-project-python>
```

Chá»‰ dÃ¹ng `-KeepServices` khi cáº§n debug cÃ³ chá»§ Ä‘Ã­ch; sau Ä‘Ã³ pháº£i tá»± cháº¡y
`docker compose -f infra/harness/compose.phase3.yaml down -v`.

## YÃªu cáº§u

- Docker Desktop Ä‘ang cháº¡y vá»›i Linux containers.
- Hai cá»•ng `3000` vÃ  `3022` Ä‘ang trá»‘ng. Náº¿u bá»‹ trÃ¹ng, sao chÃ©p `.env.example` thÃ nh `.env` vÃ  Ä‘á»•i cá»•ng host.

## Khá»Ÿi Ä‘á»™ng

Tá»« thÆ° má»¥c repository:

```powershell
docker compose --env-file infra/harness/.env.example -f infra/harness/compose.yaml up -d
docker compose -f infra/harness/compose.yaml ps
```

Má»Ÿ <http://localhost:3000>. TÃ i khoáº£n khá»Ÿi táº¡o máº·c Ä‘á»‹nh theo upstream lÃ  `admin` / `changeit`; hÃ£y Ä‘á»•i máº­t kháº©u ngay sau láº§n Ä‘Äƒng nháº­p Ä‘áº§u tiÃªn.

Náº¿u Ä‘Ã£ táº¡o `infra/harness/.env`, dÃ¹ng lá»‡nh sau thay cho lá»‡nh khá»Ÿi Ä‘á»™ng á»Ÿ trÃªn:

```powershell
docker compose --env-file infra/harness/.env -f infra/harness/compose.yaml up -d
```

## Váº­n hÃ nh

Xem log:

```powershell
docker compose -f infra/harness/compose.yaml logs -f harness
```

Dá»«ng dá»‹ch vá»¥ nhÆ°ng giá»¯ dá»¯ liá»‡u:

```powershell
docker compose -f infra/harness/compose.yaml down
```

## Báº­t pipeline vÃ  Gitspace dÃ¹ng Docker

Cháº¿ Ä‘á»™ máº·c Ä‘á»‹nh phÃ¹ há»£p Ä‘á»ƒ dÃ¹ng UI, code hosting vÃ  artifact registry. Pipeline hoáº·c Gitspace cáº§n táº¡o container pháº£i cÃ³ quyá»n truy cáº­p Docker daemon. Chá»‰ báº­t sau khi Ä‘Ã£ cháº¥p nháº­n rá»§i ro quáº£n trá»‹ host:

```powershell
docker compose `
  -f infra/harness/compose.yaml `
  -f infra/harness/compose.docker-access.yaml `
  up -d
```

NÃ¢ng cáº¥p cÃ³ chá»§ Ä‘Ã­ch báº±ng cÃ¡ch láº¥y digest má»›i cá»§a `harness/harness`, cáº­p nháº­t trÆ°á»ng `image`, rá»“i cháº¡y láº¡i `docker compose up -d`. KhÃ´ng dÃ¹ng `down --volumes` náº¿u chÆ°a chá»§ Ä‘á»™ng muá»‘n xÃ³a toÃ n bá»™ repository, pipeline vÃ  cáº¥u hÃ¬nh trong Harness.

## LÆ°u Ã½ an toÃ n

Override `compose.docker-access.yaml` mount Docker socket Ä‘á»ƒ cháº¡y pipeline vÃ  Gitspace. Quyá»n nÃ y cho container Ä‘iá»u khiá»ƒn Docker daemon, tÆ°Æ¡ng Ä‘Æ°Æ¡ng quyá»n quáº£n trá»‹ host trong thá»±c táº¿. Chá»‰ báº­t override khi tháº­t sá»± cáº§n, chá»‰ cháº¡y image Ä‘Ã£ pin, khÃ´ng cháº¡y pipeline khÃ´ng tin cáº­y vÃ  khÃ´ng Ä‘Æ°a secret STWI vÃ o repository/pipeline náº¿u chÆ°a cáº¥u hÃ¬nh secret management phÃ¹ há»£p.

Harness lÃ  cÃ´ng cá»¥ DevOps local, khÃ´ng pháº£i thÃ nh pháº§n runtime cá»§a STWI vÃ  khÃ´ng thay Ä‘á»•i `project_contract.json`.

## KhÃ´ng cháº¡y Roboflow Inference Server local

**Äá»«ng** cháº¡y `roboflow/roboflow-inference-server-gpu` hoáº·c `roboflow/roboflow-inference-server-cpu` trong Docker. Image nÃ y ngá»‘n ~2.7 GB RAM khi idle vÃ  khÃ´ng Ä‘Æ°á»£c dÃ¹ng bá»Ÿi báº¥t ká»³ thÃ nh pháº§n runtime nÃ o cá»§a STWI.

STWI gá»i tháº³ng **Roboflow Cloud API** (`https://serverless.roboflow.com`) qua `inference-sdk` â€” khÃ´ng cáº§n server local. MCP server (`scripts/infra/roboflow_mcp_server.py`) lÃ  má»™t tiáº¿n trÃ¬nh stdio nháº¹, cháº¡y trá»±c tiáº¿p báº±ng Python, khÃ´ng cáº§n Docker.
