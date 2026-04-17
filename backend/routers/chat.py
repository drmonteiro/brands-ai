"""
Consultor IA — RAG Chat System for Confeções Lança
===================================================
High-quality conversational AI that answers questions about prospected brands
using real data from the PostgreSQL database (prospects table).

Architecture:
  1. User sends a message (+ optional city filter + conversation history)
  2. Backend fetches ALL relevant prospect data from DB (full RAG context)
  3. Data is formatted into a rich, structured context block
  4. A carefully engineered system prompt positions the AI as a Lança commercial analyst
  5. GPT-5.1 (full model, not mini) generates a high-quality, data-grounded response
  6. Response is returned with the city list for the frontend dropdown
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from services.database import (
    get_prospects_by_city, 
    get_all_prospects, 
    get_all_searched_cities,
    get_dashboard_stats
)
from services.postgres import PostgresManager
from data.lanca_clients import LANCA_CLIENTS, IDEAL_CLIENT_PROFILE
from agents.nodes.utils import get_llm
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ============================================================================
# SCHEMAS
# ============================================================================

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    city: Optional[str] = None
    language: str = "pt"  # "pt" or "en"
    history: List[ChatMessage] = []


# ============================================================================
# CONTEXT BUILDER — Transforms DB rows into rich LLM context
# ============================================================================

def build_prospect_context(prospects: list, context_label: str) -> str:
    """
    Transforms a list of prospect dicts from the DB into a structured
    text block that the LLM can reason over accurately.
    """
    if not prospects:
        return f"📭 {context_label}: Nenhuma marca encontrada na base de dados para este filtro.\n"

    lines = [f"📊 {context_label} — {len(prospects)} marcas encontradas:\n"]    
    lines.append("=" * 60)

    for i, p in enumerate(prospects, 1):
        name = p.get("name", "N/A")
        city = p.get("city", "N/A")
        country = p.get("country", "N/A")
        url = p.get("website_url", "N/A")
        hq = p.get("headquarters_address", "N/A")
        price = p.get("avg_suit_price_eur", 0)
        store_count = p.get("store_count", 0)
        style = p.get("brand_style", "N/A")
        model = p.get("business_model", "N/A")
        overview = p.get("company_overview", "")
        description = p.get("detailed_description", "")
        mtm = "Sim" if p.get("made_to_measure") else "Não"
        heritage = "Sim" if p.get("heritage_brand") else "Não"
        appt_only = "Sim" if p.get("is_appointment_only") else "Não"
        
        # Scores
        final_score = p.get("final_score", 0)
        fit_score = p.get("fit_score", 0)
        
        # Similar client
        similar_client = p.get("most_similar_client", "N/A")
        similarity_explanation = p.get("similarity_explanation", "")
        
        # Contact
        contact_name = p.get("contact_name") or "N/A"
        contact_email = p.get("contact_email") or "N/A"
        
        lines.append(f"BRAND: {name.upper()}")
        lines.append(f"- Location: {city}, {country} | HQ: {hq}")
        lines.append(f"- Digital: {url}")
        lines.append(f"- Business: {store_count} stores | {style} style | {model}")
        lines.append(f"- Product: Avg Price {price}€ | MTM: {mtm} | Heritage: {heritage} | Appt Only: {appt_only}")
        lines.append(f"- Scores: Final {final_score}/100 | Fit {fit_score}")
        lines.append(f"- Similarity: Matches {similar_client} ({similarity_explanation[:150] if similarity_explanation else 'N/A'})")
        lines.append(f"- Sales Lead: {contact_name} | Email: {contact_email}")
        lines.append(f"- Description: {(overview or description)[:200]}")
        lines.append("-" * 30)

    return "\n".join(lines)


def build_client_context() -> str:
    """Build context about existing Lança clients for reference."""
    lines = ["📋 CLIENTES ATUAIS DA LANÇA (18 parceiros):"]
    for c in LANCA_CLIENTS:
        suit_price = c.get("pvp_suits_eur", "N/A")
        lines.append(f"  • {c['name']} ({c['city']}, {c['country']}) — Fatos: {suit_price}€ | {c.get('store_count', '?')} lojas | Tier: {c.get('tier', 'N/A')}")
    
    profile = IDEAL_CLIENT_PROFILE
    lines.append(f"\n🎯 PERFIL IDEAL: {profile['avg_store_count']} lojas média, PVP médio {profile['avg_pvp_eur']}€")
    return "\n".join(lines)


# ============================================================================
# SYSTEM PROMPT — The "brain" of the Consultor IA
# ============================================================================

SYSTEM_PROMPT_TEMPLATE = """
Tu és o **Consultor IA da Confeções Lança**, um assistente de inteligência comercial especializado em alfaiataria premium.

