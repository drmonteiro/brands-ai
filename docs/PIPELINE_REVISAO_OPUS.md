# Brands-AI — Documento completo para revisão de pipeline

**Propósito deste documento:** Explicar o que a aplicação faz, como o pipeline funciona, quantas API calls faz, onde estão os gargalos, e que perguntas queremos responder. Destina-se a ser enviado a um modelo (ex.: Claude Opus) para sugerir melhorias de **velocidade**, **custo**, **eficácia** e **simplicidade**.

**Data:** Maio 2026  
**Repo:** `brands-ai` — Confeções Lança prospecting tool  
**Fonte de verdade do pipeline:** `backend/agents/graph.py` + `backend/agents/nodes/*.py`

---

## 1. O que é a aplicação?

### Problema de negócio

A **Confeções Lança** é uma fábrica portuguesa de fatos de homem (mid-to-high, €500–€1.700). A equipa comercial precisa encontrar **retailers/boutiques independentes** numa cidade-alvo que possam ser parceiros de manufacturing (private label / own label).

### O que a app faz

1. O utilizador introduz uma **cidade** (ex.: "Viena", "Lisboa", "Brighton").
2. Um **pipeline automático** (LangGraph + FastAPI):
   - Pesquisa marcas de menswear na web
   - Filtra só marcas que vendem **fatos de homem**
   - Enriquece cada marca (preços, sede, lojas, contactos)
   - Pontua vs portfolio de clientes Lança existentes
   - Guarda as **top 20** na base de dados PostgreSQL
3. O frontend mostra resultados, permite filtrar, exportar CSV, dar feedback, e usar um **chat consultor IA** com contexto dos prospects guardados.

### Stack

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 15, TypeScript, Tailwind, NextAuth (Azure AD) |
| Backend | FastAPI, LangGraph, async PostgreSQL |
| DB | PostgreSQL + pgvector (embeddings) |
| Search | **Exa** (neural search) — *não Tavily* |
| LLM | **Azure OpenAI** (GPT-5.1 deep, GPT-5-mini fast) |
| Localização | **Google Places API (New)** |
| Email | Resend (draft + send) |

> **Nota:** O `README.md` raiz está desatualizado (menciona Tavily e um grafo de 6 nós com HITL). O código actual usa **4 nós** e **Exa**.

---

## 2. Arquitectura de alto nível

```
┌─────────────┐     POST /api/prospect (SSE)      ┌──────────────────┐
│  Frontend   │ ────────────────────────────────► │  workflow_service │
│  (Next.js)  │ ◄── progress events + results ─── │  + LangGraph      │
└─────────────┘                                   └────────┬─────────┘
                                                           │
                    discovery → filter → enrich → score_save
                                                           │
                                                           ▼
                                                  ┌──────────────────┐
                                                  │  PostgreSQL       │
                                                  │  prospects        │
                                                  │  lanca_clients    │
                                                  │  checkpoints      │
                                                  └──────────────────┘
```

### Cache

Se a cidade **já tem prospects** na DB e `force_refresh=false`, o pipeline **não corre** — devolve até 50 resultados em cache via SSE.

Ficheiro: `backend/services/workflow_service.py`

---

## 3. Pipeline LangGraph — 4 nós

Grafo linear em `backend/agents/graph.py`:

```
discovery → filter → enrich → score_save → END
```

### Estado partilhado (`GraphState`)

| Campo | Descrição |
|-------|-----------|
| `target_city` | Cidade introduzida pelo user |
| `target_country` | Inferido por LLM no discovery |
| `exchange_rate` | Taxa EUR→USD (hardcoded 1.08) |
| `search_results_raw` | Resultados brutos Exa (deduplicados por domínio) |
| `filtered_brands` | Marcas que passaram filtro "fatos de homem" |
| `enriched_brands` | Marcas com dados estruturados + localização |
| `verified_brands` | Top leads finais (BrandLead) |
| `progress` | Mensagens SSE acumuladas |

---

## 4. Nó 1 — Discovery (`discovery.py`)

### Objectivo
Encontrar candidatos na web para a cidade-alvo.

### Passos

1. **LLM (mini):** Inferir país da cidade  
   - Prompt: `"Given the city 'X', what country is it in?"`  
   - 1 call

2. **LLM (mini):** Gerar 8–12 queries de pesquisa Exa  
   - Foco: marcas/retailers de fatos, não só alfaiates bespoke  
   - Output: JSON array de strings  
   - 1 call

3. **Exa (sequencial):** Para cada query  
   - `num_results=20` (env `EXA_NUM_RESULTS`)  
   - Texto até 10.000 chars por resultado  
   - Exclui ~30 domínios (Amazon, Yelp, redes sociais, etc.)  
   - **~8–12 searches**, uma após a outra (não paralelo)

4. **Dedup:** Por domínio → tipicamente **40–80 domínios únicos**

### API calls típicas (cidade nova)

| Serviço | Calls |
|---------|-------|
| Azure GPT-5-mini | 2 |
| Exa search | 8–12 |

### Gargalo conhecido
Queries Exa correm **em série** — latência mínima ≈ 8 × tempo Exa.

> **Queries em detalhe:** ver **Secção 20 — Anexo** (textos exactos de todas as pesquisas Exa, Google Places e prompts LLM de geração de queries).

---

## 5. Nó 2 — Filter (`filter.py`)

### Objectivo
Manter só negócios que vendem **fatos de homem** (não streetwear, mulher, blogs, H&M, etc.).

### Passos

1. Dividir candidatos em batches de **12** (`FILTER_BATCH_SIZE`)
2. **LLM (mini):** Por batch, classificar KEEP/REMOVE  
   - Envia: URL, title, excerpt de conteúdo (até 2000 chars)  
   - Output: `[{"url", "keep", "brand_name", "reason"}]`  
   - Batches processados **sequencialmente**

### API calls típicas (~60 candidatos)

| Serviço | Calls |
|---------|-------|
| Azure GPT-5-mini | ~5 |

---

## 6. Nó 3 — Enrich (`enrich.py` + `location_enrichment.py`)

