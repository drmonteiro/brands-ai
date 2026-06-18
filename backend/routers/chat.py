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
        hq_city = p.get("headquarters_city", "N/A")
        hq_conf = p.get("headquarters_confidence", "unknown")
        local_store = p.get("local_store_address", "N/A")
        city_presence = p.get("city_presence_type", "unknown")
        store_conf = p.get("store_count_confidence", "unknown")
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
        
        price_note = p.get("price_note", "")
        
        lines.append(f"BRAND: {name.upper()}")
        lines.append(f"- Location: {city}, {country} | HQ: {hq_city} ({hq_conf}) | Local store: {local_store}")
        lines.append(f"- Presence: {city_presence} | Store count confidence: {store_conf}")
        lines.append(f"- Digital: {url}")
        lines.append(f"- Business: {store_count} stores | {style} style | {model}")
        lines.append(f"- Product: Avg Price {price}€ | MTM: {mtm} | Heritage: {heritage} | Appt Only: {appt_only} | Price Note: {price_note if price_note else 'N/A'}")
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
Ajuda a equipa comercial a analisar os dados de prospeção. Deves ser profissional, analítico e garantir que a informação é apresentada de forma limpa e estruturada.

CONTEXTO LANÇA:
- Fábrica portuguesa de alfaiataria de alta qualidade (B2B), **situada em Vales do Rio, Covilhã, Portugal** (desde 1973).
- Fatos (500€-2300€), Casacos (300€-1380€), Calças (200€-920€).
- Mercado alvo: Boutiques premium (1-20 lojas).

{client_context}

---
DADOS DE PROSPEÇÃO:
{prospect_context}

---
ESTATÍSTICAS GERAIS:
{stats_context}

