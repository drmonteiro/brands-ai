import asyncio
from typing import Optional, Tuple, Dict, Any
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.callbacks import get_openai_callback
from openai import LengthFinishReasonError

from services.extraction.css_extractor import ExtractedBoutiqueData
from config import Config
import logging

logger = logging.getLogger(__name__)

# Max 2 concurrent LLM calls to avoid Azure rate limiting (429 → exponential backoff stalls)
_llm_semaphore = asyncio.Semaphore(2)

# Retries when the model stops early (output length / reasoning)
_MAX_LLM_RETRIES = 3
_INITIAL_BACKOFF_SEC = 1.5

SYSTEM_PROMPT = """És um extractor de dados especializado em boutiques de \
moda masculina premium. A tua tarefa é extrair informação estruturada \
sobre uma marca/boutique a partir do conteúdo do seu site.

CONTEXTO DO NEGÓCIO:
Estamos a avaliar boutiques como potenciais clientes para uma fábrica \
de fatos de luxo. Procuramos boutiques que vendam fatos entre 500€ e \
2500€, com 1 a 20 lojas físicas independentes.

FORMATO DO CONTEÚDO:
O conteúdo abaixo vem de MÚLTIPLAS PÁGINAS do mesmo site, separadas \
por linhas "--- HOMEPAGE PAGE ---", "--- PRODUCT PAGE ---", \
"--- STORE PAGE ---", etc. Trata todo o conteúdo como sendo da MESMA \
marca/boutique.

REGRAS DE EXTRAÇÃO:

1. PREÇOS:
   - Extrai APENAS preços de fatos completos, blazers, ou casacos formais
   - Procura preços principalmente nas secções PRODUCT PAGE
   - IGNORA preços de acessórios (gravatas, lenços, cintos), camisas \
soltas, ou produtos não-formais
   - Normaliza para EUR quando possível, mas mantém a moeda original \
no campo "currency"
   - Se vires gamas tipo "from €500" ou "€500-€800", extrai o valor \
mais baixo
   - Preços plausíveis para fatos: entre 200€ e 5000€. Se vires algo \
fora deste range, é provavelmente erro de parsing — não extraias

2. STORE ADDRESSES:
   - Extrai APENAS lojas físicas próprias da marca, NÃO retailers \
terceiros que vendem a marca
   - Procura moradas principalmente nas secções STORE PAGE e HOMEPAGE PAGE
   - Se vires uma página "Stockists" ou "Where to buy" com lista de \
outras lojas, IGNORA — isso são revendedores, não pontos de venda \
próprios
   - Para cada loja: morada completa, cidade, país. País obrigatório
   - Se a marca menciona "flagship store" ou "boutique", essa é \
prioritária

3. BRAND_NAME:
   - Nome oficial da marca, não slogan
   - Procura principalmente na secção HOMEPAGE PAGE
   - Prefere o que aparece no logo/header ou em meta tags og:site_name
   - NÃO uses o domínio (ex: "hawesandcurtis" → "Hawes & Curtis")

4. PRINCÍPIO GERAL — NÃO INVENTES:
   - Se um campo não estiver claramente presente no conteúdo, devolve \
null/lista vazia
   - É MUITO melhor devolver vazio do que adivinhar
   - Não infiras preços a partir de "premium" ou "luxury" — só extrai \
o que está escrito

5. OWNER / DECISOR:
   - Extrai o nome do fundador, owner, CEO, ou director da marca
   - Procura em qualquer secção (About, Team, Our Story, Contact, Footer)
   - Se houver múltiplos, prefere o mais sénior (CEO > Director > Manager)
   - Extrai também o cargo (owner_role): Founder, CEO, Owner, Director, etc.
   - Se não encontrares nenhum nome específico, devolve null"""


