# 👔 Confeções Lança - Backend AI Architecture
## Sistema de Prospecção Inteligente de Mercado

Este documento descreve o fluxo técnico detalhado do backend, desde o momento em que uma cidade é introduzida no UI até à persistência final dos leads qualificados.

---

## 🏗️ Estrutura de Pastas (v1.1.0)
A partir da versão 1.1.0, o backend foi modularizado para maior escalabilidade:

```text
backend/
├── agents/             # Orquestração LangGraph
│   ├── nodes/          # Lógica individual de cada nó do Grafo
│   │   ├── initializer.py  # Geração de queries e cache
│   │   ├── discovery.py    # Busca web (Tavily)
│   │   ├── validator.py    # Filtro LLM + Scoring
│   │   └── persistence.py  # Guardar em base de dados
│   ├── graph.py        # Definição e compilação do Workflow
│   └── utils.py        # Utilitários partilhados do agente
├── routers/            # Endpoints da API (FastAPI Routers)
├── services/           # Lógica de negócio de baixo nível
├── main.py             # Ponto de entrada
```

## 🏗️ Arquitetura Core
O sistema é construído sobre uma arquitetura de **Grafo de Agentes** usando **LangGraph**, que permite um fluxo de trabalho cíclico e com memória.

*   **Framework**: FastAPI
*   **Orquestração**: LangGraph (Stateful Workflow)
*   **Persistência de Estado**: **PostgresSaver** (Checkpointing persistente)
*   **Inteligência**: Azure OpenAI (GPT-4o)
*   **Busca Web**: Tavily AI (Otimizado para LLMs)
*   **Base de Dados**: PostgreSQL 16 + pgvector

---

## 🌊 Fluxo de Execução Step-by-Step

### 1. Entrada de Dados (`main.py`)
A jornada começa com um `POST /api/prospect`.
*   O sistema verifica na base de dados PostgreSQL se a cidade já foi pesquisada (Cache).
*   Se existir cache e o utilizador não forçar o refresh, os resultados são devolvidos instantaneamente.
*   Caso contrário, é instanciado um novo **Thread ID** e o Grafo LangGraph é iniciado.

### 2. Nó: Inicialização (`initialize_search`)
O primeiro nó do grafo prepara o terreno:
*   **Cálculo de Câmbio**: Obtém o rácio EUR/USD em tempo real.
*   **Definição de Parâmetros**: Define thresholds de preço baseados no perfil histórico da Lança.
*   **Geração de Queries**: O LLM gera 5 a 10 queries de pesquisa altamente específicas (ex: *"bespoke tailors in London"*, *"premium menswear boutiques Mayfair"*).

### 3. Nó: Descoberta (`discovery_node`)
Este nó é o "explorador" do sistema.
*   **Execução de Busca**: Usa a API do Tavily para executar as queries geradas.
*   **Filtragem de URLs**: Remove sites de notícias, diretórios genéricos (Yelp, TripAdvisor) e foca-se apenas em domínios oficiais de marcas.
*   **Deduplicação Agressiva**: Garante que a mesma marca não seja processada várias vezes.

### 4. Nó: Validação & Extração (`validation_node`)
O nó mais complexo e "inteligente" do sistema. Para cada URL encontrada:

*   **A. Scraping & Limpeza**: Extrai o conteúdo raw do site e limpa o ruído HTML.
*   **B. Deep Pricing Discovery**: Se o preço não for encontrado na homepage, o agente navega automaticamente para páginas de "Shop" ou "Suits" para encontrar valores monetários.
*   **C. Extração LLM (GPT-4o)**: Um agente especializado analisa o conteúdo para extrair:
    *   Número de lojas físicas.
    *   Preço médio de um fato.
    *   Composição de materiais (Foco em **100% Lã**).
    *   Posicionamento de mercado (Luxury vs Contemporary).
*   **D. Scoring Semântico (pgvector)**: 
    *   O perfil da marca é comparado com os **18 clientes reais** da Lança guardados na base de dados vectorial.
    *   É gerado um **Similarity Score** e uma explicação textual da semelhança.
*   **E. Cálculo de Fit Score (0-100)**: Uma fórmula ponderada avalia Preço, Localização, Estilo e Tamanho da empresa.

### 5. Intervenção Humana (Breakpoints)
O grafo interrompe a execução em dois pontos críticos para aprovação do utilizador:
1.  **Após a Descoberta**: Para validar se as marcas encontradas fazem sentido.
2.  **Antes da Persistência**: Para selecionar quais sãos os alvos finais para envio de proposta.

### 6. Nó: Persistência (`filter_node`)
O passo final de consolidação.
*   **Normalização**: Todos os dados são convertidos para um formato relacional rigoroso.
*   **Escrita em Disco**: Os dados são guardados na tabela `prospects` do PostgreSQL.
*   **Logs Técnicos**: É registado o log de verificação para auditoria futura.

---

## 🛠️ Tecnologias de Dados e IA

### Base de Dados Vectorial (pgvector)
Não guardamos apenas texto; guardamos "significado". No arranque, o sistema lê o ficheiro `lanca_clients.py`, gera embeddings para os clientes ideais e guarda-os na tabela `lanca_clients`. Isto permite que o sistema "saiba" o que é um bom cliente para a Lança sem estar programado de forma rígida.

### Extração de Preços (Double-Hop Logic)
O backend não desiste se não vir um preço. Ele implementa uma lógica de "salto":
1.  Verifica Homepage.
2.  Se falhar, procura links de produtos.
3.  Se falhar, faz uma pesquisa específica no Google/Tavily focada em *"brand name suit price"*.

---

## 📊 Estrutura de Resposta do Agente (JSON)
Cada prospecto é entregue ao frontend com esta anatomia:
```json
{
  "name": "Bespoke Tailor Ltd",
  "avgPrice": 1200,
  "woolPercentage": "Confirmado 100% Lã",
  "storeCount": 2,
  "locationQuality": "premium",
  "similarityScore": 85.5,
  "fitScore": 92.0,
  "detailedDescription": "Análise técnica detalhada...",
  "verificationLog": ["...", "..."]
}
```

---
*Documentação gerada automaticamente para o Sistema de Gestão Lança AI v2.5*
