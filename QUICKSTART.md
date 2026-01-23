# Quick Start Guide - Confeções Lança Lead Generation

Get up and running in 5 minutes!

## ⚡ Fast Setup

### 1. Install Dependencies (1 minute)

```bash
npm install
```

### 2. Get API Keys (2 minutes)

You need API keys from 3 services:

| Service | Sign Up | Info | Get Key |
|---------|---------|------|---------|
| **Azure OpenAI** | [Azure Portal](https://portal.azure.com) | Enterprise-grade | Keys & Endpoint |
| **Tavily** | [app.tavily.com](https://app.tavily.com) | 1,000 credits/mo | Dashboard |
| **Resend** | [resend.com](https://resend.com) | 100 emails/day | [Get Key](https://resend.com/api-keys) |

### 3. Configure Environment (30 seconds)

```bash
# Copy the example file
cp .env.example .env.local

# Edit with your keys
nano .env.local
```

Paste your keys:
```env
AZURE_OPENAI_ENDPOINT=https://occmodels.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
TAVILY_API_KEY=tvly-...
RESEND_API_KEY=re_...
FROM_EMAIL=your-email@example.com
```

### 4. Start the App (30 seconds)

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## 🎯 First Search

1. **Enter a city:** Try "Boston" or "Austin"
2. **Click Search**
3. **Watch the magic:** Progress log shows real-time discovery
4. **Review brands:** Top 10 qualified leads appear
5. **Send emails:** Click "Send Partnership Proposal" for each brand

## 📊 What Happens Behind the Scenes

```
Your Input: "Boston"
     ↓
[Agent searches for boutique menswear brands]
     ↓
[Validates: store count < 20, suits > $540, US-based]
     ↓
[Ranks by quality alignment]
     ↓
Top 10 brands ready for outreach! 🎉
```

## 🔧 Common Issues

### "Failed to start search"
- Check your Azure OpenAI credentials are correct
- Verify your deployment name matches
- Ensure your Azure OpenAI resource has quota

### "No results found"
- Try a different city (e.g., "New York", "San Francisco")
- Check Tavily API key and credit balance

### Email not sending
- Verify Resend API key
- Check the console for error messages

## 📚 Next Steps

- **Production Setup:** Read [SETUP.md](./SETUP.md) for full integration
- **Customization:** Check [README.md](./README.md) for configuration options
- **API Integration:** Replace mock functions with real Tavily API calls

## 💡 Tips

- **Free tier limits:** OpenAI ~100 searches, Tavily ~200 searches/mo
- **Best cities:** Major US metros (Boston, Austin, Portland, Charleston)
- **Email deliverability:** Add a custom domain in Resend for better results

## 🚀 Deploy

Push to GitHub and connect to Vercel:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

Then visit [vercel.com](https://vercel.com) and import your repo.

---

**Questions?** Check the full [README.md](./README.md) or contact comercial@confecos-lanca.pt

**Confeções Lança** • Since 1973 • Excellence in Portuguese Manufacturing
