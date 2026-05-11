# Brands AI — Documentação completa da arquitetura (estado atual)

Este documento descreve **tudo o que está implementado e configurado** na aplicação **brands-ai** (Confeções Lança): tecnologias, dados, pipelines de IA, pesquisas na web, filtros, queries SQL, APIs, frontend, CI/CD e variáveis de ambiente. Foco especial no fluxo **desde a cidade introduzida até à escolha e persistência dos melhores clientes/prospects**.

---

## 1. Visão geral do produto

**Objetivo:** apoiar a equipa comercial da Lança a descobrir **marcas de retalho masculino** (boutiques, independentes, médio-alto) numa **cidade** dada, qualificá-las com regras de negócio e perfil dos clientes actuais, **persistir** resultados em PostgreSQL com **scores**, e permitir **consulta conversacional** (chat) e **gestão** (filtros, feedback, email).

**Componentes principais:**

| Camada | Tecnologia | Função |
|--------|------------|--------|
| Frontend | Next.js (App Router), React, Tailwind, NextAuth (Azure AD) | UI: pesquisa por cidade, cidades guardadas, clientes Lança, chat |
| Backend | FastAPI (Python 3.11), Gunicorn+Uvicorn | API REST + SSE para pipeline de prospecção |
| Orquestração IA | LangGraph + checkpointer PostgreSQL | Grafo: initialize → discovery → validation → persistence |
| Dados | PostgreSQL + extensão **pgvector** | Prospects, clientes Lança embeddados, feedback, supressão, checkpoints |
| Pesquisa web | **Exa** (`exa-py`) | 3 queries × 30 resultados cada (~90 URLs brutas antes de dedup) |
| LLMs | **Azure OpenAI** (deployment “rápido” vs “profundo”) | Triagem, análise profunda, chat, embeddings |
| Enriquecimento | **Google Places API** | Moradas, telefone, contagem de lojas quando aplicável |
| Scraping selectivo | **Crawl4AI** (self-hosted, configurável) ou legado Firecrawl+Jina | Top ~15 marcas após análise LLM — emails, imagens, LinkedIn |
| Email | Resend (+ rascunho mailto) | Envio / geração de propostas |
| WhatsApp (opcional) | Twilio webhook | Mesma lógica RAG que o chat, com sessão por número |

---

## 2. Estrutura de repositório (o que existe no código)

```
brands-ai/
├── backend/                 # API FastAPI + agentes
│   ├── main.py              # App, CORS, lifespan (init DB, fechar pool)
│   ├── config.py            # Variáveis de ambiente + perfil ideal Lança + lista CURRENT_CLIENTS (marketing)
│   ├── models.py            # Pydantic: BrandLead, ProspectorState, filtros, SearchRequest, etc.
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── migrations/          # SQL: prospects, lanca_clients, feedback, colunas extra
│   ├── routers/             # workflow, prospects, cities, analytics, email, export, chat, whatsapp
│   ├── agents/
│   │   ├── graph.py         # LangGraph + AsyncPostgresSaver
│   │   └── nodes/           # initializer, discovery, validator, persistence, utils
│   ├── services/            # database, postgres, vector_db, workflow_service, scrapers, contact_finder, etc.
│   └── data/                # lanca_clients (18 parceiros para embeddings), multilingual_keywords, premium_locations
├── frontend/                # Next.js
│   ├── app/                 # page (home), saved-cities, chat, clients, api/auth/[...nextauth]
│   ├── components/          # BrandCard, FilterPanel, Sidebar, UI
│   └── middleware.ts        # NextAuth — protege rotas excepto auth e estáticos
├── docker-compose.yml       # PostgreSQL pgvector + Crawl4AI + API
└── .github/workflows/       # Deploy backend Azure + frontend Azure Static Web Apps
```

---

## 3. Fluxo extremo-a-extremo: da cidade à resposta final

### 3.1 Pesquisa na página inicial (`/`)

1. O utilizador escreve uma **cidade** (ex.: `Milano`) e opcionalmente activa **“Forçar nova pesquisa”** (`force_refresh`).
2. O browser faz `POST {NEXT_PUBLIC_API_URL}/api/prospect` com JSON: `{ "city": "<cidade>", "force_refresh": true|false }`.
3. A resposta é **Server-Sent Events (SSE)**: eventos `progress`, `heartbeat` (manter vivo o socket no Azure ~25s), `complete`, `error`, e em fluxos HITL `waiting_approval` (código de resume existe; o grafo actual vai até `END` sem interrupção obrigatória).

