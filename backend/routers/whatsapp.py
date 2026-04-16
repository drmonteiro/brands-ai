"""
WhatsApp Webhook — Twilio Integration for Consultor IA
=======================================================
Receives incoming WhatsApp messages from Twilio, processes them through
the same RAG pipeline as the web chat, and sends replies back via WhatsApp.

Flow:
  1. User sends WhatsApp message → Twilio forwards to our webhook
  2. We extract the message text and sender number
  3. We call the same chat logic (RAG over prospects DB)
  4. We send the AI response back via Twilio API
  5. User receives the response in WhatsApp

Commands:
  - "cidade [nome]" → Changes the city context (e.g., "cidade Londres")
  - "reset" → Clears conversation history
  - "ajuda" → Shows available commands
"""

from fastapi import APIRouter, Request, Response
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse
from config import Config
from services.database import get_prospects_by_city, get_all_prospects, get_all_searched_cities, get_dashboard_stats
from data.lanca_clients import LANCA_CLIENTS, IDEAL_CLIENT_PROFILE
from agents.nodes.utils import get_llm
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from routers.chat import build_prospect_context, build_client_context, SYSTEM_PROMPT_TEMPLATE
from collections import defaultdict
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

# ============================================================================
# IN-MEMORY SESSION STORE (per-user conversation history)
# ============================================================================
# Key: phone number, Value: { "history": [...], "city": str, "last_active": datetime }
user_sessions: dict = defaultdict(lambda: {
    "history": [],
    "city": None,
    "last_active": datetime.now()
})

MAX_HISTORY = 8  # Keep last 8 messages per user to avoid token overflow
SESSION_TIMEOUT_HOURS = 24  # Auto-clear sessions after 24h of inactivity


def cleanup_old_sessions():
    """Remove sessions older than SESSION_TIMEOUT_HOURS."""
    cutoff = datetime.now() - timedelta(hours=SESSION_TIMEOUT_HOURS)
    expired = [phone for phone, data in user_sessions.items() if data["last_active"] < cutoff]
    for phone in expired:
        del user_sessions[phone]


# ============================================================================
# WHATSAPP WEBHOOK — Receives messages from Twilio
# ============================================================================

@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """
    Twilio sends POST requests here when a user sends a WhatsApp message.
    We process it and return a TwiML response.
    """
    # Parse Twilio's form data
    form_data = await request.form()
    incoming_msg = form_data.get("Body", "").strip()
    from_number = form_data.get("From", "")  # e.g., "whatsapp:+351966134848"
    
    print(f"[WHATSAPP] Message from {from_number}: {incoming_msg}")
    
    # Cleanup old sessions periodically
    cleanup_old_sessions()
    
    # Get or create user session
    session = user_sessions[from_number]
    session["last_active"] = datetime.now()
    
    # ── Handle special commands ──
    msg_lower = incoming_msg.lower().strip()
    
    # Command: "ajuda" or "help"
    if msg_lower in ("ajuda", "help", "comandos", "?"):
        reply_text = (
            "🤖 *Consultor IA Lança — Comandos:*\n\n"
            "📍 *cidade [nome]* — Mudar contexto (ex: _cidade Londres_)\n"
            "🌍 *cidade todas* — Ver dados globais\n"
            "🔄 *reset* — Limpar conversa\n"
            "❓ *ajuda* — Ver este menu\n\n"
            "💡 *Exemplos de perguntas:*\n"
            "• _Quais são as melhores marcas para abordar?_\n"
            "• _Mostra-me marcas com preços abaixo de 800€_\n"
            "• _Quem tem contacto de email disponível?_\n"
            "• _Faz-me um resumo das oportunidades em Londres_"
        )
        return send_twiml_response(reply_text)
    
    # Command: "reset"
    if msg_lower in ("reset", "limpar", "nova conversa"):
        user_sessions[from_number] = {
            "history": [],
            "city": None,
            "last_active": datetime.now()
        }
        return send_twiml_response("✅ Conversa reiniciada.\n\nPodes começar uma nova pergunta ou usar *cidade [nome]* para focar numa cidade.")
    
    # Command: "cidade [name]"
    if msg_lower.startswith("cidade "):
        city_name = incoming_msg[7:].strip()
        if city_name.lower() in ("todas", "global", "all"):
            session["city"] = None
            return send_twiml_response("🌍 Contexto alterado para *Global (Todas as Cidades)*.\n\nPergunta o que quiseres!")
        else:
            session["city"] = city_name
            return send_twiml_response(f"📍 Contexto alterado para *{city_name}*.\n\nAgora as minhas respostas focam-se apenas nas marcas de {city_name}.")
    
    # ── Regular message: Process with RAG ──
    try:
        reply_text = await process_whatsapp_message(incoming_msg, session)
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        import traceback
        traceback.print_exc()
        reply_text = "⚠️ Ocorreu um erro ao processar a tua pergunta. Tenta novamente daqui a pouco."
    
    # Save to history
    session["history"].append({"role": "user", "content": incoming_msg})
    session["history"].append({"role": "assistant", "content": reply_text})
    
    # Trim history
    if len(session["history"]) > MAX_HISTORY * 2:
        session["history"] = session["history"][-(MAX_HISTORY * 2):]
    
    return send_twiml_response(reply_text)