### Objectivo
Extrair dados estruturados por marca: preços, sede, lojas, email, validar localização.

Este é o nó **mais longo e mais caro** (~20–40 min para ~48 marcas).

### Sub-fases

#### N3a — Exa price lookup (paralelo, max 5 concurrent)
- Por marca: search `"{brand} suits price"` no domínio da marca  
- Fallback: search mais amplo se falhar  
- **1–2 Exa calls × N marcas**

#### N3b — LLM structured extraction (batched)
- Batches de **6 marcas** (`ENRICH_BATCH_SIZE`)  
- Modelo: **GPT-5.1**  
- Input por marca: conteúdo Exa discovery (4000 chars) + pricing page (3000 chars)  
- Output: JSON com name, prices, HQ (só se explícito), overview, email, etc.  
- Batches **sequenciais**

#### N3c — HQ resolution
Por marca (paralelo Exa max 5, LLM HQ max 3):

1. **Exa:** Página about/contact do domínio  
2. **LLM 5.1:** Extrair sede do conteúdo (só evidência explícita → `verified`)  
3. Se não verified → **LLM 5.1 obrigatório:** conhecimento sobre a marca (`llm_knowledge`, só `confidence: high`, **sem morada**)

Também:
- **LLM mini (1×):** Resolver nomes válidos da cidade-alvo (`CityContext`) — sem listas hardcoded  
- **LLM mini (0–1×):** Batch verificar se sedes encontradas = mesma cidade que o alvo

#### N3d — Exa email lookup
- Só marcas sem email  
- 1–2 Exa calls por marca  
- Regex extrai email do texto (sem LLM)

#### N3e — Store locator
- **Exa:** Página store locator por marca  
- **LLM 5.1:** Extrair lista de lojas (só explícito → `verified`)

#### N3f — Google Places
- Por marca: **2 calls** API  
  - `search_local_presence` — loja na cidade-alvo  
  - `count_brand_locations` — contagem global  
- Paralelo max **5 concurrent**  
- Valida: nome da marca bate certo + endereço contém cidade-alvo

#### N3g — Merge + validate
- Merge lojas site > Google Places  
- `validate_location_data`: limpa moradas não verificadas, rejeita lojas na cidade errada  
- Define `city_presence_type`: `hq` | `store` | `showroom` | `unknown`

### API calls típicas (~48 marcas)

| Serviço | Calls (approx) |
|---------|----------------|
| Exa | ~200 (preços + HQ + stores + emails) |
| Azure GPT-5.1 | ~130 (extract + HQ×2 + stores + fit parcial) |
| Azure GPT-5-mini | 2–3 |
| Google Places | ~96 (48×2) |

### Princípios de qualidade (localização)

- **Errado > vazio:** preferimos `unknown` a dados inventados  
- Sede `verified` = evidência no site  
- Sede `llm_knowledge` = só cidade, confiança high, sem morada  
- Google Places nunca vira sede  
- Filtro final exclui marcas sem presença confirmada na cidade-alvo

---

## 7. Nó 4 — Score + Save (`persistence.py`)

### Objectivo
Pontuar, filtrar, guardar top 20.

### Passos

1. **Pre-filtros (sem API):**
   - Excluir clientes Lança existentes (lista em `data/lanca_clients.py`, 18 clientes)
   - Excluir marcas sem presença na cidade (`should_exclude_brand_for_location`)

2. **N4a — Similaridade pgvector (sequencial!)**
   - Por marca: embedding do perfil → `find_similar_clients` (top 3)  
   - **1 embedding API call × N marcas**, uma a uma  
   - Modelo: `text-embedding-3-large` (config) — **atenção:** migration usa `vector(1536)` (small)

3. **N4b — LLM fit assessment (batched)**
   - Batches de **8** marcas  
   - **GPT-5.1:** Score 0–10 fit como parceiro Lança + razão  
   - Inclui perfil ideal + clientes Lança de referência

4. **N4c — Score final (código, sem LLM)**
   ```
   final_score = 40% similarity + 30% LLM_fit + 15% price + 15% store_count
   ```
   > **Nota:** `city_presence_score` é calculado mas **não entra** nesta fórmula.

5. **N4d — Save**
   - Top **20** (`MAX_OUTPUT_BRANDS`) → PostgreSQL  
   - Dedup por `domain + city`

### API calls típicas (~35 marcas após filtros)

| Serviço | Calls |
|---------|-------|
| Azure embeddings | ~35 |
| Azure GPT-5.1 (fit) | ~5 |

---

## 8. Resumo de API calls por run completo

Estimativa para **~48 marcas enriquecidas** (ex.: teste Viena, ~36 min):

| API | Calls | Custo estimado (USD) |
|-----|-------|----------------------|
| Azure GPT-5.1 | ~150 | $1.50 – $2.50 |
| Azure GPT-5-mini | ~10 | $0.03 – $0.08 |
| Azure Embeddings | ~35 | ~$0.01 |
| Exa Search | ~210 | $1.20 – $2.00* |
| Google Places | ~96 | $0 – $3.50** |
| **Total** | **~500** | **~$3 – $8 / cidade** |

\* Exa: 1000 searches/mês grátis → primeiras ~4–5 cidades free  
\*\* Google: 5000 Text Search Pro/mês grátis → muitas runs free

### Onde está o custo e a latência?

```
Custo API (typical run)
├── GPT-5.1 (N3 enrich)     ████████████████████  ~55%
├── Exa (N1 + N3)           ██████████████        ~35%
├── Google Places (N3f)     ████                  ~0–40%
└── Resto                   ▏                     ~5%

Tempo (typical ~48 brands)
├── N3 Enrich               ██████████████████████████████  ~60–70%
├── N1 Discovery (seq Exa)  ████████                          ~10–15%
├── N4 Score (seq embed)    █████                             ~5–10%
└── N2 Filter               ██                                ~5%
```

---

## 9. Todas as chamadas LLM — inventário

> **Prompts completos (texto exacto):** Secção **21**.  
> **Queries Exa/Google Places:** Secção **20**.