### 3.2 Camada de cache no `workflow_service` (antes do LangGraph)

Ficheiro: `backend/services/workflow_service.py`.

- Se **`force_refresh` é falso** e `city_has_results(city)` é verdadeiro (**SQL:** `COUNT(*) FROM prospects WHERE city = normalized_city` > 0):
  - **Não corre** o grafo LangGraph.
  - Devolve imediatamente `complete` com até **50** prospects via `get_prospects_by_city(city, limit=50)`.
- Se há cache miss ou `force_refresh`:
  - Compila/usa o grafo com `thread_id = prospect_search_{city}` ou, com refresh forçado, `prospect_search_{city}_{timestamp}` para não colidir com checkpoints antigos.
  - Faz stream de `progress` a partir dos `progress` do estado do grafo.

**Nota importante:** o nó `initialize_search` tem **outra** regra de cache interna: se já existem **≥ 25** prospects para a cidade e **`force_refresh` é falso**, o grafo **encerra cedo** sem discovery (mas isto só se aplica quando o grafo **é** invocado — a camada SSE acima pode já ter devolvido dados com só 1 prospect na cidade).

### 3.3 LangGraph — nós e arestas

Ficheiro: `backend/agents/graph.py`.

**Estado (`GraphState`):** `target_city`, `target_country`, `search_queries`, `query_origins`, `candidate_urls`, `potential_brands`, `verified_brands`, `search_results`, `progress`, `exchange_rate`, `price_threshold_eur` / `price_threshold_usd`, `max_stores`, `error`, `cached`, `cached_count`, `queries_approved`, `brands_approved`, `force_refresh`.

**Fluxo:**

1. **initialize** (`initialize_search`)
2. Aresta condicional: se `cached == True` → **END**; senão → **discovery**
3. **discovery** → **validation** → **persistence** → **END**

**Checkpointer:** `AsyncPostgresSaver` sobre pool `psycopg` (mesma `SYNC_DATABASE_URL` que o resto da app), com `thread_id` estável por cidade.

---

## 4. Nó 1 — Initialize (`backend/agents/nodes/initializer.py`)

### 4.1 Inferência de país

- Se `target_country` vem vazio ou `"USA"`, chama **`infer_country(city)`**: LLM rápido (`get_llm(fast=True)`) — “Given the city X, what country?” — para preencher o país (usado depois no Google Places).

### 4.2 Cache interno do grafo (≥ 25 prospects)

- `get_prospects_by_city(target_city, limit=100)` — se contagem ≥ **25** e **não** `force_refresh`:
  - Retorna `cached: True`, `search_queries: []`, progresso a indicar dados em cache (sem custo Exa/LLM pesado neste ramo).

### 4.3 Limiares de preço

- Taxa de câmbio **fixa** 1.08 em `get_exchange_rate()` (EUR→USD).
- `price_threshold_eur` default **500** no `ProspectorState` → converte para USD no estado.

### 4.4 Geração de **queries de pesquisa** (Exa)

Função **`select_queries(city)`** — estado actual do código:

| # | Origem (`query_origin`) | Template exacto (inglês; `{city}` substituído) |
|---|-------------------------|-----------------------------------------------|
| 1 | `GoldenProfile` | `menswear brand similar to Hawes Curtis independent tailored suits boutique {city}` |
| 2 | `LocalDiscovery` | `independent menswear boutique premium suits {city}` |
| 3 | `NicheTailoring` | `tailored suits ready to wear brand boutique {city}` |

**Total: 3 queries por execução completa do nó initialize** (quando não há cache de grafo).

**Código auxiliar presente mas não ligado ao pipeline actual:** `generate_local_queries(city)` gera 3 queries na língua local via LLM para cidades não inglesas; **`select_queries` não a invoca** — portanto, neste momento, **todas as cidades usam só as 3 frases em inglês acima**. `is_english_city` / listas `ENGLISH_CITIES` aplicam-se apenas se `generate_local_queries` for usado no futuro.

---

## 5. Nó 2 — Discovery (`backend/agents/nodes/discovery.py`)

### 5.1 API e parâmetros Exa

