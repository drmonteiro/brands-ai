"""
Análise dos 18 Clientes da Lança para extrair estatísticas
Inclui análise de 3 categorias de preço: Fatos completos, Casacos e Calças
"""

import statistics
from data.lanca_clients import LANCA_CLIENTS

print('=' * 60)
print('📊 ANÁLISE DOS 18 CLIENTES DA LANÇA')
print('=' * 60)

# ============================================================
# PREÇOS - 3 CATEGORIAS
# ============================================================
suit_prices = [c['pvp_suits_eur'] for c in LANCA_CLIENTS if c.get('pvp_suits_eur')]
jacket_prices = [c['pvp_jacket_eur'] for c in LANCA_CLIENTS if c.get('pvp_jacket_eur')]
trouser_prices = [c['pvp_trousers_eur'] for c in LANCA_CLIENTS if c.get('pvp_trousers_eur')]

print(f'\n💰 PREÇOS - FATOS COMPLETOS (casaco + calça) (EUR):')
print(f'   Min: €{min(suit_prices)}')
print(f'   Max: €{max(suit_prices)}')
print(f'   Média: €{statistics.mean(suit_prices):.0f}')
print(f'   Mediana: €{statistics.median(suit_prices):.0f}')
print(f'   Clientes com preço conhecido: {len(suit_prices)}/18')
print(f'   ✅ Gama alvo Lança: €500 – €1.700')

print(f'\n🧥 PREÇOS - SÓ CASACO (EUR):')
print(f'   Min: €{min(jacket_prices)}')
print(f'   Max: €{max(jacket_prices)}')
print(f'   Média: €{statistics.mean(jacket_prices):.0f}')
print(f'   Mediana: €{statistics.median(jacket_prices):.0f}')
print(f'   Clientes com preço conhecido: {len(jacket_prices)}/18')
print(f'   ✅ Gama alvo Lança: €300 – €1.000')

print(f'\n👖 PREÇOS - SÓ CALÇA (EUR):')
print(f'   Min: €{min(trouser_prices)}')
print(f'   Max: €{max(trouser_prices)}')
print(f'   Média: €{statistics.mean(trouser_prices):.0f}')
print(f'   Mediana: €{statistics.median(trouser_prices):.0f}')
print(f'   Clientes com preço conhecido: {len(trouser_prices)}/18')
print(f'   ✅ Gama alvo Lança: €250 – €750')

# Lojas
stores = [c['store_count'] for c in LANCA_CLIENTS]
print(f'\n🏪 NÚMERO DE LOJAS:')
print(f'   Min: {min(stores)}')
print(f'   Max: {max(stores)}')
print(f'   Média: {statistics.mean(stores):.1f}')
print(f'   Mediana: {statistics.median(stores):.0f}')
print(f'   < 5 lojas: {len([s for s in stores if s < 5])}/18')
print(f'   5-10 lojas: {len([s for s in stores if 5 <= s <= 10])}/18')
print(f'   11-20 lojas: {len([s for s in stores if 11 <= s <= 20])}/18')
print(f'   > 20 lojas: {len([s for s in stores if s > 20])}/18')

# Lã
wool = [c['wool_percentage'] for c in LANCA_CLIENTS]
print(f'\n🧶 LÃ 100%:')
print(f'   100% lã: {wool.count("100%")}/18 ({wool.count("100%")/18*100:.0f}%)')

# Made to Measure
mtm = [c['made_to_measure'] for c in LANCA_CLIENTS]
print(f'\n✂️ FATOS À MEDIDA (MTM):')
print(f'   Sim: {mtm.count(True)}/18 ({mtm.count(True)/18*100:.0f}%)')
print(f'   Não: {mtm.count(False)}/18 ({mtm.count(False)/18*100:.0f}%)')

# Brand Type
brand_types = [c['brand_type'] for c in LANCA_CLIENTS]
print(f'\n🏷️ TIPO DE MARCA:')
print(f'   Marca Própria: {brand_types.count("own_brand")}/18 ({brand_types.count("own_brand")/18*100:.0f}%)')
print(f'   Multimarca: {brand_types.count("multibrand")}/18 ({brand_types.count("multibrand")/18*100:.0f}%)')

# Tiers
tiers = [c['tier'] for c in LANCA_CLIENTS]
print(f'\n⭐ TIERS:')
print(f'   High Value: {tiers.count("high_value")}/18')
print(f'   Medium Value: {tiers.count("medium_value")}/18')
print(f'   Low Value: {tiers.count("low_value")}/18')

# Anos de parceria
years = [c['years_as_client'] for c in LANCA_CLIENTS]
print(f'\n📅 ANOS DE PARCERIA:')
print(f'   Min: {min(years)} anos')
print(f'   Max: {max(years)} anos')
print(f'   Média: {statistics.mean(years):.1f} anos')

# Países
countries = {}
for c in LANCA_CLIENTS:
    cc = c['country_code']
    countries[cc] = countries.get(cc, 0) + 1
print(f'\n🌍 PAÍSES:')
for cc, count in sorted(countries.items(), key=lambda x: -x[1]):
    print(f'   {cc}: {count} clientes')

print('\n' + '=' * 60)
print('\n📋 CONCLUSÕES PARA O SCORING:')
print('=' * 60)
print(f'''
FILTROS HARD (ELIMINATÓRIOS):
  ❌ Preço fato < €{min(suit_prices)} → REJEITAR
  ❌ Preço casaco < €{min(jacket_prices)} → REJEITAR
  ❌ Preço calça < €{min(trouser_prices)} → REJEITAR
  ❌ Lojas > {max(stores)} → REJEITAR

GAMAS DE PREÇO ALVO (3 categorias):
  🧥 Fato completo (casaco + calça): €500 – €1.700
  🧥 Só casaco: €300 – €1.000
  👖 Só calça: €250 – €750

SCORING BASEADO EM DADOS:
  💰 Preço ideal fatos: €{int(statistics.median(suit_prices))} - €{max(suit_prices)}
  💰 Preço ideal casacos: €{int(statistics.median(jacket_prices))} - €{max(jacket_prices)}
  💰 Preço ideal calças: €{int(statistics.median(trouser_prices))} - €{max(trouser_prices)}
  🏪 Lojas ideal: 1-{int(statistics.median(stores))} (mediana dos clientes)
  🧶 100% Lã: OBRIGATÓRIO (100% dos clientes têm)
  ✂️ Fatos à medida: PREFERENCIAL (+{mtm.count(True)/18*100:.0f}% dos clientes têm)
  🏷️ Marca própria: PREFERENCIAL (+{brand_types.count("own_brand")/18*100:.0f}% dos clientes são)
  🏙️ Sede: OBRIGATÓRIO (marca deve ter sede na cidade alvo)
''')