MISSÃO:
Ajuda a equipa comercial a analisar os dados de prospecção. Deves ser profissional, analítico e garantir que a informação é apresentada de forma limpa e estruturada.

CONTEXTO LANÇA:
- Fábrica portuguesa de alfaiataria de alta qualidade (B2B).
- Fatos (500€-2300€), Casacos (300€-1380€), Calças (200€-920€).
- Mercado alvo: Boutiques premium (1-20 lojas).

{client_context}

---
DADOS DE PROSPECÇÃO:
{prospect_context}

---
ESTATÍSTICAS GERAIS:
{stats_context}

---
REGRAS DE FORMATAÇÃO E COMUNICAÇÃO (OBRIGATÓRIO):
1. Responde em Português Europeu (PT-PT).
2. Usa Markdown profissional: **negritos** para nomes, listas com • e tabelas se necessário.
3. ESTILO LIMPO: Não uses caracteres estranhos (como desenhos de caixas ou barras decorativas longas).
4. ESTRUTURA: Divide a resposta em secções claras com títulos curtos.
5. Se mencionares marcas, estrutura assim:
   • **NOME** | Preço: X€ | Score: X/100 | [Website]
6. Sê conciso. O utilizador quer informação rápida e acionável.
7. Nunca inventes dados. Se não souberes, diz "Informação não disponível".
"""


# ============================================================================
# CHAT ENDPOINT
# ============================================================================

@router.get("/history")
async def get_chat_history(limit: int = 50):
    """Retrieve chat history from PostgreSQL."""
    try:
        pool = await PostgresManager.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT role, content, city_context, created_at 
                FROM chat_messages 
                ORDER BY created_at ASC 
                LIMIT $1
            """, limit)
            return {"history": [dict(row) for row in rows]}
    except Exception as e:
        print(f"[CHAT HISTORY ERROR] {e}")
        return {"history": []}