- Cliente: `Exa(api_key=os.environ.get("EXA_API_KEY"))`.
- Por cada uma das **3** strings de `search_queries`:
  - `exa.search(query, num_results=30, type="auto", exclude_domains=[...], contents={"text": {"maxCharacters": 10000}, "highlights": True})`

**Contagem nominal:** 3 × 30 = **até 90** resultados brutos (menos se a API devolver menos).

### 5.2 Domínios excluídos (lista fixa)

Inclui marketplaces, redes sociais, directórios, Google Maps, Wikipedia, revistas (GQ, Esquire), etc. — ver array `exclude_domains` no ficheiro.

### 5.3 Deduplicação

- Junta todos os resultados; **`deduplicate_by_domain`** mantém o primeiro URL por **domínio raiz** (sem `www`).

### 5.4 Saída

- `candidate_urls`: lista de URLs únicos.
- `search_results`: lista de `QuerySearchResults` (query, origem, lista de `{url, title, content/highlights, text, query_origin}`).

---

## 6. Nó 3 — Validation (`backend/agents/nodes/validator.py`)

Concorrência global: `asyncio.Semaphore(3)` — no máximo **3** validações de cidade em paralelo a nível de nó.

### Fase 0 — Agregação de URLs e exclusões “grátis”

Para cada URL nos resultados Exa (por domínio único):

1. **Excluir clientes Lança actuais:** domínios e nomes vindos de `data/lanca_clients.LANCA_CLIENTS` (evita prospeccionar parceiros existentes).
2. **`is_known_chain(url, title)`** — `multilingual_keywords` / listas de cadeias conhecidas.
3. **`is_domain_suppressed(domain)`** — `SELECT 1 FROM suppression_list WHERE domain = $1`.
4. **Blogs / media / marketplaces:** `is_blog_or_media(url)` — padrões de path e conjunto `MEDIA_DOMAINS`.

Depois: **cap opcional a 200 URLs**, ordenando por um mapa fictício `ORIGIN_PRIORITY` — **atenção:** as origens reais do Exa são `GoldenProfile`, `LocalDiscovery`, `NicheTailoring`; muitas chaves do mapa (B2B, Trade, etc.) **não coincidem**, pelo que na prática a ordenação pode degradar para prioridade “Unknown” igual para todos.

### Fase 0b — Texto Exa para triagem (sem scraping completo)

- Constrói `exa_text_map`: por URL normalizado, o maior `text` Exa ≥ **500** caracteres.
- `ExtractedContent` por candidato: ou texto Exa (até 15k) ou vazio.

### Keyword scoring multi-idioma

- `detect_language` — heurística por palavras comuns (it/fr/de/es/pt).
- `calculate_keyword_score` — `data/multilingual_keywords.py` (centenas de termos positivos/negativos e pesos).
- Mantém apenas conteúdos com **`quality_score` ≥ 1**.

### Enriquecimento de preços no texto

- `enrich_content_with_prices` sobre os conteúdos escorados.

### Similaridade vectorial rápida (pré-filtro)

- Para cada conteúdo: `find_similar_clients(content[:4000], n_results=1)` (embedding temporário vs tabela `lanca_clients`).

### Regras de exclusão / penalização antes da triagem LLM

- `is_appointment_only(content)` — palavras-chave “só com marcação” vs indicadores de loja online.
- `extract_price_from_content`: se preço alto confiança **> 0.75** e **< 250 €** → excluir; se **> 0.8** e **> 2500 €** → excluir.
- Se similaridade **< 40**, preço 0, e `quality_score` **< 3** → excluir.
- Ordenação por score composto (similaridade, keywords, preço visível, penalidade appointment-only).
- **Top 80** `ExtractedContent` passam à **Phase 1**.

### Phase 1 — Triagem rápida (LLM fast, **uma chamada por candidato**)

- `triage_candidate`: prompt com regras de segmento, **presença física em `{target_city}`**, preços visíveis, cadeia vs independente.
- Pós-processamento:
  - Se `city_match` falso → score cap **4**.
  - `appointment_only` → -2; `prices_visible` falso → -1.
  - Passa se `score >= 4` e `is_menswear` true.

*(A mensagem de progresso no código pode dizer “score ≥ 5”; o critério efectivo no código é **≥ 4**.)*

### Phase 1.5 — Google Places