| # | Fase | Modelo | Batch | Input principal | Output |
|---|------|--------|-------|-----------------|--------|
| 1 | N1 | mini | 1 | Nome cidade | País |
| 2 | N1 | mini | 1 | Cidade + país | 8–12 queries JSON |
| 3 | N2 | mini | 12 candidatos | URL, title, 2000 chars | keep/remove JSON |
| 4 | N3.1 | mini | 1 | Cidade-alvo | CityContext JSON |
| 5 | N3.2 | 5.1 | 6 marcas | Exa content + pricing | Structured JSON |
| 6 | N3.3a | 5.1 | 1 marca | Exa about page 4000 chars | HQ JSON |
| 7 | N3.3b | 5.1 | 1 marca | Nome + website + contexto | HQ city (high only) |
| 8 | N3.5 | mini | batch | Sede cities vs target | same_as_target JSON |
| 9 | N3.6 | 5.1 | 1 marca | Store locator 5000 chars | Stores JSON |
| 10 | N4 | 5.1 | 8 marcas | Perfil + clientes Lança | fit_score 0–10 |

**Fora do pipeline:** Chat (`/api/chat`), email draft (`/api/email/draft`), WhatsApp webhook — cada um com GPT-5.1.

---

## 10. Modelo de dados — `prospects`

Campos principais (migrations 001–005):

| Campo | Origem |
|-------|--------|
| `name`, `website_url`, `domain`, `city` | Pipeline |
| `avg_suit_price_eur`, `price_range_*` | LLM extract (Exa pricing) |
| `store_count`, `store_locations` | Site store locator + Google Places merge |
| `store_count_confidence` | verified / estimated / uncertain / unknown |
| `headquarters_city`, `headquarters_address` | Exa about (verified) ou LLM (city only) |
| `headquarters_confidence` | verified / llm_knowledge / unknown |
| `local_store_address` | Google Places (validado na cidade) |
| `city_presence_type` | hq / store / showroom / unknown |
| `final_score`, `similarity_score`, `fit_score` | N4 scoring |
| `most_similar_client` | pgvector |
| Contact fields | LLM extract + Exa email |

---

## 11. Frontend — fluxos principais

| Página | Rota | Função |
|--------|------|--------|
| Pesquisa | `/` | Input cidade → SSE pipeline → redirect saved-cities |
| Cidades guardadas | `/saved-cities` | Grid BrandCard, filtros, export, delete cidade |
| Clientes Lança | `/clients` | Referência estática dos 18 clientes |
| Consultor IA | `/chat` | RAG sobre prospects + conhecimento geral menswear |

Componente chave: `BrandCard.tsx` — mostra sede, loja local, badges de confiança, email draft.

---

## 12. Scoring — dois sistemas (confusão potencial)

### A. Pipeline runtime (`persistence.py`) — **o que rankeia saves**

```
final = 40% pgvector_sim + 30% llm_fit + 15% price + 15% stores
```

### B. Rubric YAML (`rubric.yaml`) — **auditoria / avaliação**

Critérios critical/important/bonus com hard rejects (preço <€375, >€2500, >30 lojas, etc.)

Usado por `evaluation/rubric_evaluator.py` — **não** pelo pipeline principal.

### C. `services/scoring.py` — **função completa alternativa**

Soma 7 componentes (price 20, size 15, city 15, wool 10, MTM 10, similarity 20, market 10).  
Usada por `vector_db.match_prospect_to_clients` — **não** por `score_and_save_node`.

> **Pergunta para revisão:** Devemos unificar estes 3 sistemas?

---

## 13. Concorrência e limites actuais

| Constante | Valor | Ficheiro |
|-----------|-------|----------|
| `EXA_NUM_RESULTS` | 20 | discovery.py |
| `FILTER_BATCH_SIZE` | 12 | filter.py |
| `ENRICH_BATCH_SIZE` | 6 | enrich.py |
| `EXA_PRICE_MAX_CONCURRENT` | 5 | enrich.py |
| `EXA_MAX_CONCURRENT` | 5 | location_enrichment.py |
| `HQ_LLM_MAX_CONCURRENT` | 3 | location_enrichment.py |
| Google Places concurrent | 5 | enrich.py |
| `FIT_BATCH` | 8 | persistence.py |
| `MAX_OUTPUT_BRANDS` | 20 | persistence.py |

### O que corre em série (gargalo de velocidade)

- Discovery: todas as queries Exa  
- Filter: todos os batches LLM  
- Enrich N3b: todos os batches extract LLM  
- Score N4a: todos os embeddings (1 por marca)  
- Save: loop sequencial

---

## 14. Problemas conhecidos / dívida técnica

1. **README e docs antigos** descrevem Tavily + 6 nós + HITL — código tem 4 nós + Exa  
2. **Embedding dimension mismatch:** config `text-embedding-3-large` vs DB `vector(1536)` (small)  
3. **Scoring triple:** persistence vs rubric.yaml vs scoring.py — inconsistente  
4. **`city_presence_score` calculado mas não usado** no final_score de persistence  
5. **`EXA_API_KEY` não está** no `.env.example`  
6. **Tavily, Crawl4AI, Firecrawl** nas deps/deploy mas **não usados** no pipeline activo  
7. **Teste Viena (~36 min):** filter de localização teve bugs (Viena≠Vienna) — corrigido com CityContext LLM  
8. **N3c sede:** 2 LLM calls por marca (extract + knowledge) — maior custo/tempo  
9. **Exchange rate** hardcoded 1.08  
10. **`chat_messages` table** usada mas sem migration no repo

---

## 15. Dependências externas obrigatórias

```env
# Mínimo para pipeline completo
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=gpt-5.1
AZURE_OPENAI_DEPLOYMENT_FAST=gpt-5-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
EXA_API_KEY=                    # não documentado em .env.example
GOOGLE_PLACES_API_KEY=          # opcional mas recomendado
SYNC_DATABASE_URL=              # PostgreSQL + pgvector
```

---

## 16. Perguntas para o revisor (Opus)

Queremos sugestões concretas sobre:

