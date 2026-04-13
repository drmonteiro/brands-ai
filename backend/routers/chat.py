from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from services.database import get_prospects_by_city, get_all_prospects
from agents.nodes.utils import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    city: Optional[str] = None
    history: List[ChatMessage] = []

@router.post("")
async def process_chat(request: ChatRequest):
    try:
        # 1. Fetch Context
        if request.city and request.city.strip().lower() != "todas":
            prospects_data = await get_prospects_by_city(request.city, limit=50)
            context_title = f"Marcas validadas em {request.city}"
        else:
            prospects_data = await get_all_prospects(limit=100)
            context_title = "Todas as marcas validadas (amostra de 100)"
        
        # 2. Format Context for LLM
        context_str = f"=== CONTEXTO DO SISTEMA: {context_title} ===\n"
        if not prospects_data:
            context_str += "Não existem marcas guardadas para os filtros selecionados.\n"
        else:
            for i, p in enumerate(prospects_data):
                context_str += f"{i+1}. Nome: {p.get('name', 'N/A')}\n"
                context_str += f"   - Sede/Lojas: {p.get('headquarters_address', 'N/A')}\n"
                context_str += f"   - Fatos (PVP): {p.get('avg_suit_price_eur', 'N/A')}€\n"
                context_str += f"   - Preços Visíveis: {p.get('prices_visible', False)}\n"
                context_str += f"   - Só por Marcação: {p.get('is_appointment_only', False)}\n"
                context_str += f"   - Score Lança AI: {p.get('final_score', 'N/A')}\n"
                context_str += f"   - Link: {p.get('website_url', 'N/A')}\n\n"

        # 3. Build Prompt
        system_prompt = f"""
        És o Consultor IA da Confeções Lança, um especialista em mercado premium de moda masculina (b2b).
        A tua função é analisar a base de dados de leads extraídas e responder às dúvidas do comercial de forma direta, analítica e concisa.
        Usa SEMPRE português europeu. 
        
        {context_str}
        
        REGRAS IMPORTANTES:
        - Os limites de preço alvo da Lança são fatos entre 500€ e 2300€. Se o user perguntar quais as marcas fora do target, avisa que o sistema filtra automaticamente os outliers, mas analisa os dados acima.
        - Quando mencionares uma marca, podes incluir o Link se relevante e o preço médio dos fatos.
        - Se a pergunta não for sobre as marcas, responde de forma educada mas volta o tema para as marcas.
        - Sê muito direto, escrevendo em parágrafos curtos ou bullet points.
        """

        messages = [SystemMessage(content=system_prompt)]
        
        # Add history
        for msg in request.history:
            # We skip system messages in history to focus on user/assistant
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                # For simplicity here we just use HumanMessage with a prefix, or properly mapped
                messages.append(HumanMessage(content=f"Assistant: {msg.content}"))
        
        # Add current message
        messages.append(HumanMessage(content=request.message))

        # 4. Generate Response
        llm = get_llm(fast=True)  # Using fast model (e.g. gpt-4o-mini) for chat speed
        response = llm.invoke(messages)

        return {"response": response.content}
        
    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