- Para cada candidato que passou: `enrich_with_places(brand_guess, city, country)` com semáforo 5.
- Resultado guardado em `structured_data["places"]` no `ExtractedContent`.

### Phase 2 — Análise profunda (LLM “full”, **lotes de 3**)

- `deep_analyze_batch`: inclui `CONFECOS_LANCA_PROFILE` de `config.py` e exemplos `generate_rich_client_examples` a partir dos clientes Lança.
- Devolve JSON de marcas com preços, `fitScore`, moradas, contactos, etc.
- **Número de chamadas LLM “deep”:** aproximadamente **ceil(N_passou_triage / 3)** lotes (cada lote uma invocação).

### Phase 2b — Validação de presença na cidade (pós-LLM)

- Verifica `hasPhysicalPresence` / `hasHeadquarters`, `headquartersAddress`, `storeLocations`, ou evidência do nome da cidade no texto da triagem.

### Phase 2.5 — Scraping selectivo (top **15**)

- `batch_extract_content(scrape_urls)` — se `USE_CRAWL4AI=true`, usa Crawl4AI multi-página (`full_site_extraction_flow`); senão caminho Firecrawl+Jina (com circuit breaker Firecrawl).

### Phase 3 — Montagem `BrandLead`

- Deduplica por domínio e nome.
- `detect_premium_location` / `calculate_location_score` (`data/premium_locations.py`).
- Merge: dados LLM + Places + scrape (emails, LinkedIn, imagens).
- Ordenação final: `fit_score`, depois `quality_score`.
- Saída: **`potential_brands`** (lista `BrandLead`).

---

## 7. Nó 4 — Persistence (`backend/agents/nodes/persistence.py`)

- Para cada marca em `potential_brands`:
  - Se domínio já existir na cidade: tenta **enriquecer contactos** (`find_contacts_for_brand`) e `update_prospect_contact` se novos dados.
  - Senão: monta `prospect_dict`, corre **`calculate_prospect_score`** (vector_db), **`save_prospect`**.
- Progresso final com contagens guardadas / duplicados.

---

## 8. Scoring persistente (`backend/services/vector_db.py`)

Após extração, cada prospect recebe **`final_score` 0–100** com componentes:

| Componente | Peso no código | Origem |
|----------|----------------|--------|
| Preço | `calculate_price_score * 0.8` (até ~20) | Comparado com medianas dos 18 clientes |
| Dimensão (lojas) | `calculate_size_score * 0.75` (até ~15) | Ideal ~1–4 lojas |
| Lã | `calculate_wool_score * 0.67` (até ~10) | Bonus 100% lã |
| MTM | até 10 | Preferência MTM |
| Similaridade embedding | até 20 | vs `lanca_clients` |
| Mercado | até 10 | `MARKET_STRENGTH_STATIC` por `country_code` |
| Fit LLM | até 15 | `fit_score` do deep analysis /100 |

**Hard filters** (não eliminam gravação mas **capam** score a 40 se falharem):

- Preço conhecido **< 375 €**
- **> 30** lojas

**Embeddings clientes Lança:** tabela `lanca_clients`, dimensão **1536** (`text-embedding-3-small`). Query típica de similaridade:

```sql
SELECT *, 1 - (embedding <=> $1::vector) AS similarity_score
FROM lanca_clients
ORDER BY embedding <=> $1::vector
LIMIT $2;
```

`populate_clients_database()` preenche a partir de `LANCA_CLIENTS` em `data/lanca_clients.py`.

---

## 9. Inventário de queries SQL principais (`backend/services/database.py`)

| Função | Resumo SQL / comportamento |
|--------|----------------------------|
| `get_prospects_by_city` | `SELECT DISTINCT ON (domain) * FROM prospects WHERE city = $1 ORDER BY domain, final_score DESC LIMIT $2` |
| `city_has_results` | `SELECT COUNT(*) FROM prospects WHERE city = $1` → > 0 |
| `get_all_prospects` | Distinct on domain, ordenado por score global, limite N |
| `get_prospects_filtered` | `WHERE` dinâmico (cidade, país, lojas, preço, scores, status, estilos, MTM, nome, similar_to_client) + subquery DISTINCT ON domain + count distinct |
| `get_filter_options` | Vários `SELECT DISTINCT` + agregados MIN/MAX |
| `get_price_analysis` / `get_store_count_analysis` | Agregações por buckets |
| `get_dashboard_stats` | Totais, por status, top cidades, distribuição de scores |
| `get_all_searched_cities` | GROUP BY city com médias e contagens por status |
| `save_prospect` | `INSERT ... ON CONFLICT (id) DO UPDATE` |
| `is_domain_suppressed` | `SELECT 1 FROM suppression_list` |
| `prospect_feedback` | Insert + opcional `UPDATE prospects SET status = 'rejected'` se feedback down |

