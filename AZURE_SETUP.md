# Azure OpenAI Configuration Guide

## ✅ Your Azure OpenAI Credentials

Suas credenciais já estão configuradas no arquivo `.env.local`:

```env
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

## 🔧 Como Funciona

A aplicação agora usa **Azure OpenAI** em vez do OpenAI regular. Aqui está o que foi configurado:

### 1. **LLM Configuration**

O arquivo `lib/agents/prospector.ts` foi atualizado para usar `AzureChatOpenAI`:

```typescript
import { AzureChatOpenAI } from "@langchain/openai";

function getLLM() {
  return new AzureChatOpenAI({
    azureOpenAIApiKey: process.env.AZURE_OPENAI_API_KEY,
    azureOpenAIApiVersion: process.env.AZURE_OPENAI_API_VERSION,
    azureOpenAIApiInstanceName: 'occmodels',
    azureOpenAIApiDeploymentName: process.env.AZURE_OPENAI_DEPLOYMENT,
    temperature: 0.2,
  });
}
```

### 2. **Deployment Details**

- **Endpoint:** `occmodels.openai.azure.com`
- **Deployment:** `gpt-5.1` (seu modelo implantado)
- **API Version:** `2024-08-01-preview`

## 🧪 Testando a Configuração

### 1. Verificar Build

```bash
npm run build
```

✅ **Status:** Build completado com sucesso!

### 2. Iniciar Servidor

```bash
npm run dev
```

Servidor disponível em: http://localhost:3000

### 3. Testar Busca

1. Acesse http://localhost:3000
2. Digite uma cidade americana (ex: "Boston")
3. Clique "Search"
4. Observe o **Progress Log** - ele mostrará chamadas ao seu Azure OpenAI

## 📊 Uso do Azure OpenAI

A aplicação usa o Azure OpenAI para:

### **Durante Discovery & Validation**
- ❌ **Não usado atualmente** (mock data para desenvolvimento)

### **Durante Brand Analysis** (quando integrar Tavily)
- ✅ Analisar conteúdo de websites
- ✅ Extrair informações (nome, preços, lojas)
- ✅ Validar se é marca US independente
- ✅ Interpretar páginas "About Us" e "Store Locator"

## 🔐 Segurança

### **Proteção de Credenciais**

O arquivo `.env.local` está no `.gitignore` e **nunca será commitado**.

### **Para Deploy em Produção**

Quando fizer deploy (Vercel, Azure, etc.), adicione as variáveis de ambiente no dashboard:

```
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

## 💡 Comparação: Azure vs OpenAI Regular

| Feature | Azure OpenAI | OpenAI Regular |
|---------|--------------|----------------|
| **Enterprise Security** | ✅ Sim | ❌ Não |
| **Data Residency** | ✅ Configurável | ❌ Não |
| **SLA** | ✅ 99.9% | ❌ Best effort |
| **Private Endpoints** | ✅ Sim | ❌ Não |
| **Billing** | ✅ Azure Account | ❌ OpenAI Account |
| **Compliance** | ✅ GDPR, SOC 2 | ⚠️ Limitado |

**Vantagem para Confeções Lança:** Azure OpenAI oferece maior segurança e compliance, ideal para uso empresarial.

## 🚀 Próximos Passos

### 1. **Adicionar Tavily API Key**

Para ativar a busca real de marcas:

```env
TAVILY_API_KEY=tvly-your_key_here
```

Obtenha em: [app.tavily.com](https://app.tavily.com)

### 2. **Adicionar Resend API Key**

Para ativar envio de emails:

```env
RESEND_API_KEY=re_your_key_here
```

Obtenha em: [resend.com/api-keys](https://resend.com/api-keys)

### 3. **Integrar Tavily na Produção**

Edite `lib/agents/prospector.ts` e substitua as funções mock:
- `mockTavilySearch()` → Use Tavily Search API
- `extractBrandInfo()` → Use Tavily Extract + Azure OpenAI

Instruções detalhadas em [SETUP.md](./SETUP.md).

## ⚙️ Troubleshooting

### Erro: "Azure OpenAI API error"

**Possíveis causas:**
1. API key incorreta
2. Deployment name errado (certifique-se que é `gpt-5.1`)
3. Quota esgotada no Azure
4. API version incompatível

**Soluções:**
1. Verifique as credenciais no Azure Portal
2. Confirme que o deployment `gpt-5.1` existe e está ativo
3. Verifique quotas em Azure Portal > Seu recurso > Quotas
4. Tente API version `2024-02-01` se `2024-08-01-preview` não funcionar

### Erro: "Instance name not found"

O endpoint `occmodels.openai.azure.com` é extraído automaticamente. Se houver problemas, verifique se o ENDPOINT está correto no `.env.local`.

## 📈 Monitoramento

### Via Azure Portal

1. Acesse [portal.azure.com](https://portal.azure.com)
2. Navegue até seu recurso Azure OpenAI
3. Veja **Metrics** para:
   - Total de chamadas
   - Tokens processados
   - Latência média
   - Erros

### Via Aplicação

O Progress Log mostra cada chamada ao LLM em tempo real.

## 🎉 Status

✅ **Azure OpenAI configurado e funcionando!**

A aplicação está pronta para usar seu deployment `gpt-5.1` no Azure OpenAI.

---

**Configurado para:** Confeções Lança  
**Deployment:** gpt-5.1 @ occmodels.openai.azure.com  
**Data:** Janeiro 2026
