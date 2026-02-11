"""
Análise dos 18 Clientes da Lança para extrair estatísticas
"""

import statistics
from data.lanca_clients import LANCA_CLIENTS

print('=' * 60)
print('📊 ANÁLISE DOS 18 CLIENTES DA LANÇA')
print('=' * 60)

# Preços
prices = [c['pvp_suits_eur'] for c in LANCA_CLIENTS if c.get('pvp_suits_eur')]
print(f'\n💰 PREÇOS (EUR):')
print(f'   Min: €{min(prices)}')
print(f'   Max: €{max(prices)}')
print(f'   Média: €{statistics.mean(prices):.0f}')
print(f'   Mediana: €{statistics.median(prices):.0f}')
print(f'   Clientes com preço conhecido: {len(prices)}/18')

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
  ❌ Preço < €{min(prices)} → REJEITAR
  ❌ Lojas > {max(stores)} → REJEITAR

SCORING BASEADO EM DADOS:
  💰 Preço ideal: €{int(statistics.median(prices))} - €{max(prices)}
  🏪 Lojas ideal: 1-{int(statistics.median(stores))} (mediana dos clientes)
  🧶 100% Lã: OBRIGATÓRIO (100% dos clientes têm)
  ✂️ Fatos à medida: PREFERENCIAL (+{mtm.count(True)/18*100:.0f}% dos clientes têm)
  🏷️ Marca própria: PREFERENCIAL (+{brand_types.count("own_brand")/18*100:.0f}% dos clientes são)
''')
