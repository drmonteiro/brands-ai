# Confeções Lança - Agentic Lead Generation System

![Confeções Lança](https://img.shields.io/badge/Since-1973-1e293b)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20AI-green)

An intelligent, agentic lead generation ecosystem designed for **Confeções Lança**, a premium Portuguese garment manufacturer specializing in high-quality menswear since 1973.

## 🎯 Purpose

This application automates the discovery and qualification of boutique US menswear retailers that align with Confeções Lança's premium manufacturing capabilities. The system identifies brands with:

- **Fewer than 20 stores** (boutique scale)
- **Suit prices above €500** (~$540 USD)
- **US-based, independent operations** (not international conglomerates)

## 🏗️ Architecture

### Tech Stack

- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript
- **AI Orchestration:** LangGraph.js
- **Search API:** Tavily (optimized for LLM workflows)
- **UI Components:** shadcn/ui + Tailwind CSS
- **Email:** Resend API
- **State Management:** SQLite (LangGraph checkpointer)

### Agentic Workflow

The system implements a sophisticated multi-node workflow:

```
┌─────────────┐
│ Initialize  │ ← Fetch exchange rates, set parameters
└──────┬──────┘
       ↓
┌─────────────┐
│  Discovery  │ ← Search for boutique brands (Tavily)
└──────┬──────┘
       ↓
┌─────────────┐
│ Validation  │ ← Verify store count, pricing, origin
└──────┬──────┘
       ↓
┌─────────────┐
│   Filter    │ ← Rank and select top 10 brands
└──────┬──────┘
       ↓
┌─────────────┐
│  Approval   │ ← **HUMAN-IN-THE-LOOP** checkpoint
└──────┬──────┘
       ↓
┌─────────────┐
│ Send Email  │ ← Dispatch partnership proposals
└─────────────┘
```

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm
- Azure OpenAI API key and deployment (for LLM reasoning)
- Tavily API key (for web searching)
- Resend API key (for email sending)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd confecos-lanca
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment variables:**
   
   Create a `.env.local` file in the root directory:
   ```env
   # Azure OpenAI Configuration
   AZURE_OPENAI_ENDPOINT=https://occmodels.openai.azure.com/
   AZURE_OPENAI_API_KEY=your_azure_key_here
   AZURE_OPENAI_DEPLOYMENT=gpt-4o
   AZURE_OPENAI_API_VERSION=2024-08-01-preview
   
   # Tavily API Key for web searching
   TAVILY_API_KEY=tvly-...
   
   # Resend API Key for email sending
   RESEND_API_KEY=re_...
   
   # Email configuration
   FROM_EMAIL=comercial@confecos-lanca.pt
   ```

4. **Run the development server:**
   ```bash
   npm run dev
   ```

5. **Open the application:**
   
   Navigate to [http://localhost:3000](http://localhost:3000)

## 💼 How to Use

### Step 1: Search for Brands

1. Enter a US city name (e.g., "Boston", "Austin", "Portland")
2. Click "Search" to initiate the agentic workflow
3. Watch the **Progress Log** for real-time updates

### Step 2: Review Results

The system will display the **Top 10 Qualified Brands** with:

- **Brand Name & Website**
- **Store Count Badge** (Green < 10 stores, Amber 10-20 stores)
- **Average Suit Price** in USD
- **Verification Details** (how the agent validated the brand)

### Step 3: Send Partnership Proposals

For each qualified brand:

1. Review the brand's details
2. Click **"Send Partnership Proposal"**
3. The system sends a professionally crafted email highlighting:
   - Confeções Lança's 50+ years of manufacturing excellence
   - Advanced production technologies (laser cutting, precision manufacturing)
   - Sustainability commitment (renewable energy, waste management)
   - Flexibility (industrial scale + tailor-made models)

### Step 4: Track Results

The Progress Log records all email dispatches with timestamps.

## 🎨 Design Philosophy

The UI follows a **professional, premium aesthetic** that mirrors Confeções Lança's brand values:

- **Color Palette:** Navy (#1e293b), Charcoal, Silver
- **Typography:** Clean, modern sans-serif (Inter)
- **UX Principles:** Clear information hierarchy, instant feedback, minimal friction

## 🔧 Configuration

### Adjusting Search Parameters

Edit `lib/agents/prospector.ts` to modify:

```typescript
export function createInitialState(city: string): ProspectorState {
  return {
    // ...
    priceThresholdEUR: 500,  // Minimum suit price in EUR
    maxStores: 20,           // Maximum store count
    // ...
  };
}
```

### Customizing Email Templates

Edit `app/api/approve-email/route.ts` in the `generateEmailHTML()` function.

## 📊 Business Logic

### Price Verification

The system converts the €500 EUR threshold to USD using live exchange rates:

```
R_USD ≥ P_threshold × E_EUR/USD
```

For example, with an exchange rate of 1.08:
- Minimum acceptable price = €500 × 1.08 = **$540 USD**

### Store Count Validation

The agent:
1. Searches for "Store Locator", "Locations", "About Us" pages
2. Counts physical addresses (not wholesale partnerships)
3. Filters out brands with > 20 locations

### Origin Verification

The agent checks for indicators of international operations:
- Multiple country offices
- Non-US headquarters
- International shipping policies

## 🧪 Development Notes

### Mock Data

The current implementation includes **mock search results** for development. To integrate real data:

1. **Add Tavily API integration** in `lib/agents/prospector.ts`:
   ```typescript
   import { TavilyClient } from 'tavily';
   const tavily = new TavilyClient(process.env.TAVILY_API_KEY);
   ```

2. **Replace mock functions** with actual API calls in:
   - `mockTavilySearch()` → Use `tavily.search()`
   - `extractBrandInfo()` → Use `tavily.extract()` + LLM parsing

### Human-in-the-Loop Implementation

The current system implements a **simplified HITL** flow. For production:

1. Add **LangGraph SqliteSaver** for state persistence:
   ```typescript
   import { SqliteSaver } from "@langchain/langgraph";
   const checkpointer = SqliteSaver.fromConnString("./langgraph.db");
   const graph = workflow.compile({ checkpointer });
   ```

2. Implement **interrupt-on** configuration for the email node

3. Store `thread_id` in client state to resume workflows

## 🌐 Deployment

### Vercel (Recommended)

1. Push to GitHub
2. Connect repository to Vercel
3. Add environment variables in Vercel dashboard
4. Deploy

### Environment Variables Required

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- `TAVILY_API_KEY`
- `RESEND_API_KEY`
- `FROM_EMAIL`

## 🎯 Strategic Alignment

This application embodies Confeções Lança's core values:

| Company Value | Implementation |
|--------------|----------------|
| **Rigor** | Multi-step validation ensures only qualified leads |
| **Precision** | Exact price and store-count filtering |
| **Technical Competence** | Advanced AI orchestration with LangGraph |
| **Innovation** | Agentic workflow for automated prospecting |
| **Quality** | Premium UI/UX matching brand standards |

## 📝 License

Proprietary - Confeções Lança © 2024

## 🤝 Contact

**Confeções Lança**  
Covilhã, Portugal  
Email: comercial@confecos-lanca.pt  
Established: 1973

---

*"Superior quality clothing... exceeding all expectations."*