---

## 10. API REST (prefixos)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/prospect` | SSE — inicia pipeline (body: `SearchRequest`) |
| POST | `/api/prospect/resume` | SSE — retoma grafo com aprovações (HITL preparado) |
| GET | `/api/prospects` | Lista filtrada (query params) |
| POST | `/api/prospects/filter` | Mesmo com body `ProspectFilters` |
| GET | `/api/prospects/filters/options` | Opções + presets `ideal_boutiques`, `luxury_only` |
| POST | `/api/prospects/suppress` | RGPD — adiciona domínio à supressão |
| GET/PATCH/DELETE | `/api/prospects/{id}` | Detalhe, estado, apagar |
| POST | `/api/prospects/{id}/feedback` | Feedback comercial |
| GET | `/api/cities` | Lista cidades pesquisadas |
| GET | `/api/cities/{city}/stats` | Stats + top 5 |
| DELETE | `/api/cities/{city}` | Apaga todos os prospects da cidade |
| GET | `/api/dashboard` | Stats gerais |
| GET | `/api/analytics/prices` | Distribuição de preços |
| GET | `/api/analytics/stores` | Contagens por tamanho |
| POST | `/api/email/send` | Envio Resend |
| POST | `/api/email/draft` | Rascunho + `mailto:` |
| POST | `/api/chat` | Consultor IA (RAG sobre prospects) |
| GET/DELETE | `/api/chat/history` | Histórico |
| GET | `/api/chat/cities` | Cidades para dropdown do chat |
| POST | `/api/whatsapp/webhook` | Twilio (se configurado) |
| GET | `/api/export/csv` | Export CSV de prospects (filtros city, status) |

**CORS** (`main.py`): `http://localhost:3000`, `https://ambitious-coast-0f9176703.1.azurestaticapps.net`.

---

## 11. Chat / “pergunta → resposta final” (`backend/routers/chat.py`)

1. Grava mensagem do utilizador em **`chat_messages`** (role, content, city_context).
2. Se cidade não for “global/todas/all”: `get_prospects_by_city(city, 50)`; senão `get_all_prospects(100)`.
3. Constrói texto estruturado `build_prospect_context` + `build_client_context` (18 clientes) + estatísticas `get_dashboard_stats` / `get_all_searched_cities`.
4. Sistema dinâmico **PT vs EN** (regras de formatação diferentes).
5. `get_llm(fast=False).invoke(messages)` — modelo **profundo**.
6. Grava resposta do assistente em `chat_messages`.

**⚠️ Gap de schema:** não existe migração no repositório que crie a tabela `chat_messages`. Em produção esta tabela tem de existir (criação manual ou migração por acrescentar), senão o chat falha ao gravar/ler histórico.

**Campo `is_appointment_only`:** referenciado em `build_prospect_context`; **não** consta das migrações de `prospects` — na prática virá sempre vazio/falso até haver coluna ou lógica que o preencha.

---

## 12. Frontend — rotas e integrações

| Rota | Função |
|------|--------|
| `/` | Pesquisa cidade → POST SSE `/api/prospect`; mostra últimas mensagens de progresso |
| `/saved-cities` | Lista cidades, cartões de marcas, `GET /api/prospects?city=...` com filtros (ver `FilterPanel`) |
| `/chat` | Consultor: `POST /api/chat`, selector de cidade, idioma PT/EN |
| `/clients` | Página estática de “rede de clientes” (dados hardcoded no TS — mirror de marketing, não a BD `lanca_clients`) |

**Autenticação:** `NextAuth` com **Azure AD** (`frontend/app/api/auth/[...nextauth]/route.ts`); `middleware.ts` protege todas as rotas excepto `api/auth`, `auth/signin`, `_next`, `favicon`.

**Variável típica:** `NEXT_PUBLIC_API_URL` (default browser: `http://localhost:8000`).

