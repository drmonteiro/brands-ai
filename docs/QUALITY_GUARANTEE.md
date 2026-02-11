# Como Garantimos Qualidade dos Resultados

## Problema: Tavily retorna links genéricos

O Tavily é um motor de busca web que retorna resultados baseados em queries de texto. **Por si só, não garante qualidade** - pode retornar qualquer coisa que corresponda à pesquisa.

## Solução: 5 Camadas de Filtragem Inteligente

O sistema usa **múltiplas camadas de validação** para garantir que apenas os melhores clientes potenciais chegam ao resultado final.

---

## 📊 CAMADA 1: Query Generation Inteligente (IA)

**O que faz:** Gera queries de pesquisa baseadas no perfil ideal da Lança

**Como funciona:**
- Usa o perfil ideal da Lança (não analisa clientes específicos)
- Foca no tipo de marcas procuradas: boutique, premium, poucas lojas, qualidade europeia
- Gera 3 queries específicas focadas em:
  - Boutique menswear retailers (não grandes lojas de departamento)
  - Premium/luxury suits (€500+)
  - Independent retailers com poucas lojas (<20)
  - Heritage brands e bespoke tailors
  - Marcas que valorizam manufatura europeia de qualidade

**Exemplo de queries geradas:**
```
"Boston luxury menswear boutique suits"
"Boston premium custom tailor bespoke suits"
"Boston high end men suits store"
```

**Garantia:** As queries são **específicas e direcionadas**, não genéricas como "menswear Boston"

---

## 🔍 CAMADA 2: Filtros do Tavily

**O que faz:** Exclui domínios conhecidos como ruins

**Domínios excluídos:**
- Marketplaces: amazon.com, ebay.com
- Grandes cadeias: nordstrom.com, macys.com, walmart.com
- Redes sociais: facebook.com, instagram.com, twitter.com
- Sites de reviews: yelp.com, tripadvisor.com
- Fast fashion: asos.com, zalando.com

**Garantia:** Reduz drasticamente o ruído de resultados irrelevantes

---

## 🤖 CAMADA 3: Selection Agent (IA) - Primeira Filtragem

**O que faz:** Analisa os 60 resultados do Tavily e seleciona os 5 melhores de cada query (15 total)

**Critérios de seleção:**
1. ✅ Deve ser marca/retalhista de vestuário masculino que vende fatos
2. ✅ Preferir marcas luxury, premium ou boutique
3. ✅ Preferir sites oficiais (não diretórios ou marketplaces)
4. ✅ Preferir lojas independentes/boutique sobre grandes cadeias
5. ✅ OK incluir marcas sem preços visíveis (bespoke tailors)

**O que REJEITA:**
- ❌ Páginas de blog/notícias
- ❌ Links de redes sociais
- ❌ Sites de reviews
- ❌ Grandes lojas de departamento
- ❌ Fast fashion

**Filtros adicionais no código:**
```python
bad_url_patterns = [
    '/blog', '/news', '/press', '/article',
    '/about', '/about-us', '/our-story',
    '/contact', '/locations', '/find-us',
    'facebook.com', 'instagram.com', 'yelp.com'
]
```

**Garantia:** Apenas sites oficiais de marcas relevantes passam

---

## 📄 CAMADA 4: Content Extraction & Final Selection (IA)

**O que faz:** Extrai o conteúdo completo dos sites e analisa em profundidade

**Processo:**
1. Tavily extrai o conteúdo HTML/texto completo de cada site selecionado
2. IA analisa o conteúdo completo (não apenas preview)
3. Identifica:
   - Nome da marca
   - Número de lojas
   - Preços de fatos
   - Estilo da marca (Luxury/Premium/Bespoke)
   - Modelo de negócio (Retail/Bespoke/Both)
   - Tipos de roupa vendidos

**Critérios finais:**
- ✅ Deve vender fatos ou vestuário formal
- ✅ Posicionamento luxury, premium ou boutique
- ✅ Marcas independentes (não grandes lojas de departamento)
- ✅ Potencial interesse em parceria de manufatura portuguesa

**Garantia:** Validação profunda do conteúdo real do site, não apenas do preview

---

## 🎯 CAMADA 5: Similarity Scoring (ChromaDB + IA)