### Velocidade
1. Como reduzir **~36 min → ?** para 48 marcas sem perder qualidade?  
2. Vale a pena **paralelizar discovery Exa** (8–12 queries)? Com que concurrency cap?  
3. Os **~130 calls GPT-5.1 no enrich** são justificáveis? Que calls podemos **fundir** ou **eliminar**?  
4. Faz sentido fazer **1 LLM call grande** (extract + HQ + stores) vs fases separadas?  
5. Embeddings em N4 — por que sequencial? Batch embedding API?

### Custo (~$3–8/run)
6. Exa ~210 searches — podemos **reutilizar** conteúdo discovery em vez de 3–4 searches separados por marca?  
7. HQ: Exa about + LLM extract + LLM knowledge — **3 passos** — qual podemos cortar?  
8. Google Places 2×/marca — `count_brand_locations` é necessário se já temos store locator?  
9. GPT-5-mini vs 5.1 — que tarefas podem descer de modelo?

### Eficácia / qualidade
10. O filtro N2 (só Exa snippet) é suficiente ou perdemos marcas boas?  
11. A dupla validação de localização (Exa + Places + LLM city) é over-engineering?  
12. Como garantir sede correcta **sem** 2 LLM calls/marca?  
13. O scoring actual (40/30/15/15) reflecte o rubric comercial? Deve incluir city_presence?

### Arquitectura
14. Unificar os 3 sistemas de scoring?  
15. Remover integrações mortas (Tavily, Crawl4AI)?  
16. Cache por domínio entre cidades (sede/preços não mudam)?  
17. HITL faz sentido num ponto do pipeline?

### Simplificação radical
18. **Pipeline mínimo viável:** Discovery → Filter → Extract (1 LLM) → Save — o que perdemos?  
19. Alternativa: Exa **Answer API** ($5/1k) vs search + múltiplos LLM extracts?  
20. Vale a pena **pré-filtrar por país/cidade** no Exa antes de enriquecer tudo?

---

## 17. Ficheiros-chave para consulta

| Ficheiro | Conteúdo |
|----------|----------|
| `backend/agents/graph.py` | Grafo LangGraph |
| `backend/agents/nodes/discovery.py` | N1 |
| `backend/agents/nodes/filter.py` | N2 |
| `backend/agents/nodes/enrich.py` | N3 |
| `backend/agents/nodes/persistence.py` | N4 |
| `backend/services/location_enrichment.py` | HQ, lojas, CityContext, filtros geo |
| `backend/services/google_places.py` | Google Places |
| `backend/services/workflow_service.py` | SSE + cache |
| `backend/services/scoring.py` | Rubric scorer alternativo |
| `backend/rubric.yaml` | Critérios comerciais |
| `backend/data/lanca_clients.py` | 18 clientes referência |
| `frontend/app/page.tsx` | UI pesquisa |
| `frontend/components/BrandCard.tsx` | Card prospect |

---

## 18. Diagrama detalhado do Enrich (nó crítico)

```
filtered_brands (N)
    │
    ├─► [PARALLEL max 5] Exa price × N          ──► price_contents[]
    │
    ├─► [SEQ batches 6] LLM 5.1 extract          ──► structured[]
    │
    ├─► [PARALLEL] Exa HQ + LLM extract × N
    │       └─► if not verified → LLM knowledge × N  ◄── 2 LLM/marca
    │
    ├─► [PARALLEL max 5] Exa email × (N - com email)
    │
    ├─► [PARALLEL max 5] Exa store locator × N
    │       └─► LLM 5.1 extract stores × N
    │
    ├─► [PARALLEL max 5] Google Places × N × 2 calls
    │
    └─► merge + validate_location_data
            └─► enriched_brands
```

---

## 19. Critério de sucesso do pipeline

Um run é **bem-sucedido** se:

1. Encontra marcas **reais** de fatos de homem na cidade-alvo  
2. Dados de **sede e lojas são correctos** (ou explicitamente `unknown`)  
3. Preços estão na faixa €500–€2000 (rubric)  
4. Top 20 inclui parceiros plausíveis vs clientes Lança (Hawes & Curtis, Garcia Madrid, etc.)  
5. Completa em tempo aceitável para uso comercial (<15 min ideal?)  
6. Custo por cidade previsível e baixo (<$5 ideal?)

---

## 20. Anexo — Queries, prompts e parâmetros de pesquisa

Esta secção lista **exactamente** o que é enviado a cada API de pesquisa (não LLM de extracção — esses estão na Secção 9).

---

### 20.1 N1 — LLM gera queries Exa (Discovery)

**Modelo:** GPT-5-mini · **1 call por cidade**

**Prompt completo** (`discovery.py` → `_generate_queries`):

```
You are helping a Portuguese suit manufacturer find potential retail partners.

CITY: {city}
COUNTRY: {country}

Generate 8-10 search queries to find MEN'S SUIT BRANDS AND RETAILERS in {city}.

IMPORTANT RULES:
- We want BRANDS and RETAILERS that sell men's suits (ready-to-wear), NOT individual bespoke tailors
- We want businesses with physical stores (ideally 2-20 stores), not online-only
- Include queries in English AND the local language of {city}
- Focus on: suits, blazers, tailored jackets, formal menswear
- DO NOT focus on: bespoke-only tailors, made-to-measure-only ateliers, shirt-only shops
- Mix different angles: "men's suit brand", "menswear retailer", "formal wear store", "suit shop"

GOOD query examples:
- "men's suit brands {city} retailer"
- "premium menswear store {city} suits"
- "formal wear brand {city} multiple locations"
- "{city} men's clothing store suits jackets"

BAD query examples (too narrow):
- "bespoke tailor {city}" (finds only individual tailors)
- "custom suit {city}" (finds only made-to-measure)
- "Savile Row style {city}" (too luxury/niche)

Return ONLY a JSON array of query strings. No explanation.
Example: ["query 1", "query 2", ...]
```

**Output esperado:** JSON array com 8–12 strings (truncado a 12).

**Fallback se LLM falhar** (6 queries fixas):

```
men's suit brands {city} retailer
premium menswear store {city} suits jackets
formal wear brand {city} {country}
{city} men's clothing store suits
best suit shops {city} {country}
menswear retailer {city} multiple stores
```

