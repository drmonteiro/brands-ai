# Confeções Lança - Agentic Lead Generation System

![Confeções Lança](https://img.shields.io/badge/Since-1973-1e293b)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue)
![Python](https://img.shields.io/badge/Python-3.12-green)
![FastAPI](https://img.shields.io/badge/FastAPI-Async-teal)

An intelligent, agentic lead generation ecosystem designed for **Confeções Lança**, a premium Portuguese garment manufacturer specializing in high-quality menswear since 1973.

## 📁 Project Structure

```
confecos-lanca/
├── frontend/                 # Next.js 15 React Application
│   ├── app/                  # Next.js App Router pages
│   ├── components/           # React components
│   │   └── ui/               # shadcn/ui components
│   ├── lib/                  # Utilities and types
│   ├── public/               # Static assets
│   ├── package.json          # Frontend dependencies
│   ├── next.config.ts        # Next.js configuration
│   ├── tailwind.config.ts    # Tailwind CSS configuration
│   └── tsconfig.json         # TypeScript configuration
│
├── backend/                  # Python FastAPI Backend
│   ├── agents/               # AI Agent implementations
│   │   └── prospector.py     # Lead prospecting agent
│   ├── services/             # Business services
│   │   └── email_service.py  # Email sending service
│   ├── main.py               # FastAPI application entry point
│   ├── models.py             # Pydantic models
│   ├── config.py             # Configuration management
│   ├── requirements.txt      # Python dependencies
│   └── venv/                 # Python virtual environment
│
└── README.md                 # This file
```

## 🎯 Purpose

This application automates the discovery and qualification of boutique US menswear retailers that align with Confeções Lança's premium manufacturing capabilities. The system identifies brands with:

- **Fewer than 20 stores** (boutique scale)
- **Suit prices above €500** (~$540 USD)
- **US-based, independent operations** (not international conglomerates)

## 🏗️ Architecture

### Tech Stack

**Frontend:**
- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript
- **UI Components:** shadcn/ui + Tailwind CSS
- **State Management:** React Hooks

**Backend:**
- **Framework:** FastAPI (Python 3.12+)
- **AI Orchestration:** LangChain / LangGraph
- **Search API:** Tavily (optimized for LLM workflows)
- **Email:** Resend API
- **LLM:** Azure OpenAI GPT-4o

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

- **Node.js 18+** and npm
- **Python 3.12+** and pip
- Azure OpenAI API key and deployment (for LLM reasoning)
- Tavily API key (for web searching)
- Resend API key (for email sending)

### Installation

#### 1. Clone the repository

```bash
git clone <repository-url>
cd confecos-lanca
```

#### 2. Setup Frontend

```bash
cd frontend
npm install
```

Create a `.env.local` file in the `frontend` directory:

```env
# Frontend doesn't need API keys - they're managed by the backend
```

#### 3. Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend` directory:

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

### Running the Application

#### 1. Start the Backend (Terminal 1)

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`

#### 2. Start the Frontend (Terminal 2)

```bash
cd frontend
npm run dev
```

The application will be available at `http://localhost:3000`

## 💼 How to Use

### Step 1: Search for Brands

1. Enter a US city name (e.g., "Boston", "Austin", "Portland")
2. Click "Search" to initiate the agentic workflow
3. Watch the progress as the AI searches and validates brands

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

## 🎨 Design Philosophy

The UI follows a **professional, premium aesthetic** that mirrors Confeções Lança's brand values:

- **Color Palette:** Gold (#F5C518), Black (#1a1a1a), Cream (#FAF8F5)
- **Typography:** DM Serif Display (headings) + Outfit (body)
- **UX Principles:** Clear information hierarchy, instant feedback, minimal friction

## 📊 API Endpoints

### Backend Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/prospect` | POST | Start brand prospecting (SSE stream) |
| `/api/approve-email` | POST | Send partnership email to a brand |
| `/api/health` | GET | Health check endpoint |

## 🌐 Deployment

### Frontend (Vercel)

1. Push to GitHub
2. Connect repository to Vercel
3. Set root directory to `frontend`
4. Deploy

### Backend (Railway / Render / AWS)

1. Set root directory to `backend`
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables

### Environment Variables Required

**Backend:**
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