def build_user_prompt(
    markdown: str,
    partial_extraction: Optional[ExtractedBoutiqueData] = None,
    missing_fields: Optional[list[str]] = None,
) -> str:
    """
    Constrói o prompt do utilizador, opcionalmente com contexto de
    extração parcial já feita pela Camada 1 (CSS).
    """
    parts = []

    if partial_extraction and missing_fields:
        already_extracted = []
        if partial_extraction.prices and "prices" not in missing_fields:
            already_extracted.append(
                f"- prices: {partial_extraction.prices}"
            )
        if (
            partial_extraction.store_addresses
            and "store_addresses" not in missing_fields
        ):
            already_extracted.append(
                f"- store_addresses: "
                f"{len(partial_extraction.store_addresses)} lojas já extraídas"
            )
        if (
            partial_extraction.brand_name
            and "brand_name" not in missing_fields
        ):
            already_extracted.append(
                f"- brand_name: {partial_extraction.brand_name}"
            )

        if already_extracted:
            parts.append(
                "Já foram extraídos os seguintes campos via análise "
                "estruturada (NÃO os re-extraias, mantém os valores exatos):"
            )
            parts.extend(already_extracted)
            parts.append("")

        parts.append(
            f"Extrai APENAS os seguintes campos em falta a partir do "
            f"conteúdo abaixo: {', '.join(missing_fields)}"
        )
    else:
        parts.append("Extrai todos os campos relevantes a partir do conteúdo abaixo.")

    parts.append("")
    parts.append("---")
    parts.append("CONTEÚDO DO SITE:")
    parts.append("---")
    parts.append(markdown)

    return "\n".join(parts)


class LLMExtractor:
    def __init__(self):
        self.deployment_name = Config.AZURE_OPENAI_EXTRACTION_DEPLOYMENT
        self.llm = AzureChatOpenAI(
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION,
            azure_deployment=self.deployment_name,
            temperature=1,
            max_tokens=20000,
            timeout=180,
            reasoning_effort="low",
        ).with_structured_output(ExtractedBoutiqueData)

    async def extract(
        self,
        markdown: str,
        partial_extraction: Optional[ExtractedBoutiqueData] = None,
        missing_fields: Optional[list[str]] = None,
    ) -> Tuple[ExtractedBoutiqueData, Dict[str, Any]]:
        """
        Extrai dados estruturados de um markdown via GPT (structured output).
        Devolve (ExtractedBoutiqueData, token_usage_dict).
        Em falha total devolve ExtractedBoutiqueData() vazio.
        """
        user_prompt = build_user_prompt(
            markdown=markdown,
            partial_extraction=partial_extraction,
            missing_fields=missing_fields,
        )

        if markdown and len(markdown) > 12000:
            logger.warning("Markdown truncado de %s para 12000 chars", len(markdown))
            user_prompt = user_prompt[:12000 + 2000]

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "{user_input}"),
        ])

        chain = prompt | self.llm
        token_usage: Dict[str, Any] = {}

        last_error: Optional[Exception] = None
        for attempt in range(_MAX_LLM_RETRIES):
            try:
                async with _llm_semaphore:
                    logger.info(
                        "[LLM_EXTRACTOR] extraction starting (model=%s, attempt=%s/%s)",
                        self.deployment_name,
                        attempt + 1,
                        _MAX_LLM_RETRIES,
                    )
                    with get_openai_callback() as cb:
                        result = await chain.ainvoke({"user_input": user_prompt})
                        token_usage = {
                            "prompt_tokens": cb.prompt_tokens,
                            "completion_tokens": cb.completion_tokens,
                            "total_tokens": cb.total_tokens,
                            "cost_usd": cb.total_cost,
                        }

                logger.info(
                    "[LLM_EXTRACTOR] OK — prices=%s stores=%s brand=%s | tokens=%s cost=$%.4f",
                    len(result.prices or []),
                    len(result.store_addresses or []),
                    result.brand_name,
                    token_usage.get("total_tokens", 0),
                    float(token_usage.get("cost_usd", 0) or 0),
                )
                return result, token_usage
            except LengthFinishReasonError as e:
                last_error = e
                wait = _INITIAL_BACKOFF_SEC * (2 ** attempt)
                logger.warning(
                    "[LLM_EXTRACTOR] LengthFinishReasonError (attempt %s/%s): %s — backoff %.1fs",
                    attempt + 1,
                    _MAX_LLM_RETRIES,
                    e,
                    wait,
                )
                await asyncio.sleep(wait)
            except Exception as e:
                last_error = e
                logger.error("[LLM_EXTRACTOR] extraction failed: %s", e, exc_info=True)
                break

        logger.error(
            "[LLM_EXTRACTOR] giving empty ExtractedBoutiqueData after failure: %s",
            last_error,
        )
        fallback = partial_extraction if partial_extraction is not None else ExtractedBoutiqueData()
        return fallback, {"total_tokens": 0, "cost_usd": 0.0, "error": str(last_error)}


llm_extractor = LLMExtractor()