---

### 20.2 N1 — Exa search (por cada query gerada)

**API:** `exa.search(query, **kwargs)` · **8–12 calls sequenciais**

| Parâmetro | Valor |
|-----------|-------|
| `query` | String do array LLM (ex.: `"men's suit brands Vienna retailer"`) |
| `num_results` | `20` (env `EXA_NUM_RESULTS`) |
| `type` | `"auto"` |
| `exclude_domains` | Ver lista abaixo |
| `contents.text.maxCharacters` | `10000` |
| `contents.highlights` | `true` |

**Domínios excluídos** (`EXCLUDE_DOMAINS`):

```
amazon.com, ebay.com, walmart.com, target.com,
nordstrom.com, saksfifthavenue.com, neimanmarcus.com,
aliexpress.com, alibaba.com,
yelp.com, yellowpages.com, tripadvisor.com,
trustpilot.com, glassdoor.com, indeed.com,
foursquare.com, kompass.com,
facebook.com, instagram.com, tiktok.com,
twitter.com, x.com, linkedin.com,
pinterest.com, reddit.com, quora.com,
google.com, maps.google.com,
wikipedia.org, wikidata.org,
timeout.com, esquire.com, gq.com
```

**Retries:** até 3 (`EXA_MAX_RETRIES`), backoff 1.5s × 2^attempt em erros transientes (429, 5xx, timeout).

---

### 20.3 N3a — Exa price lookup (por marca)

**Ficheiro:** `enrich.py` → `_exa_price_lookup`

| Tentativa | Query Exa | `num_results` | Scope |
|-----------|-----------|---------------|-------|
| 1ª | `{brand_name} suits price` | 3 | `include_domains=[domínio da marca]` |
| 2ª (fallback) | `{brand_name} men's suits price collection` | 2 | global (sem domain lock) |

| Parâmetro | Valor |
|-----------|-------|
| `type` | `"auto"` |
| `contents.text.maxCharacters` | `5000` (`EXA_PRICE_MAX_CHARS`) |

**Concorrência:** max 5 em paralelo (`EXA_PRICE_MAX_CONCURRENT`).

---

### 20.4 N3c — Exa HQ lookup (por marca)

**Ficheiro:** `location_enrichment.py` → `exa_hq_lookup`

| Campo | Valor |
|-------|-------|
| Query | `{brand_name} headquarters about us contact address registered office` |
| `include_domains` | Domínio do `website_url` da marca |
| `num_results` | 3 |
| `contents.text.maxCharacters` | `4000` |

---

### 20.5 N3d — Exa email lookup (por marca sem email)

**Ficheiro:** `enrich.py` → `_exa_email_lookup`

| Tentativa | Query Exa | `num_results` | Scope |
|-----------|-----------|---------------|-------|
| 1ª | `{brand_name} contact email` | 3 | `include_domains=[domínio]` |
| 2ª (fallback) | `{brand_name} email contact us` | 2 | global |

Extração: **regex** no texto (sem LLM). Preferência: `info@`, `contact@`, `hello@`, `sales@`.

---

### 20.6 N3e — Exa store locator (por marca)

**Ficheiro:** `location_enrichment.py` → `exa_store_locator_lookup`

| Campo | Valor |
|-------|-------|
| Query | `{brand_name} store locations find a store boutiques shops` |
| `include_domains` | Domínio da marca |
| `num_results` | 3 |
| `contents.text.maxCharacters` | `4000` |

---

### 20.7 N3f — Google Places (por marca)

**API:** `POST https://places.googleapis.com/v1/places:searchText`

#### Call A — Presença local na cidade (`search_local_presence`)

| Campo | Valor |
|-------|-------|
| `textQuery` | `{brand_name} menswear {city}` (+ ` {country}` se disponível) |
| `maxResultCount` | 3 |

**FieldMask:** `displayName`, `formattedAddress`, `nationalPhoneNumber`, `internationalPhoneNumber`, `websiteUri`, `googleMapsUri`, `rating`, `userRatingCount`, `types`, `location`, `businessStatus`

**Validação pós-API:** nome do place deve fazer match com a marca; endereço deve conter cidade-alvo.

#### Call B — Contagem global de lojas (`count_brand_locations`)

| Campo | Valor |
|-------|-------|
| `textQuery` | `{brand_name} store` (+ ` {country}` se disponível) |
| `maxResultCount` | 20 |

**FieldMask:** `displayName`, `formattedAddress`, `businessStatus`, `location`, `websiteUri`

**Validação:** ignora `CLOSED_PERMANENTLY`; filtra por `_brand_name_matches(place_name, brand_name)`.

**Concorrência:** max 5 marcas em paralelo.

---

### 20.8 Resumo — templates de query por fase

| Fase | Template | API | × por run (~48 marcas) |
|------|----------|-----|------------------------|
| N1 Discovery | LLM gera 8–12 queries variadas | Exa | 8–12 |
| N3a Price | `{brand} suits price` | Exa | ~48–96 |
| N3c HQ | `{brand} headquarters about us contact...` | Exa | ~48 |
| N3d Email | `{brand} contact email` | Exa | ~30–60 |
| N3e Stores | `{brand} store locations find a store...` | Exa | ~48 |
| N3f Local | `{brand} menswear {city}` | Google | ~48 |
| N3f Count | `{brand} store` | Google | ~48 |

**Total pesquisas externas (Exa + Places):** ~280–360 por run completo.

---

### 20.9 O que NÃO são "queries" de pesquisa

Estes passos usam **LLM** (não Exa/Places directamente) — prompts completos na **Secção 21**.

---

## 21. Anexo — Prompts LLM completos (pipeline + extras)

Convenções:
- `{variável}` = substituído em runtime pelo código
- Blocos dinâmicos (`{candidates_block}`, `{brands_block}`, `{context}`) são construídos a partir dos dados reais
- **mini** = `AZURE_OPENAI_DEPLOYMENT_FAST` (GPT-5-mini)
- **5.1** = `AZURE_OPENAI_DEPLOYMENT` (GPT-5.1)
- `max_tokens=12000` em todas as calls (`utils.py`)