**O que faz:** Compara cada prospect com os 62 clientes atuais da Lança

**Processo:**
1. Gera embedding temporário do prospect (não guarda)
2. Compara com embeddings dos 62 clientes Lança no ChromaDB
3. Calcula pontuação de similaridade (0-100%)
4. Gera explicação de por que é similar

**Scores calculados:**
- **Size Score (25%):** Número de lojas (menos = melhor)
- **Quality Score (30%):** Lã 100%, bespoke, preço premium
- **Similarity Score (30%):** Similaridade com clientes atuais
- **Market Score (15%):** Força do mercado (país com clientes Lança)

**Final Score:** Combinação ponderada dos 4 scores

**Garantia:** Apenas prospects que se alinham com o perfil dos clientes atuais recebem scores altos

---

## 📊 Resumo do Fluxo Completo

```
Tavily retorna 60 URLs genéricos
    ↓
CAMADA 1: Queries inteligentes (já aplicado)
    ↓
CAMADA 2: Exclui domínios ruins (amazon, yelp, etc.)
    ↓
CAMADA 3: IA seleciona 15 melhores (5 por query)
    ↓
CAMADA 4: IA analisa conteúdo completo, valida 10-15
    ↓
CAMADA 5: ChromaDB compara com 62 clientes, calcula scores
    ↓
RESULTADO: Apenas prospects com score alto e perfil alinhado
```

---

## 🛡️ Garantias de Qualidade

### 1. **Queries Específicas**
- Baseadas no perfil ideal da Lança (não em clientes específicos)
- Não pesquisa genérico como "menswear"
- Foca em: boutique, premium, luxury, bespoke, poucas lojas

### 2. **Múltiplas Validações IA**
- 3 chamadas diferentes à OpenAI:
  - Query generation
  - Initial selection
  - Final validation

### 3. **Filtros de URL**
- Rejeita padrões conhecidos (blog, about, contact)
- Rejeita redes sociais e marketplaces

### 4. **Análise de Conteúdo**
- Não confia apenas no preview do Tavily
- Extrai e analisa conteúdo completo do site

### 5. **Similarity Matching**
- Compara com clientes reais da Lança
- Apenas prospects similares recebem scores altos

### 6. **Scoring Multi-dimensional**
- Não é apenas "vende fatos?"
- Avalia: tamanho, qualidade, similaridade, mercado

---

## ⚠️ Limitações e Melhorias Possíveis

### Limitações Atuais:
1. **Dependência do Tavily:** Se Tavily não encontrar bons resultados, o sistema não pode criar do zero
2. **Queries fixas:** Apenas 3 queries por cidade (poderia ser mais)
3. **Análise de conteúdo:** Depende da qualidade da extração do Tavily

### Melhorias Possíveis:
1. **Mais queries:** Aumentar de 3 para 5-10 queries por cidade
2. **Validação manual:** Permitir revisão humana antes de guardar
3. **Feedback loop:** Aprender com prospects rejeitados
4. **Análise de competidores:** Comparar com marcas similares conhecidas
5. **Validação de preços:** Verificar preços em múltiplas fontes

---

## 📈 Métricas de Qualidade

O sistema rastreia:
- **Final Score:** 0-100 (meta: >65 para "recommended")
- **Similarity Score:** % de similaridade com clientes atuais
- **Quality Score:** Baseado em lã, bespoke, preço
- **Size Score:** Número de lojas (ideal: 1-5)

**Recomendações:**
- ⭐ **80+:** HIGHLY RECOMMENDED - Ideal boutique partner
- ✅ **65-79:** RECOMMENDED - Good potential partner
- ⚠️ **50-64:** CONSIDER - Review manually
- ❌ **<50:** LOW PRIORITY - May be too large or not aligned

---

## 🎯 Conclusão

**O Tavily fornece os links, mas o sistema garante qualidade através de:**
1. Queries inteligentes baseadas em clientes reais
2. Múltiplas camadas de filtragem IA
3. Análise profunda de conteúdo
4. Comparação com clientes atuais (ChromaDB)
5. Scoring multi-dimensional

**Resultado:** Apenas prospects que se alinham com o perfil ideal da Lança chegam ao resultado final.