# ============================================================================
# CORE RAG PROCESSING (reuses chat.py logic)
# ============================================================================

async def process_whatsapp_message(message: str, session: dict) -> str:
    """Process a WhatsApp message using the same RAG pipeline as the web chat."""
    
    city = session.get("city")
    
    # 1. Fetch prospect data
    if city:
        prospects_data = await get_prospects_by_city(city, limit=50)
        context_label = f"Marcas prospetadas em {city}"
    else:
        prospects_data = await get_all_prospects(limit=100)
        context_label = "Todas as marcas prospetadas (global)"
    
    # 2. Build context
    prospect_context = build_prospect_context(prospects_data, context_label)
    client_context = build_client_context()
    
    try:
        stats = await get_dashboard_stats()
        cities = await get_all_searched_cities()
        city_names = [c["city"] for c in cities] if cities else []
        stats_context = (
            f"Total de marcas na BD: {stats.get('total_prospects', 0)}\n"
            f"Cidades pesquisadas: {', '.join(city_names) if city_names else 'Nenhuma'}\n"
            f"Score médio global: {stats.get('avg_score', 0):.0f}/100"
        )
    except Exception:
        stats_context = "Estatísticas indisponíveis."
    
    # 3. Build system prompt (same as web chat, with WhatsApp-specific additions)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        prospect_context=prospect_context,
        client_context=client_context,
        stats_context=stats_context
    )
    
    # Add WhatsApp-specific formatting rules
    system_prompt += """
    
═══════════════════════════════════════════
REGRAS ESPECIAIS PARA WHATSAPP:
═══════════════════════════════════════════
- Formata a resposta para WhatsApp: usa *negrito* (não **), _itálico_, e emojis moderados.
- Respostas devem ser CURTAS e DIRETAS (máximo 500 palavras). O utilizador está no telemóvel.
- Usa bullet points com • em vez de listas numeradas longas.
- Se a resposta for muito extensa, dá um resumo e pergunta se quer mais detalhe.
- Nunca uses markdown do tipo ## ou ### — no WhatsApp não funciona.
"""
    
    # 4. Build message chain
    messages = [SystemMessage(content=system_prompt)]
    
    for msg in session.get("history", [])[-MAX_HISTORY * 2:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    
    messages.append(HumanMessage(content=message))
    
    # 5. Generate response (full model for quality)
    llm = get_llm(fast=False)
    response = llm.invoke(messages)
    
    return response.content


# ============================================================================
# TWILIO RESPONSE HELPER
# ============================================================================

def send_twiml_response(text: str) -> Response:
    """Create a TwiML response that Twilio understands."""
    # WhatsApp has a 1600 char limit per message
    # If our response is longer, we truncate with a note
    if len(text) > 1550:
        text = text[:1500] + "\n\n_(resposta cortada — pergunta mais específica para detalhe)_"
    
    resp = MessagingResponse()
    resp.message(text)
    return Response(content=str(resp), media_type="application/xml")