---

### 21.1 N1 — Inferir país da cidade

| | |
|---|---|
| **Ficheiro** | `discovery.py` → `_infer_country` |
| **Modelo** | mini · **1× por run** |
| **Input dinâmico** | `{city}` = cidade do user |

```
Given the city '{city}', what country is it in? Reply with ONLY the English name of the country. No punctuation.
```

**Output:** texto livre (ex.: `Austria`)  
**Fallback se erro:** `"USA"`

---

### 21.2 N1 — Gerar queries Exa

| | |
|---|---|
| **Ficheiro** | `discovery.py` → `_generate_queries` |
| **Modelo** | mini · **1× por run** |
| **Input dinâmico** | `{city}`, `{country}` |

```
You are helping a Portuguese suit manufacturer find potential retail partners.

CITY: {city}
COUNTRY: {country}

Generate 8-10 search queries to find MEN'S SUIT BRANDS AND RETAILERS in {city}.

IMPORTANT RULES:
- We want BRANDS and RETAILERS that sell men's suits (ready-to-wear), NOT individual bespoke tailors
- We want businesses with physical stores (ideally 2-20 stores), not online-only
- Include queries in English AND the local language of {city}
- Focus on: suits, blazers, tailored jackets, formal menswear
- DO NOT focus on: bespoke-only tailors, made-to-measure-only ateliers, shirt-only shops
- Mix different angles: "men's suit brand", "menswear retailer", "formal wear store", "suit shop"

GOOD query examples:
- "men's suit brands {city} retailer"
- "premium menswear store {city} suits"
- "formal wear brand {city} multiple locations"
- "{city} men's clothing store suits jackets"

BAD query examples (too narrow):
- "bespoke tailor {city}" (finds only individual tailors)
- "custom suit {city}" (finds only made-to-measure)
- "Savile Row style {city}" (too luxury/niche)

Return ONLY a JSON array of query strings. No explanation.
Example: ["query 1", "query 2", ...]
```

**Output:** JSON array de strings (8–12, max 12)  
**Fallback:** 6 queries fixas — ver Secção 20.1

---

### 21.3 N2 — Filtro KEEP/REMOVE

| | |
|---|---|
| **Ficheiro** | `filter.py` → `_filter_batch` |
| **Modelo** | mini · **ceil(N/12) batches** |
| **Input dinâmico** | `{target_city}`, `{candidates_block}`, `{len(candidates)}` |

**Bloco `{candidates_block}`** — por candidato (até 12):
```
--- CANDIDATE {i} ---
URL: {url}
TITLE: {title}
CONTENT (excerpt): {text ou highlights, max 2000 chars}
```

**Prompt:**
```
You are a strict filter for a Portuguese suit manufacturer (Confeções Lança).
We ONLY want brands/retailers that sell MEN'S SUITS (fatos de homem).

CITY: {target_city}

KEEP if the business sells:
- Men's suits (complete suits, two-piece, three-piece)
- Men's blazers/sport coats + tailored trousers (suit separates)
- Formal menswear with suits as a core product

REMOVE if the business is:
- T-shirt, casual wear, streetwear, sportswear brand
- Women's-only fashion
- Shirt-only brand (no suits)
- Shoe/accessory-only brand
- Blog, magazine, review site, marketplace
- Generic department store or fast fashion chain (H&M, Zara, etc.)
- Restaurant, hotel, or non-clothing business
- Brand with zero evidence of selling suits

CANDIDATES ({len} total):
{candidates_block}

TASK: For each candidate, decide KEEP or REMOVE.
Return ONLY a JSON array with one object per candidate, in SAME order:
[{"url": "...", "keep": true/false, "brand_name": "extracted brand name", "reason": "short reason"}]

Return ONLY the JSON array, no other text.
```

**Fallback se erro:** mantém todos os candidatos (`keep: true`)

---

### 21.4 N3 — Contexto da cidade-alvo (CityContext)

| | |
|---|---|
| **Ficheiro** | `location_enrichment.py` → `resolve_target_city_context` |
| **Modelo** | mini · **1× por run** |
| **Input dinâmico** | `{city_query}` |

```
The user is searching for menswear brands in the city "{city_query}".

Return the standard names for this SAME municipality (English, local language, common alternate spellings).
Only include names that genuinely refer to this exact city — do NOT include nearby cities or regions.
If the query is ambiguous or not a real city, return confidence "unknown".

Return ONLY JSON:
{
  "canonical_name": "Standard English name",
  "names": ["all valid spellings including local language"],
  "country": "Country name or null",
  "confidence": "high" or "unknown"
}
```

**Output usado para:** comparar sedes/endereços sem listas hardcoded  
**Fallback:** só o nome que o user escreveu

---

### 21.5 N3b — Extração estruturada (preços, overview, HQ inicial)

| | |
|---|---|
| **Ficheiro** | `enrich.py` → `_extract_structured_batch` |
| **Modelo** | 5.1 · **ceil(N/6) batches** |
| **Input dinâmico** | `{target_city}`, `{target_country}`, `{candidates_block}`, `{len(brands)}` |

**Bloco `{candidates_block}`** — por marca (até 6):
```
=== BRAND {i} ===
URL: {url}
BRAND NAME (from filter): {brand_name}
GENERAL CONTENT:
{exa discovery text/highlights, max 4000 chars}
PRICING PAGE CONTENT:
{exa price lookup, max 3000 chars}
```

