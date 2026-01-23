# Confeções Lança - Setup Guide

This guide will walk you through setting up the Agentic Lead Generation System for production use.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [API Key Setup](#api-key-setup)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Production Integration](#production-integration)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have:

- **Node.js 18+** and npm installed
- A code editor (VS Code recommended)
- Terminal/command line access
- Credit card for API service registration (most have free tiers)

## API Key Setup

### 1. Azure OpenAI API Key

**Purpose:** Powers the LLM reasoning in the agent workflow (analyzing brands, extracting information)

**Steps:**
1. Access your Azure Portal
2. Navigate to your Azure OpenAI resource
3. Go to "Keys and Endpoint"
4. Copy the following:
   - **Endpoint URL** (e.g., `https://occmodels.openai.azure.com/`)
   - **API Key** (Key 1 or Key 2)
   - **Deployment Name** (your model deployment, e.g., `gpt-4o`)
5. Note the API version you're using (e.g., `2024-08-01-preview`)

**Cost:** Based on your Azure OpenAI pricing tier

### 2. Tavily API Key

**Purpose:** Performs intelligent web searches optimized for LLM consumption

**Steps:**
1. Go to [https://app.tavily.com/](https://app.tavily.com/)
2. Sign up for a free account
3. Navigate to your dashboard
4. Copy your API key (starts with `tvly-`)

**Free Tier:** 1,000 credits/month (enough for ~100-200 searches depending on depth)

### 3. Resend API Key

**Purpose:** Sends partnership proposal emails to brands

**Steps:**
1. Go to [https://resend.com/](https://resend.com/)
2. Sign up for an account
3. Navigate to [API Keys](https://resend.com/api-keys)
4. Create a new API key
5. Copy the key (starts with `re_`)

**Free Tier:** 100 emails/day, 3,000 emails/month

### 4. Domain Setup for Emails (Optional but Recommended)

For professional email sending:

1. In Resend, go to [Domains](https://resend.com/domains)
2. Add your domain (e.g., `confecos-lanca.pt`)
3. Add the DNS records to your domain registrar
4. Verify the domain
5. Update `FROM_EMAIL` in `.env.local` to use your verified domain

## Installation

### Step 1: Clone and Install

```bash
# Navigate to your projects directory
cd ~/projects

# Clone the repository
git clone <repository-url> confecos-lanca
cd confecos-lanca

# Install dependencies
npm install
```

### Step 2: Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env.local

# Edit the file with your API keys
nano .env.local  # or use your preferred editor
```

Add your keys:

```env
AZURE_OPENAI_ENDPOINT=https://occmodels.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
TAVILY_API_KEY=tvly-xxxxx...
RESEND_API_KEY=re_xxxxx...
FROM_EMAIL=comercial@confecos-lanca.pt
```

### Step 3: Test the Installation

```bash
# Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Configuration

### Adjusting Search Parameters

Edit `lib/agents/prospector.ts`:

```typescript
export function createInitialState(city: string): ProspectorState {
  return {
    targetCity: city,
    targetCountry: "USA",
    priceThresholdEUR: 500,  // Change minimum price here
    maxStores: 20,           // Change maximum stores here
    // ...
  };
}
```

### Customizing the Email Template

Edit `app/api/approve-email/route.ts` in the `generateEmailHTML()` function:

```typescript
function generateEmailHTML(brand: BrandLead): string {
  return `
    <!DOCTYPE html>
    <html>
      <!-- Customize your email template here -->
    </html>
  `;
}
```

## Production Integration

### Integrating Real Tavily Search

Replace the mock function in `lib/agents/prospector.ts`:

```typescript
// Remove mock function
async function mockTavilySearch(query: string): Promise<SearchResult[]> {
  // DELETE THIS
}

// Add real Tavily integration
import { tavily } from "@tavily/core";

async function performTavilySearch(query: string): Promise<SearchResult[]> {
  const client = tavily({ apiKey: process.env.TAVILY_API_KEY! });
  
  const response = await client.search(query, {
    search_depth: "advanced",
    max_results: 10,
    include_domains: [],
    exclude_domains: ["amazon.com", "ebay.com"],
  });
  
  return response.results.map(r => ({
    title: r.title,
    url: r.url,
    content: r.content,
    score: r.score,
  }));
}
```

Update the `discoveryNode` function to use the real search:

```typescript
async function discoveryNode(state: ProspectorState): Promise<Partial<ProspectorState>> {
  // ...
  for (const query of state.searchQueries) {
    const results = await performTavilySearch(query);
    candidateUrls.push(...results.map(r => r.url));
  }
  // ...
}
```

### Integrating Real Brand Extraction

Use Tavily's Extract API and LLM reasoning:

```typescript
async function extractBrandInfo(url: string, priceThreshold: number): Promise<BrandLead | null> {
  try {
    // 1. Extract website content
    const client = tavily({ apiKey: process.env.TAVILY_API_KEY! });
    const extraction = await client.extract([url]);
    
    // 2. Use LLM to analyze the content
    const llm = new ChatOpenAI({ modelName: "gpt-4o", temperature: 0.2 });
    
    const prompt = `
      Analyze this boutique menswear brand and extract the following:
      1. Brand name
      2. Number of physical store locations (count addresses, not wholesale partners)
      3. Average suit price in USD (find 3 non-sale suits and average them)
      4. Is this a US-based independent brand? (not international conglomerate)
      
      Website content:
      ${extraction.results[0].raw_content}
      
      Return JSON: { "name": "...", "storeCount": N, "avgPrice": N, "isUSBased": true/false }
    `;
    
    const response = await llm.invoke(prompt);
    const data = JSON.parse(response.content as string);
    
    // 3. Validate constraints
    if (!data.isUSBased || data.storeCount >= 20 || data.avgPrice < priceThreshold) {
      return null;
    }
    
    return {
      name: data.name,
      websiteUrl: url,
      storeCount: data.storeCount,
      averageSuitPriceUSD: data.avgPrice,
      originCountry: "USA",
      verified: true,
      verificationLog: [
        `Found ${data.storeCount} store locations`,
        `Average suit price: $${data.avgPrice}`,
        `Confirmed US-based independent brand`,
      ],
      passesConstraints: true,
    };
    
  } catch (error) {
    console.error(`Error extracting brand info for ${url}:`, error);
    return null;
  }
}
```

### Integrating Real Email Sending

Replace the mock email function in `app/api/approve-email/route.ts`:

```typescript
import { Resend } from 'resend';

async function sendPartnershipEmail(brand: BrandLead): Promise<{ success: boolean; error?: string }> {
  try {
    const resend = new Resend(process.env.RESEND_API_KEY!);
    
    // Try to find contact email (you may need to scrape or manually add)
    const toEmail = await findContactEmail(brand.websiteUrl);
    
    const result = await resend.emails.send({
      from: process.env.FROM_EMAIL!,
      to: toEmail,
      subject: `Partnership Opportunity from Confeções Lança - Premium Portuguese Manufacturing`,
      html: generateEmailHTML(brand),
    });
    
    console.log(`[EMAIL] Sent successfully to ${brand.name}:`, result);
    
    return { success: true };
    
  } catch (error) {
    console.error("[EMAIL] Error sending email:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// Helper to find contact email (implement based on your needs)
async function findContactEmail(url: string): Promise<string> {
  // Option 1: Scrape the contact page
  // Option 2: Use a service like Hunter.io
  // Option 3: Use a pattern like info@domain.com
  
  const domain = new URL(url).hostname;
  return `info@${domain}`;
}
```

## Troubleshooting

### Issue: "Failed to fetch exchange rate"

**Solution:** Check your internet connection. The app uses a free exchange rate API. If it's down, the fallback rate of 1.08 is used.

### Issue: "Tavily API rate limit exceeded"

**Solution:** 
- Check your Tavily dashboard for usage
- Upgrade to a paid plan if needed
- Reduce the number of search queries in `searchQueries` array

### Issue: "Azure OpenAI API error"

**Solution:**
- Verify your API key and endpoint are correct
- Check your Azure OpenAI deployment name matches
- Ensure your Azure resource has sufficient quota
- Verify the API version is correct

### Issue: "Email not sending"

**Solution:**
- Verify your Resend API key
- Check if your domain is verified (if using custom domain)
- Review Resend logs for delivery status

### Issue: Build errors with LangGraph

**Solution:**
```bash
# Clear cache and reinstall
rm -rf node_modules .next
npm install
npm run dev
```

## 🚀 Deployment

### Deploy to Vercel

1. Push your code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Import your repository
4. Add environment variables in Vercel dashboard:
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_DEPLOYMENT`
   - `AZURE_OPENAI_API_VERSION`
   - `TAVILY_API_KEY`
   - `RESEND_API_KEY`
   - `FROM_EMAIL`
5. Deploy

### Deploy to Other Platforms

The app works on any platform supporting Next.js 15:
- Netlify
- AWS Amplify
- Google Cloud Run
- Railway
- Fly.io

## 📞 Support

For issues or questions:
- Review the main [README.md](./README.md)
- Check API provider documentation
- Contact: comercial@confecos-lanca.pt

---

**Confeções Lança** • Excellence in Portuguese Manufacturing since 1973