### Filtros UI (`FilterPanel.tsx`) → query API

- **Qualidade “Fit Lança”:** `high` → `min_score=70`; `medium` → `min_score=50`.
- **Dimensão:** boutique 1–5 lojas; médio 6–20; grande ≥21.
- **Preço:** faixas `under_500`, `500_1000`, `1000_2000`, `over_2000` mapeadas para `min_price` / `max_price` em EUR.

---

## 13. WhatsApp (`backend/routers/whatsapp.py`)

- Webhook Twilio: comandos `reset`, `cidade <nome>` para definir contexto de cidade na sessão em memória.
- Mensagens normais: reutiliza pipeline semelhante ao chat/RAG (`process_whatsapp_message`).

---

## 14. Variáveis de ambiente (resumo)

**Obrigatórias para o pipeline completo:**

- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION` (opcional default), `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_DEPLOYMENT_FAST`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- `EXA_API_KEY` (discovery — **não** está no `.env.example` mas é usada no código e no GitHub Actions)
- `SYNC_DATABASE_URL` ou `POSTGRES_*` para `PostgresManager`

**Fortemente recomendadas:**

- `GOOGLE_PLACES_API_KEY` (fase 1.5 do validator)
- `USE_CRAWL4AI=true` + `CRAWL4AI_BASE_URL` (default `http://localhost:11235` — no `docker-compose` há `CRAWL4AI_API_URL` para o serviço; **alinhar** URL real com o que `Config` lê)

**Opcionais:**

- `RESEND_API_KEY`, `FROM_EMAIL`
- `FIRECRAWL_API_KEY`, `JINA_API_KEY`
- `TWILIO_*` para WhatsApp
- `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- `TAVILY_API_KEY` — presente em config/requirements; **Tavily está desactivado** no fluxo de contactos (comentários em código)

**Frontend:** `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET`, `AZURE_AD_TENANT_ID`, `NEXTAUTH_SECRET`, `NEXT_PUBLIC_API_URL`.

---

## 15. Docker Compose

- **db:** `pgvector/pgvector:pg16`, user `lanca`, DB `lanca_leads`, porta 5432.
- **crawl4ai:** imagem `unclecode/crawl4ai:0.8.5`, porta 11235.
- **api:** build `backend/Dockerfile`, depende de db + crawl4ai; repassa `.env`; define `USE_CRAWL4AI=True` — verificar consistência do hostname da URL Crawl4AI (`crawl4ai:11235` vs `CRAWL4AI_BASE_URL`).

---

## 16. CI/CD

- **`main_app-web-lanca.yml`:** Python 3.11, `pip install -r backend/requirements.txt`, artefacto para Azure Web App; sincronização de **Application Settings** incluindo todas as keys listadas (OpenAI, Exa, Postgres, Jina, Firecrawl, etc.).
- **`azure-static-web-apps-*.yml`:** deploy do frontend Next.js para Azure Static Web Apps.

---

## 17. Resumo numérico do pipeline (referência rápida)

| Etapa | Número / ordem de grandeza |
|-------|----------------------------|
| Queries Exa por cidade (sem cache de grafo) | **3** |
| Resultados pedidos por query | **30** |
| Candidatos URL típicos pós-dedup domínio | ~60–90 (varia) |
| Cap URLs antes validação pesada | **200** |
| Texto Exa mínimo para entrar no mapa | **500** chars |
| Top conteúdos para triagem LLM | **80** |
| Chamadas triagem LLM (fast) | até **80** (1 por URL) |
| Lotes deep LLM | até **ceil(triage_passed / 3)** |
| Google Places | 1 pedido por candidato após triagem (semáforo 5) |
| Scraping Crawl4AI / Firecrawl | até **15** URLs finais |
| Persistência | 1× `calculate_prospect_score` (embed + possível explicação LLM) + `save_prospect` por marca nova |

---

## 18. Documentos relacionados no repositório

- `docs/ARCHITECTURE_FLOW.md` — fluxo arquitectónico (pode estar parcialmente desactualizado vs código)
- `docs/QUALITY_GUARANTEE.md` — garantias de qualidade
- `backend/plans/phase_2_langgraph.md`, `phase_3_hitl.md` — planos futuros / HITL

---

*Última actualização do conteúdo: alinhado ao código do repositório brands-ai na data de elaboração deste ficheiro (Maio 2026).*