**Prompt:**
```
You are a data analyst extracting structured information about menswear brands for a Portuguese suit manufacturer (Confeções Lança).

CITY: {target_city}
COUNTRY: {target_country}

For each brand below, extract structured data from BOTH the general content and pricing page content.
The PRICING PAGE CONTENT comes directly from the brand's website — it contains real product prices.
If information is not available, use null.

BRANDS ({len} total):
{candidates_block}

TASK: Extract structured data for each brand.
Return ONLY a JSON array with one object per brand, in SAME order:
[{
  "name": "Brand Name",
  "website_url": "https://...",
  "origin_country": "Country where brand is headquartered",
  "headquarters_city": "City where brand HQ is located (explicit evidence only) or null",
  "headquarters_confidence": "verified" or "unknown",
  "avg_suit_price_eur": 800,
  "price_range_min_eur": 500,
  "price_range_max_eur": 1200,
  "made_to_measure": true/false/null,
  "wool_percentage": "100%" or "mixed" or null,
  "brand_style": "Heritage/Premium/Contemporary/Luxury/Traditional",
  "business_model": "Retail/Bespoke/Multi-brand/Online+Retail",
  "company_overview": "2-3 sentences describing the brand, what they sell, and their positioning",
  "contact_email": "email found in content or null",
  "clothing_types": ["suits", "blazers", "trousers"],
  "target_gender": "men" or "unisex" or "women",
  "is_chain": true/false/null,
  "bespoke_only": true/false/null
}]

PRICING RULES:
- PRIORITIZE prices from the PRICING PAGE CONTENT — these are real prices from the brand's site
- Convert all prices to EUR. Use approximate rates: £1 = €1.17, $1 = €0.93, CHF 1 = €1.05
- If only one price is found, use it as both min and max
- If no price found, set all price fields to null
- avg_suit_price_eur = midpoint of min and max

HEADQUARTERS RULES:
- headquarters_city = the city where the brand's HEAD OFFICE / HQ is located
- ONLY extract if EXPLICITLY stated: "based in", "headquartered in", "founded in", "registered office", footer address
- NEVER guess or infer headquarters from store locations or target city
- If unclear or not explicitly stated, use null and headquarters_confidence "unknown"
- If explicitly found, set headquarters_confidence to "verified"

EMAIL RULES:
- Look for contact/info/sales email addresses in the content
- Prefer: sales@, info@, contact@, hello@ (general business emails)
- Do NOT use personal emails or noreply emails
- If not found, use null

Return ONLY the JSON array.
```

---

### 21.6 N3c — Extrair sede do site (Exa About page)

| | |
|---|---|
| **Ficheiro** | `location_enrichment.py` → `extract_hq_from_content` |
| **Modelo** | 5.1 · **1× por marca** com conteúdo Exa HQ |
| **Input dinâmico** | `{brand_name}`, `{hq_content[:4000]}` |

```
Extract headquarters information for the menswear brand "{brand_name}" from the content below.

RULES:
- ONLY extract if EXPLICITLY stated (e.g. "based in", "headquartered in", "registered office", "founded in", footer address)
- NEVER guess or infer from store locations
- If no explicit HQ evidence, return null for all fields and confidence "unknown"

CONTENT:
{hq_content}

Return ONLY JSON:
{
  "headquarters_city": "City name or null",
  "headquarters_address": "Full address or null",
  "origin_country": "Country or null",
  "headquarters_confidence": "verified" or "unknown"
}
```

**Aceita só se:** `headquarters_confidence == "verified"` e cidade presente

---

### 21.7 N3c — Sede via conhecimento do modelo (fallback obrigatório)

| | |
|---|---|
| **Ficheiro** | `location_enrichment.py` → `resolve_headquarters_via_llm` |
| **Modelo** | 5.1 · **1× por marca** sem sede `verified` |
| **Input dinâmico** | `{brand_name}`, `{context}` (website, domain, origin_country, description[:300]) |

```
Where is the headquarters (registered office / main atelier) of the menswear brand "{brand_name}"?

{context}

CRITICAL: Wrong location data is worse than no data.
- Only answer if you are HIGHLY confident this is factual, well-known information.
- The HQ is where the company is based — NOT a retail store in another city.
- Do NOT infer HQ from store locations, domain TLD, or country alone.
- For obscure or unidentifiable brands, return confidence "unknown".

Return ONLY JSON:
{
  "headquarters_city": "City name or null",
  "headquarters_address": null,
  "origin_country": "Country or null",
  "confidence": "high" or "unknown"
}
```

**Aceita só se:** `confidence == "high"` — guarda **só cidade**, nunca morada

---

### 21.8 N3c — Equivalência sede vs cidade-alvo (batch)

| | |
|---|---|
| **Ficheiro** | `location_enrichment.py` → `batch_check_hq_cities_against_target` |
| **Modelo** | mini · **0–1× por run** |
| **Input dinâmico** | `{ctx.canonical_name}`, `{names_block}`, `{cities_block}` |

```
Target search city: {canonical_name} (also known as: {names_block}).

For each city below, answer whether it is the SAME municipality as the target city.
Be strict — nearby cities, suburbs, or different cities with similar names are NOT the same.

Cities to check:
{cities_block}

Return ONLY JSON array:
[{"city": "exact city from list", "same_as_target": true or false}]
```

---

### 21.9 N3e — Extrair lojas do store locator

| | |
|---|---|
| **Ficheiro** | `location_enrichment.py` → `extract_stores_from_content` |
| **Modelo** | 5.1 · **1× por marca** com conteúdo Exa store locator |
| **Input dinâmico** | `{brand_name}`, `{store_content[:5000]}` |

```
Extract physical store locations for the menswear brand "{brand_name}" from the content below.

RULES:
- ONLY list stores explicitly mentioned in the content
- NEVER invent or estimate store locations
- If a total count is explicitly stated (e.g. "5 boutiques"), use it for total_count
- If no store list found, return empty stores and confidence "unknown"

CONTENT:
{store_content}

Return ONLY JSON:
{
  "stores": [{"city": "London", "address": "12 Savile Row, London W1"}],
  "total_count": 5,
  "confidence": "verified" or "unknown",
  "source_quote": "exact quote from content or null"
}
```

**Aceita só se:** `confidence == "verified"` e addresses não vazios

---

### 21.10 N4 — Fit assessment (parceiro Lança)

| | |
|---|---|
| **Ficheiro** | `persistence.py` → `_llm_fit_assessment` |
| **Modelo** | 5.1 · **ceil(N/8) batches** |
| **Input dinâmico** | `{target_city}`, `{brands_block}`, `{len(brands)}` |