---
MODELO DE EMAIL PREFERIDO:
"Dear [Name/Team],
Having reviewed your brand online, we were very impressed with your retail presence and product offer.
I’m writing to introduce a tailoring manufacturer based in central Portugal. Established in 1973, the company has extensive experience supplying own-label garments to global brands, retail groups, and independent businesses.
We bring a strong depth of expertise, combining flexibility with consistent quality and service, along with pricing that supports healthy margins. With many clients based in the UK, we’ve developed a refined level of make, as well as the ability to respond to more demanding product development briefs.
We offer two levels of jacket construction: canvas fused and traditional half canvas with a padded lapel. Production can be developed from in-house blocks or created entirely to your direction. In addition, we manufacture completely unstructured jackets, as well as formal and casual trousers, waistcoats, and coats, primarily in wool blends. Should you have any other specific styles in mind, we would be very happy to review and develop these with you.
We believe this could represent a strong partnership in producing high-quality garments and would welcome the opportunity to explore this further. I’d be happy to arrange a short 15-minute call to introduce things in more detail and discuss potential collaboration.
Thank you for your time, and I look forward to hearing from you.
Warm regards"

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
            city_name = request.city.strip()
            prospects_data = await get_prospects_by_city(city_name, limit=50)
            context_label = f"Marcas prospetadas em {city_name}"
        else:
            prospects_data = await get_all_prospects(limit=100)
            context_label = "Todas as marcas prospetadas (global)"

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

        # ── 3. Dynamic System Prompt based on Language ──
        if request.language == "en":
            lang_rules = """
            - ALWAYS respond in English.
            - Use professional business terminology.
            - Structure: Use clear headers, capitalized brand names, and bullet points.
            - Formatting: NEVER use asterisks (**), dashes (---), or hashes (###) in your response. Keep it completely clean without decorative markdown. Let capitals and line breaks do the formatting.
            """
            mission = "You are the AI Consultant for Confeções Lança, a specialized B2B assistant for premium tailoring."
            context_label_prefix = "Prospecting data"
        else:
            lang_rules = """
            - RESPONDE SEMPRE em Português Europeu (PT-PT).
            - Estilo: Direto, analítico e profissional.
            - Estrutura: Usa texto limpo e texto em MAIÚSCULAS para dar ênfase. Usa listas com pontos normais (•).
            - Formatação PROIBIDA: NÃO USES asteriscos (**), não uses separadores tipo (---) e não uses cardinais (###). O teu output tem de ser limpo e profissional, apenas com parágrafos e pontos.
            """
            mission = "Tu és o Consultor IA da Confeções Lança, um assistente de inteligência comercial especializado em alfaiataria premium."
            context_label_prefix = "Dados de prospecção"

        # Construct full prompt directly to avoid .format() issues
        system_prompt = f"""
{mission}

MISSÃO:
Ajuda a equipa comercial a analisar os dados de prospeção. Deves ser profissional e garantir que a informação é apresentada de forma limpa.

CONTEXTO LANÇA:
- Fábrica portuguesa de alfaiataria de alta qualidade (B2B), situada em Vales do Rio, Covilhã, Portugal (desde 1973).
- Fatos (500€-2300€), Casacos (300€-1380€), Calças (200€-920€).
- Mercado alvo: Boutiques premium (1-20 lojas).

{client_context}

{context_label_prefix}:
{prospect_context}

ESTATÍSTICAS GERAIS:
{stats_context}

MODELO DE EMAIL PREFERIDO (Para propostas de parceria):
Deves seguir este tom e estrutura se te pedirem para rascunhar um email:
"Dear [Name/Team],
Having reviewed your brand online, we were very impressed with your retail presence and product offer.
I’m writing to introduce a tailoring manufacturer based in central Portugal. Established in 1973, the company has extensive experience supplying own-label garments to global brands, retail groups, and independent businesses.
We bring a strong depth of expertise, combining flexibility with consistent quality and service, along with pricing that supports healthy margins. With many clients based in the UK, we’ve developed a refined level of make, as well as the ability to respond to more demanding product development briefs.
We offer two levels of jacket construction: canvas fused and traditional half canvas with a padded lapel. Production can be developed from in-house blocks or created entirely to your direction. In addition, we manufacture completely unstructured jackets, as well as formal and casual trousers, waistcoats, and coats, primarily in wool blends. Should you have any other specific styles in mind, we would be very happy to review and develop these with you.
We believe this could represent a strong partnership in producing high-quality garments and would welcome the opportunity to explore this further. I’d be happy to arrange a short 15-minute call to introduce things in more detail and discuss potential collaboration.
Thank you for your time, and I look forward to hearing from you.
Warm regards"

REGRAS DE COMUNICAÇÃO:
{lang_rules}
5. Se mencionares marcas, estrutura o texto sem usar asteriscos:
   • NOME DA MARCA | Preço: X€ | Score: X/100 | Website
6. Sê conciso. O utilizador quer informação rápida e acionável.
7. Se a informação sobre uma marca específica não estiver na nossa BD, usa o teu conhecimento interno para descrever a marca e posicionamento.
8. Assume um papel proativo e estratégico para ajudar o comercial.
9. NÃO és APENAS um assistente da Lança — és um consultor de moda masculina e mercado B2B em geral.
   O utilizador pode perguntar sobre QUALQUER marca, mercado, tendência, país, ou tema da indústria de menswear.
   Responde com o teu conhecimento geral quando a pergunta for sobre temas fora da BD da Lança (ex: "como funciona o mercado de fatos em Itália?", "quem é a Canali?", "quais são as tendências de alfaiataria em 2026?").
   Usa a BD da Lança quando disponível, mas complementa SEMPRE com o teu conhecimento do mercado.
"""

        messages = [SystemMessage(content=system_prompt)]

        # Add history
        for msg in request.history[-10:]:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        messages.append(HumanMessage(content=request.message))

        llm = get_llm(fast=False)
        response = llm.invoke(messages)
        ai_content = response.content

        # ── 4. Save Assistant Message to DB ──
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