@router.delete("/history")
async def clear_chat_history():
    """Delete all chat history from PostgreSQL."""
    try:
        pool = await PostgresManager.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM chat_messages")
            return {"status": "success", "message": "Chat history cleared"}
    except Exception as e:
        print(f"[CHAT CLEAR ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def process_chat(request: ChatRequest):
    try:
        # ── 1. Save User Message to DB ──
        pool = await PostgresManager.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_messages (role, content, city_context) VALUES ($1, $2, $3)",
                "user", request.message, request.city
            )

        # ── 2. Fetch prospect data (RAG retrieval) ──
        if request.city and request.city.strip().lower() not in ("todas", "global", "all", ""):
            city = request.city.strip()
            prospects_data = await get_prospects_by_city(city, limit=50)
            context_label = f"Marcas prospetadas em {city}"
        else:
            prospects_data = await get_all_prospects(limit=100)
            context_label = "Todas as marcas prospetadas (global)"

        # ... (rest of the logic remains similar but we load history from DB if requested)
        # For simplicity, we keep the history from request but we'll prioritize DB in the next frontend update
        
        prospect_context = build_prospect_context(prospects_data, context_label)
        client_context = build_client_context()
        
        try:
            stats = await get_dashboard_stats()
            cities_data = await get_all_searched_cities()
            city_names = [c["city"] for c in cities_data] if cities_data else []
            stats_context = (
                f"Total de marcas na BD: {stats.get('total_prospects', 0)}\n"
                f"Cidades pesquisadas: {', '.join(city_names) if city_names else 'Nenhuma'}\n"
                f"Score médio global: {stats.get('avg_score', 0):.0f}/100"
            )
        except Exception:
            stats_context = "Estatísticas indisponíveis."

        # 3. Dynamic System Prompt based on Language
        if request.language == "en":
            lang_rules = """
            - ALWAYS respond in English.
            - Use professional business terminology.
            - Structure: Use clear headers, bold brand names, and bullet points.
            - Formatting: Use **bold** for emphasis and clean Markdown.
            """
            mission = "You are the **AI Consultant for Confeções Lança**, a specialized B2B assistant for premium tailoring."
            context_label_prefix = "Prospecting data"
        else:
            lang_rules = """
            - RESPONDE SEMPRE em Português Europeu (PT-PT).
            - Estilo: Direto, analítico e profissional.
            - Estrutura: Usa Markdown limpo, **negritos** para nomes e listas com pontos •.
            - Não uses caracteres estranhos ou barras decorativas longas.
            """
            mission = "Tu és o **Consultor IA da Confeções Lança**, um assistente de inteligência comercial especializado em alfaiataria premium."
            context_label_prefix = "Dados de prospecção"

        system_prompt = f"""
{mission}

MISSÃO:
Ajuda a equipa comercial a analisar os dados de prospecção. Deves ser profissional e garantir que a informação é apresentada de forma limpa.

CONTEXTO LANÇA:
- Fábrica portuguesa de alfaiataria de alta qualidade (B2B), **situada em Lousada, Portugal** (desde 1973).
- Fatos (500€-2300€), Casacos (300€-1380€), Calças (200€-920€).
- Mercado alvo: Boutiques premium (1-20 lojas).

{{client_context}}

---
{context_label_prefix}:
{{prospect_context}}

---
ESTATÍSTICAS GERAIS:
{{stats_context}}

---
REGRAS DE COMUNICAÇÃO:
{lang_rules}
5. Se mencionares marcas, estrutura assim:
   • **NOME** | Preço: X€ | Score: X/100 | [Website]
6. Sê conciso. O utilizador quer informação rápida e acionável.
7. Se a informação sobre uma marca específica **não estiver na nossa BD**, não digas apenas "não disponível". Usa o teu conhecimento interno para descrever a marca, o seu posicionamento e como a Lança a poderia abordar, deixando claro que esses dados são baseados no teu conhecimento geral e não na prospecção recente.
8. Assume um papel proativo: o teu objetivo é ajudar o comercial a fechar negócio, por isso tenta sempre dar uma resposta útil e estratégica.
9. Mantém o rigor técnico, mas sê criativo nas sugestões de abordagem.
"""
        final_system_prompt = system_prompt.format(
            prospect_context=prospect_context,
            client_context=client_context,
            stats_context=stats_context
        )

        messages = [SystemMessage(content=final_system_prompt)]

        for msg in request.history[-10:]:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        messages.append(HumanMessage(content=request.message))

        llm = get_llm(fast=False)
        response = llm.invoke(messages)
        ai_content = response.content

        # ── 3. Save Assistant Message to DB ──
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_messages (role, content, city_context) VALUES ($1, $2, $3)",
                "assistant", ai_content, request.city
            )

        return {"response": ai_content}

    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CITIES LIST — For the frontend dropdown
# ============================================================================

@router.get("/cities")
async def get_chat_cities():
    """Return list of cities that have been searched (for the dropdown filter)."""
    try:
        cities = await get_all_searched_cities()
        city_list = [{"name": c["city"], "count": c["total_prospects"]} for c in cities]
        return {"cities": city_list}
    except Exception as e:
        print(f"[CHAT CITIES ERROR] {e}")
        return {"cities": []}