**Bloco `{brands_block}`** — por marca (até 8):
```
--- BRAND {i} ---
Name: {name}
URL: {website_url}
Country: {origin_country}
Price: €{avg_suit_price_eur}
Stores: {store_count}
Wool: {wool_percentage}
MTM: {made_to_measure}
Style: {brand_style}
Business: {business_model}
Overview: {company_overview, max 500 chars}
```

**Prompt:**
```
You are evaluating menswear brands as potential manufacturing partners for Confeções Lança, a Portuguese suit manufacturer.

LANÇA'S IDEAL PARTNER PROFILE:
- Independent menswear retailers/boutiques (NOT large department stores)
- Mid-to-high range: suits €500-€1,700, jackets €300-€1,000
- Fewer than 20 physical stores (easier partnership)
- Brands that value European manufacturing quality
- Own label collections or interested in private label production
- Headquartered or strong presence in {target_city}

CURRENT LANÇA CLIENTS (for reference):
- Hawes & Curtis (UK, 30 stores, €500 suits, 10yr partner)
- Carlos Nieto (Colombia, 20 stores, €800 suits, 12yr partner)
- Walker Slater (UK, 5 stores, €800 suits, Scottish tweed specialist)
- Gresham Blake (UK, 1 store, €1000 suits, bespoke Brighton tailor)
- Garcia Madrid (Spain, 1 store, €1000 suits, 10yr partner)

BRANDS TO EVALUATE ({len} total):
{brands_block}

TASK: Rate each brand 0-10 on fit as a Lança partner.
10 = perfect match (similar to best current clients)
7-9 = strong fit
4-6 = moderate fit
1-3 = poor fit
0 = not suitable

Return ONLY a JSON array:
[{"url": "...", "fit_score": 0-10, "fit_reason": "one sentence explanation"}]
```

---

### 21.11 N4 — Embeddings (não é prompt de chat)

| | |
|---|---|
| **Ficheiro** | `vector_db.py` → `find_similar_clients` |
| **Modelo** | `text-embedding-3-large` (config) |
| **Input** | Texto perfil construído em `persistence.py` → `_build_profile_text(brand)` |

Exemplo de texto embedado:
```
{Brand Name} is a menswear brand based in {country}. {company_overview} Suit price: approximately €{price}. Operates {N} store(s). Wool: {wool}. [MTM/style/business model se disponível]
```

**Nota:** Não há prompt LLM — é API de embeddings. **1 call por marca**, sequencial.

---

### 21.12 Fora do pipeline principal

#### A) Explicação de similaridade (`vector_db.py` → `generate_similarity_explanation`)

**Não usado** em `score_and_save_node` (importado mas inactive). Usado em `scoring.calculate_prospect_score`.

**Modelo:** GPT-5.1 · **1× por prospect**

```
You are analyzing why a prospect brand is similar to an existing Confeções Lança client.

PROSPECT:
- Name: {name}
- Country: {country}
- Stores: {store_count}
- Price: €{price_eur}
- Wool: {wool}
- Made-to-Measure: {mtm}
- Style: {style}
- Business Model: {business}

LANÇA CLIENT (Most Similar - {similarity_score}% match):
- Name: {client_name}
- Country: {client_country}
- Stores: {client_stores}
- Wool: {client_wool}
- Made-to-Measure: {client_mtm}
- Style: {client_style}
- Business Model: {client_business}
- Profile: {client_profile}

TASK:
Write a brief explanation (2-3 sentences) explaining why these brands are similar.
Focus on:
- Business size and structure (store count)
- Quality positioning (wool percentage, bespoke services)
- Brand positioning and style
- Business model alignment

Be concise and specific. Write in English.

Example format:
"This prospect is similar to [Client Name] because both are small boutique retailers..."

Explanation:
```

#### B) Chat consultor (`routers/chat.py`)

**Modelo:** GPT-5.1 · **1× por mensagem do user**

Estrutura de mensagens:
1. **SystemMessage** — prompt dinâmico com:
   - Missão Lança (PT ou EN conforme `request.language`)
   - Contexto clientes Lança (`client_context`)
   - Prospects da BD filtrados por cidade (`prospect_context`, até 50)
   - Estatísticas dashboard
   - Template de email preferido
   - Regras de formatação (sem markdown decorativo)
2. **Até 10 mensagens** de histórico (user/assistant)
3. **HumanMessage** — pergunta actual

#### C) Email outreach (`email_service.py` → `generate_personalized_outreach`)

**Modelo:** GPT-5.1 · **1× por email gerado** (quando user pede draft personalizado)

```
Write a highly professional B2B partnership proposal email from Confeções Lança (Portuguese quality menswear manufacturer) to {brand.name}.

You MUST use the following structure and content as requested by the client, but you can add small personalizations to make it feel more authentic for {brand.name} in {city}.

BASE TEMPLATE:
Dear [Name/Team],
Having reviewed your brand online, we were very impressed with your retail presence and product offer.
[... template completo Lança ...]
Warm regards

INFO TO USE FOR PERSONALIZATION:
- Target Brand: {brand.name}
- Location: {city}
- Segment: {style}
- Decision Maker: {recipient}

Return ONLY the email body in English. No subject line.
```

---

### 21.13 Tabela resumo — todos os prompts LLM do pipeline

| # | Fase | Função | Modelo | Calls/run (~48 marcas) |
|---|------|--------|--------|------------------------|
| 1 | N1 | Inferir país | mini | 1 |
| 2 | N1 | Gerar queries Exa | mini | 1 |
| 3 | N2 | Filtro KEEP/REMOVE | mini | ~5 |
| 4 | N3 | CityContext | mini | 1 |
| 5 | N3b | Extract estruturado | 5.1 | ~8 |
| 6 | N3c | HQ do site | 5.1 | ~48 |
| 7 | N3c | HQ conhecimento | 5.1 | ~48 |
| 8 | N3c | Equivalência sedes | mini | 0–1 |
| 9 | N3e | Extract lojas | 5.1 | ~40 |
| 10 | N4 | Fit assessment | 5.1 | ~5 |
| — | N4 | Embeddings | embedding API | ~35 |
| **Total LLM chat** | | | | **~155–160** |

---

*Documento gerado para revisão externa. Actualizar quando o pipeline mudar.*
