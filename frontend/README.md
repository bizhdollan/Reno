# RenovationTech Frontend

Modern React + TypeScript frontend for the RenovationTech Platform.

## 🛠️ Tech Stack

- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui (ready to add components)
- **State Management**: 
  - Zustand (client/UI state)
  - TanStack Query (server state)
- **Routing**: React Router v6
- **Backend**: Firebase (Firestore, Auth, Storage)

## 📁 Project Structure

```
src/
├── app/
│   └── routes/              # Page components
│       ├── index.tsx        # Landing page
│       ├── EstimatePage.tsx # AI chat estimator
│       ├── MarketplacePage.tsx # Contractor marketplace
│       └── ProjectPage.tsx  # Project details
├── components/
│   ├── ui/                  # shadcn/ui components
│   ├── chat/                # Chat interface components
│   ├── marketplace/         # Marketplace components
│   └── shared/              # Shared components
├── stores/
│   ├── useEstimateStore.ts  # Estimate flow state
│   ├── useAuthStore.ts      # Authentication state
│   └── useMarketplaceStore.ts # Marketplace filters
├── hooks/                   # Custom React hooks
├── lib/
│   ├── utils.ts             # Utility functions
│   ├── firebase.ts          # Firebase configuration
│   ├── api.ts               # API client
│   └── types.ts             # TypeScript types
└── utils/                   # Additional utilities
```

## 🚀 Getting Started

### Prerequisites

- Node.js 20+ (installed via nvm)
- npm 11+

### Installation

1. Install dependencies:
```bash
npm install
```

2. Create environment file:
```bash
cp .env.example .env.local
```

3. Add your Firebase credentials to `.env.local`:
```env
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_domain
VITE_FIREBASE_PROJECT_ID=your_project_id
# ... etc
```

### Development

Run the development server:
```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Build

Build for production:
```bash
npm run build
```

Preview production build:
```bash
npm run preview
```

## 🎨 Adding shadcn/ui Components

When you need to add shadcn/ui components (buttons, cards, etc.), you can manually add them from [shadcn/ui](https://ui.shadcn.com/) or use the CLI:

```bash
npx shadcn@latest add button
npx shadcn@latest add card
# etc.
```
