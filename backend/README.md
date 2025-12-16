# RenovationTech Backend

FastAPI backend with LangGraph conversational AI for renovation estimation.

## 🛠️ Tech Stack

- **Framework**: FastAPI
- **State Machine**: LangGraph
- **LLM Abstraction**: LiteLLM
- **Database**: Firebase Firestore
- **Vector DB**: Milvus (Zilliz Cloud)
- **Authentication**: Firebase Auth
- **Package Manager**: uv

## 📁 Project Structure

```
backend/
├── main.py                        # FastAPI app + runner (entry point)
├── src/
│   ├── config.py                  # Environment configuration
│   ├── dependencies.py            # Dependency injection
│   │
│   ├── api/v1/                    # API endpoints
│   │   ├── estimate.py            # WebSocket chat endpoint
│   │   ├── projects.py            # Project CRUD
│   │   ├── marketplace.py         # Marketplace endpoints
│   │   └── unlock.py              # Unlock endpoint
│   │
│   ├── core/                      # Core business logic
│   │   ├── langgraph/            # State machine
│   │   │   ├── graph.py          # Main graph definition
│   │   │   ├── state.py          # State schema
│   │   │   ├── edges.py          # Transition logic
│   │   │   └── nodes/            # Conversation nodes
│   │   ├── llm/                  # LLM providers
│   │   │   ├── provider.py       # LiteLLM wrapper
│   │   │   ├── schemas.py        # Pydantic schemas
│   │   │   └── prompts/          # System prompts
│   │   └── vision/               # Image processing
│   │
│   ├── db/                       # Database clients
│   │   ├── firestore.py          # Firestore client
│   │   ├── milvus.py             # Milvus client
│   │   └── models.py             # Data models
│   │
│   ├── services/                 # Business services
│   │   ├── project_service.py
│   │   ├── unlock_service.py
│   │   └── cost_tracker.py
│   │
│   └── utils/                    # Utilities
│       ├── image_utils.py
│       └── token_generator.py
│
├── tests/                        # Test suite
├── pyproject.toml               # Dependencies
└── .env.example                 # Environment template
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- uv (package manager)

### Installation

1. Install dependencies:
```bash
uv sync
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Add your API keys and credentials to `.env`

### Development

Run the development server:
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for API documentation.

## Chat API (synchronous)

- **POST** `/api/v1/chat`
- Body:
  ```json
  {
    "project_id": "abc123",
    "message": "I want a kitchen remodel in 94102",
    "state": {} // optional: send prior ProjectState; if omitted, server uses cached or fresh state
  }
  ```
  For images (multimodal), send `message` as a LangChain-style list:
  ```json
  {
    "project_id": "abc123",
    "message": [
      {"type": "text", "text": "Here's my kitchen"},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
  }
  ```
- Response:
  ```json
  {
    "assistant": "Got it! Please share photos...",
    "state": { "current_stage": "visual_collection", "messages": [ ... ] }
  }
  ```
- Behavior:
  - Synchronous request/response (no websockets or polling).
  - State is cached in-memory per `project_id`; frontend may also send the prior `state` explicitly.
