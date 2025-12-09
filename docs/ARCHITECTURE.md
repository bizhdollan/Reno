# RenovationTech Platform — Technical Architecture

> **Version**: 1.0 (MVP)  
> **Last Updated**: December 2024  
> **Status**: Planning Phase

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack](#2-tech-stack)
3. [System Architecture](#3-system-architecture)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend Architecture](#5-backend-architecture)
6. [LangGraph Conversation State Machine](#6-langgraph-conversation-state-machine)
7. [Database Design](#7-database-design)
8. [Vector Database Strategy](#8-vector-database-strategy)
9. [LLM Provider Abstraction](#9-llm-provider-abstraction)
10. [Authentication Flow](#10-authentication-flow)
11. [API Design](#11-api-design)
13. [Future Enhancements](#13-future-enhancements)

---

## 1. Overview

### 1.1 What is RenovationTech?

RenovationTech is an AI-powered renovation estimation platform that connects homeowners with contractors through a marketplace model.

**Core Value Proposition:**
- **Homeowners**: Get instant, professional 3-tier renovation estimates (Low/Mid/High) by conversing with an AI "Quantity Surveyor"
- **Contractors**: Access pre-scoped, qualified leads through a pay-to-unlock marketplace ($199/lead)

### 1.2 MVP Scope

| In Scope (MVP) | Out of Scope (Future) |
|----------------|----------------------|
| AI conversational estimation flow | Real-time notifications for contractors |
| 3-tier cost estimation (Low/Mid/High) | Video processing & analysis |
| Image upload & analysis | Contractor bidding system |
| Project token generation | Payment integration (simulated for MVP) |
| Contractor marketplace with filters | Mobile native apps |
| Project unlock mechanism | Advanced analytics dashboard |

### 1.3 Success Metrics (from PRD)

- **90%** completion rate in Homeowner Estimator flow
- **3+ contractor unlocks** per project within 30 days
- **100%** JSON schema compliance for AI-generated estimates
- **< 60 seconds** to receive estimate

---

## 2. Tech Stack

### 2.1 Frontend

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Framework | **React 18+ with TypeScript** | Industry standard, type safety for strict JSON schemas |
| Build Tool | **Vite** | Fast dev experience, modern bundling |
| Styling | **Tailwind CSS** | Rapid UI development, mobile-first |
| Components | **shadcn/ui** | Customizable, accessible components |
| Client State | **Zustand** | Minimal boilerplate, 41% usage in State of React 2024 |
| Server State | **TanStack Query + Firebase** | Handles caching, loading states, real-time sync |
| Routing | **React Router v6** | SPA navigation |

### 2.2 Backend

| Layer | Technology | Rationale |
|-------|------------|-----------|
| API Framework | **FastAPI** | Async support, automatic OpenAPI docs, Pydantic validation |
| State Machine | **LangGraph** | Purpose-built for multi-step conversational workflows with cycles |
| LLM Abstraction | **LiteLLM** | Unified API for 100+ models, fallbacks, cost tracking |
| Observability | **LangFuse** | Conversation tracing, latency/cost analytics |
| Primary Database | **Firebase Firestore** | Real-time sync, flexible schema, authentication |
| Vector Database | **Milvus** (Zilliz Cloud) | Hybrid search, handles billions of vectors, advanced filtering |
| Authentication | **Firebase Auth** | Anonymous auth + token-based project access |

### 2.3 AI/ML Models

| Purpose | Primary Model | Fallback | Notes |
|---------|---------------|----------|-------|
| Conversation & Reasoning | Gemini 2.5 Flash | Claude Sonnet 4 | Cost-effective, fast |
| Vision (Image Analysis) | Gemini 2.5 Pro | GPT-4o | Best multimodal performance |
| Vision (Detail Extraction) | Claude Opus 4 | Gemini 2.5 Pro | Precise fine-grained inspection |
| Text Embeddings | Voyage-3 | OpenAI text-embedding-3-large | High accuracy, cost-effective |
| Multimodal Embeddings | Voyage-multimodal-3 | Cohere embed-v4.0 | Interleaved text+image support |

### 2.4 Infrastructure (TBD)

| Component | Options Under Consideration |
|-----------|----------------------------|
| Backend Hosting | Cloud Run / AWS Lambda / EC2 |
| Frontend Hosting | Vercel / Firebase Hosting |
| Vector DB | Zilliz Cloud (managed Milvus) |
| File Storage | Firebase Storage / S3 |

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React + TypeScript)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Landing    │  │  Estimator  │  │ My Projects │  │ Contractor          │ │
│  │  Page       │  │  Chat Flow  │  │ (Homeowner) │  │ Marketplace         │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ /estimate   │  │ /projects   │  │ /unlock     │  │ /marketplace        │ │
│  │ (websocket) │  │ (REST)      │  │ (REST)      │  │ (REST)              │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
        ┌───────────────────┐ ┌─────────────┐ ┌─────────────────────┐
        │    LangGraph      │ │  Firestore  │ │      Milvus         │
        │  State Machine    │ │  (Primary)  │ │  (Vector Search)    │
        │                   │ │             │ │                     │
        │ ┌───────────────┐ │ │ - Projects  │ │ - Image embeddings  │
        │ │ Conversation  │ │ │ - Users     │ │ - Text embeddings   │
        │ │ Flow Engine   │ │ │ - Unlocks   │ │ - Descriptions      │
        │ └───────────────┘ │ │ - History   │ │                     │
        └───────────────────┘ └─────────────┘ └─────────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │     LiteLLM       │
        │  (Model Router)   │
        │                   │
        │ ┌───────────────┐ │
        │ │ Gemini │Claude│ │
        │ │ GPT-4o │ etc. │ │
        │ └───────────────┘ │
        └───────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │     LangFuse      │
        │  (Observability)  │
        └───────────────────┘
```

### 3.2 Data Flow

```
Homeowner Journey:
─────────────────
[Landing Page] → [Get Free Estimate] → [AI Chat Flow] → [Upload Images]
                                              │
                                              ▼
                                    [LangGraph State Machine]
                                              │
                                              ▼
                                    [3-Tier Estimate Generated]
                                              │
                                              ▼
                                    [Select Tier & Submit]
                                              │
                                              ▼
                                    [Project Token Generated]
                                              │
                                              ▼
                                    [Project Published to Marketplace]


Contractor Journey:
──────────────────
[Landing Page] → [I'm a Contractor] → [Marketplace View]
                                              │
                                              ▼
                                    [Browse Locked Projects]
                                    (Filter by: ZIP, Type, Budget)
                                              │
                                              ▼
                                    [Unlock Project ($199)]
                                              │
                                              ▼
                                    [View Full Scope + Contact Info]
```

---

## 4. Frontend Architecture

### 4.1 Project Structure

```
src/
├── app/
│   ├── layout.tsx
│   └── routes/
│       ├── index.tsx              # Landing page
│       ├── estimate/
│       │   └── index.tsx          # AI chat estimator
│       ├── projects/
│       │   └── [token].tsx        # Project details (homeowner view)
│       └── marketplace/
│           └── index.tsx          # Contractor marketplace
├── components/
│   ├── ui/                        # shadcn/ui components
│   ├── chat/
│   │   ├── ChatContainer.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── ImageUploader.tsx
│   │   └── EstimateCard.tsx
│   ├── marketplace/
│   │   ├── ProjectCard.tsx
│   │   ├── FilterBar.tsx
│   │   └── UnlockModal.tsx
│   └── shared/
│       ├── Header.tsx
│       └── Footer.tsx
├── stores/
│   ├── useEstimateStore.ts        # Zustand store for estimate flow
│   ├── useAuthStore.ts            # Auth state
│   └── useMarketplaceStore.ts     # Marketplace filters/state
├── hooks/
│   ├── useEstimateChat.ts         # WebSocket connection to LangGraph
│   ├── useProjects.ts             # TanStack Query for Firestore
│   └── useUnlock.ts               # Unlock mutation
├── lib/
│   ├── firebase.ts                # Firebase initialization
│   ├── api.ts                     # API client
│   └── types.ts                   # TypeScript types
└── utils/
    └── imageProcessing.ts         # Base64 conversion, compression
```

### 4.2 State Management Strategy

| State Type | Tool | Example |
|------------|------|---------|
| UI State | Zustand | Current chat step, selected tier, filters |
| Server State | TanStack Query | Projects list, project details |
| Real-time State | Firestore onSnapshot | Live marketplace updates |
| Form State | React Hook Form | Chat inputs, filter forms |

## 5. Backend Architecture

### 5.1 Project Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Environment configuration
│   ├── dependencies.py            # Dependency injection
│   │
│   ├── api/
│   │   ├── v1/
│   │   │   ├── estimate.py        # WebSocket endpoint for chat
│   │   │   ├── projects.py        # Project CRUD
│   │   │   ├── marketplace.py     # Marketplace endpoints
│   │   │   └── unlock.py          # Unlock endpoint
│   │   └── router.py
│   │
│   ├── core/
│   │   ├── langgraph/
│   │   │   ├── graph.py           # Main state machine definition
│   │   │   ├── nodes/
│   │   │   │   ├── welcome.py
│   │   │   │   ├── project_basics.py
│   │   │   │   ├── visual_collection.py
│   │   │   │   ├── detailed_extraction.py
│   │   │   │   ├── material_specification.py
│   │   │   │   ├── measurement_verification.py
│   │   │   │   ├── final_review.py
│   │   │   │   └── cost_estimation.py
│   │   │   ├── state.py           # State schema
│   │   │   └── edges.py           # Transition logic
│   │   │
│   │   ├── llm/
│   │   │   ├── provider.py        # LiteLLM wrapper
│   │   │   ├── prompts/
│   │   │   │   ├── quantity_surveyor.py
│   │   │   │   ├── image_analysis.py
│   │   │   │   └── cost_estimation.py
│   │   │   └── schemas.py         # Pydantic output schemas
│   │   │
│   │   └── vision/
│   │       ├── analyzer.py        # Image analysis pipeline
│   │       └── embeddings.py      # Multimodal embedding generation
│   │
│   ├── db/
│   │   ├── firestore.py           # Firestore client
│   │   ├── milvus.py              # Milvus client
│   │   └── models.py              # Data models
│   │
│   ├── services/
│   │   ├── project_service.py
│   │   ├── unlock_service.py
│   │   └── cost_tracker.py        # LLM cost tracking
│   │
│   └── utils/
│       ├── image_utils.py
│       └── token_generator.py
│
├── tests/
├── requirements.txt
└── Dockerfile
```

## 6. LangGraph Conversation State Machine

### 6.1 State Machine Overview

The heart of RenovationTech is the conversational AI flow, implemented as a LangGraph state machine with 8 primary states.

```
                                    ┌─────────────┐
                                    │   START     │
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                              ┌────▶│   WELCOME   │
                              │     └──────┬──────┘
                              │            │
                              │            ▼
                              │     ┌─────────────────┐
                              │     │ PROJECT_BASICS  │◀───┐
                              │     └──────┬──────────┘    │
                              │            │               │ (clarification)
                              │            ▼               │
                              │     ┌─────────────────────┐│
                              │     │ VISUAL_COLLECTION   │┘
                              │     └──────┬──────────────┘
                              │            │
                              │            ▼
                              │     ┌─────────────────────┐
            (needs more info) │     │ DETAILED_EXTRACTION │◀───┐
                              │     └──────┬──────────────┘    │
                              │            │                   │ (clarification)
                              │            ▼                   │
                              │     ┌─────────────────────────┐│
                              │     │ MATERIAL_SPECIFICATION  │┘
                              │     └──────┬──────────────────┘
                              │            │
                              │            ▼
                              │     ┌─────────────────────────┐
                              └─────│ MEASUREMENT_VERIFICATION│◀───┐
                                    └──────┬──────────────────┘    │
                                           │                       │ (correction)
                                           ▼                       │
                                    ┌─────────────┐                │
                                    │ FINAL_REVIEW│────────────────┘
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────────┐
                                    │ COST_ESTIMATION │
                                    └──────┬──────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │    END      │
                                    └─────────────┘
```

### 6.2 State Definitions


### 6.6 Conversation Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Conversational, not robotic** | Prompts designed for natural contractor-like dialogue |
| **One question at a time** | Each node asks only what's needed for that step |
| **Clarification loops** | Conditional edges allow going back with max 3 retries |
| **Context accumulation** | State persists all gathered info across steps |
| **Graceful recovery** | Any step can request more info without breaking flow |

---

## 7. Database Design

### 7.1 Firestore Collections

```
firestore/
├── projects/
│   └── {projectId}/
│       ├── public/                    # Visible to all contractors
│       │   ├── projectType: string
│       │   ├── zipCode: string
│       │   ├── acceptedTier: "low" | "mid" | "high"
│       │   ├── totalPrice: number
│       │   ├── briefScope: string
│       │   ├── createdAt: timestamp
│       │   └── status: "active" | "closed"
│       │
│       └── locked/                    # Hidden until unlocked
│           ├── homeownerContact: {
│           │     email: string,
│           │     phone?: string
│           │   }
│           ├── fullEstimate: {        # Complete 3-tier JSON
│           │     low: EstimateTier,
│           │     mid: EstimateTier,
│           │     high: EstimateTier
│           │   }
│           ├── images: [{
│           │     id: string,
│           │     url: string,
│           │     analysis: string
│           │   }]
│           ├── conversationHistory: Message[]
│           └── extractedData: object
│
├── unlocks/
│   └── {unlockId}/
│       ├── projectId: string
│       ├── contractorId: string
│       ├── unlockedAt: timestamp
│       ├── amount: number             # $199 or 2% of project
│       └── paymentStatus: string      # "simulated" for MVP
│
├── project_tokens/
│   └── {token}/
│       ├── projectId: string
│       ├── createdAt: timestamp
│       └── expiresAt: timestamp
│
└── analytics/
    └── {projectId}/
        └── llm_costs/
            └── {sessionId}/
                ├── model: string
                ├── inputTokens: number
                ├── outputTokens: number
                ├── cost: number
                └── timestamp: timestamp
```
---



## 8. Authentication Flow

### 8.1 Overview

No traditional login/register pages. Token-based project access.

```
┌─────────────────────────────────────────────────────────────────┐
│                      HOMEOWNER FLOW                              │
│                                                                  │
│  [Landing] → [Get Estimate] → [Complete Chat] → [Submit]        │
│                                                      │           │
│                                                      ▼           │
│                                    ┌──────────────────────────┐  │
│                                    │ Generate Project Token   │  │
│                                    │ (e.g., "RNV-7X9K2M")    │  │
│                                    └──────────────────────────┘  │
│                                                      │           │
│                                                      ▼           │
│                            [Show Token + "Save this to view     │
│                             your project later"]                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      CONTRACTOR FLOW                             │
│                                                                  │
│  [Landing] → [I'm a Contractor] → [Firebase Anonymous Auth]     │
│                                                      │           │
│                                                      ▼           │
│                                    [Marketplace Access]          │
│                                                      │           │
│                                                      ▼           │
│                                    [Unlock Project]              │
│                                          │                       │
│                                          ▼                       │
│                            [Record: contractorId + projectId]   │
└─────────────────────────────────────────────────────────────────┘
```
## 9. Future Enhancements

### 9.1 Phase 2 Features

| Feature | Description | Priority |
|---------|-------------|----------|
| **Video Processing** | Accept video uploads, extract keyframes, analyze with Gemini | High |
| **Payment Integration** | Stripe integration for real $199 unlocks | High |
| **Contractor Notifications** | Email/push when new matching projects arrive | Medium |
| **Bidding System** | Contractors submit quotes, homeowners compare | Medium |
| **Mobile Apps** | React Native apps for iOS/Android | Medium |
