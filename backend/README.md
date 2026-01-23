# Confeções Lança - Python Backend

AI-powered lead generation backend using FastAPI, LangChain, and LangGraph.

## Architecture

```
backend/
├── main.py              # FastAPI app & endpoints
├── config.py            # Configuration & environment
├── models.py            # Pydantic models
├── requirements.txt     # Python dependencies
├── agents/
│   ├── __init__.py
│   └── prospector.py    # LangGraph prospector agent
└── services/
    ├── __init__.py
    └── email_service.py # Resend email service
```

## Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the `backend/` folder:

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4

# Tavily Search
TAVILY_API_KEY=your_tavily_key

# Resend Email
RESEND_API_KEY=your_resend_key
FROM_EMAIL=comercial@confecos-lanca.pt

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=confecos-lanca
```

### 4. Run the Server

```bash
# Development mode with auto-reload
uvicorn main:app --reload --port 8000

# Or run directly
python main.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

### `GET /`
Health check endpoint.

### `GET /health`
Health check endpoint.

### `POST /api/prospect`
Start a prospecting search for boutique menswear brands.

**Request Body:**
```json
{
  "city": "Boston"
}
```

**Response:** Server-Sent Events stream with progress updates and final results.

### `POST /api/approve-email`
Send partnership email to a brand (human-in-the-loop).

**Request Body:**
```json
{
  "brand_name": "Brand Name",
  "brand_data": { ... }
}
```

## Workflow

1. **Query Generation** - AI generates 10 search queries based on current client profiles
2. **Discovery** - Tavily searches with 10 queries × 10 results = 100 potential URLs
3. **Selection Agent** - AI picks best candidate from each query (10 selected)
4. **Content Extraction** - Tavily extracts content from selected URLs
5. **Final Selection** - AI analyzes and returns up to 10 qualified candidates
6. **Human Approval** - User reviews and approves email sending

## Technologies

- **FastAPI** - Modern Python web framework
- **LangChain** - LLM orchestration
- **LangGraph** - Workflow orchestration
- **Azure OpenAI** - GPT-4 for intelligent analysis
- **Tavily** - Web search and content extraction
- **Resend** - Email delivery
- **Pydantic** - Data validation
