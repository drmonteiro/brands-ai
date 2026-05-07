from typing import Optional, Tuple, Dict, Any
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.callbacks import get_openai_callback
from services.extraction.css_extractor import ExtractedBoutiqueData
from config import Config
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """És um extractor de dados especializado em boutiques de \
moda masculina premium. A tua tarefa é extrair informação estruturada \
sobre uma marca/boutique a partir do conteúdo do seu site.

CONTEXTO DO NEGÓCIO:
Estamos a avaliar boutiques como potenciais clientes para uma fábrica \
de fatos de luxo. Procuramos boutiques que vendam fatos entre 500€ e \
2500€, com 1 a 20 lojas físicas independentes.

REGRAS DE EXTRAÇÃO:

1. PREÇOS:
   - Extrai APENAS preços de fatos completos, blazers, ou casacos formais
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
   - Se vires uma página "Stockists" ou "Where to buy" com lista de \
outras lojas, IGNORA — isso são revendedores, não pontos de venda \
próprios
   - Para cada loja: morada completa, cidade, país. País obrigatório
   - Se a marca menciona "flagship store" ou "boutique", essa é \
prioritária

3. BRAND_NAME:
   - Nome oficial da marca, não slogan
   - Prefere o que aparece no logo/header ou em meta tags og:site_name
   - NÃO uses o domínio (ex: "hawesandcurtis" → "Hawes & Curtis")

4. PRINCÍPIO GERAL — NÃO INVENTES:
   - Se um campo não estiver claramente presente no conteúdo, devolve \
null/lista vazia
   - É MUITO melhor devolver vazio do que adivinhar
   - Não infiras preços a partir de "premium" ou "luxury" — só extrai \
o que está escrito"""


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
    # TODO: Migrar para deployment GPT-4o-mini dedicado para reduzir
    # custos de extração (~5x menos tokens sem reasoning overhead).
    # Quando migrar, reverter: temperature=0.0, max_tokens=2000,
    # timeout=60. Ver decisão técnica em docs/migrations/

    def __init__(self):
        self.deployment_name = Config.AZURE_OPENAI_EXTRACTION_DEPLOYMENT
        self.llm = AzureChatOpenAI(
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION,
            azure_deployment=self.deployment_name,
            temperature=1,  # Mandatory 1 for this deployment (O1-style)
            max_tokens=12000, # Increased for O1 reasoning tokens
            timeout=120,
        ).with_structured_output(ExtractedBoutiqueData)

    async def extract(
        self,
        markdown: str,
        partial_extraction: Optional[ExtractedBoutiqueData] = None,
        missing_fields: Optional[list[str]] = None,
    ) -> Tuple[ExtractedBoutiqueData, Dict[str, Any]]:
        """
        Extrai dados estruturados de um markdown via GPT-4o-mini.
        Devolve (ExtractedBoutiqueData, token_usage_dict).
        """
        user_prompt = build_user_prompt(
            markdown=markdown,
            partial_extraction=partial_extraction,
            missing_fields=missing_fields,
        )

        if markdown and len(markdown) > 12000:
            logger.warning(f"Markdown truncado de {len(markdown)} para 12000 chars")
            user_prompt = user_prompt[:12000 + 2000]

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "{user_input}"),
        ])

        chain = prompt | self.llm
        token_usage = {}

        try:
            logger.info(f"[LLM_EXTRACTOR] LLM extraction starting (model: {self.deployment_name})")
            with get_openai_callback() as cb:
                result = await chain.ainvoke({"user_input": user_prompt})
                token_usage = {
                    "prompt_tokens": cb.prompt_tokens,
                    "completion_tokens": cb.completion_tokens,
                    "total_tokens": cb.total_tokens,
                    "cost_usd": cb.total_cost,
                }
            
            logger.info(
                f"[LLM_EXTRACTOR] LLM extraction OK — prices: {len(result.prices or [])}, "
                f"stores: {len(result.store_addresses or [])}, "
                f"brand: {result.brand_name} | "
                f"Tokens: {token_usage['total_tokens']} (Cost: ${token_usage['cost_usd']:.4f})"
            )
            return result, token_usage
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}", exc_info=True)
            return partial_extraction or ExtractedBoutiqueData(), {"total_tokens": 0, "cost_usd": 0}

llm_extractor = LLMExtractor()
