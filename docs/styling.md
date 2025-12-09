# RenovationTech — Design System & Styling Guide

> **Version**: 1.0  
> **Last Updated**: December 2024  
> **Purpose**: Consistent, professional UI across all RenovationTech interfaces

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Spacing & Layout](#4-spacing--layout)
5. [Component Library](#5-component-library)
6. [Icons](#6-icons)
7. [Imagery & Media](#7-imagery--media)
8. [Motion & Animation](#8-motion--animation)
9. [Dark Mode](#9-dark-mode)
10. [Accessibility](#10-accessibility)
11. [Implementation](#11-implementation)

---

## 1. Design Philosophy

### 1.1 Core Principles

| Principle | Description |
|-----------|-------------|
| **Trust & Reliability** | Deep blues convey professionalism; contractors and homeowners need to feel confident |
| **Warmth & Action** | Orange accents create urgency and approachability without being aggressive |
| **Clarity First** | Clean layouts, generous whitespace, minimal cognitive load |
| **Mobile-First** | 60%+ of users will access on mobile devices |
| **Balanced Appeal** | Professional enough for contractors, friendly enough for homeowners |

### 1.2 Design Inspiration

Based on research of successful platforms in the renovation/construction and SaaS space:

- **Houzz Pro** — Clean marketplace cards, trust indicators
- **Thumbtack** — Approachable contractor marketplace
- **Stripe** — SaaS-level polish, clear CTAs
- **Linear** — Modern, minimal, professional dashboards
- **Buildertrend** — Construction industry-specific UX patterns

### 1.3 Mood

```
Professional ←————●————→ Friendly
                 ↑
            (Our Position)
            
Modern, Clean, Trustworthy, Actionable
```

---

## 2. Color System

### 2.1 Primary Palette

Based on color psychology research for construction/renovation:
- **Blue** = Trust, reliability, professionalism
- **Orange** = Action, creativity, enthusiasm, warmth
- **Neutral grays** = Balance, sophistication

```css
/* Primary Colors */
--primary: #1E3A5F;           /* Deep Navy Blue - Trust & Professionalism */
--primary-foreground: #FFFFFF;

/* Accent/CTA Colors */
--accent: #F59E0B;            /* Amber/Orange - Action & Warmth */
--accent-foreground: #1E3A5F;
--accent-hover: #D97706;      /* Darker amber on hover */

/* Secondary */
--secondary: #E2E8F0;         /* Light Slate - Subtle backgrounds */
--secondary-foreground: #334155;
```

### 2.2 Full Color Tokens (shadcn/ui Compatible)

```css
@layer base {
  :root {
    /* Backgrounds */
    --background: 210 40% 98%;        /* #F8FAFC - Off-white */
    --foreground: 215 25% 15%;        /* #1E293B - Dark slate */
    
    /* Cards & Surfaces */
    --card: 0 0% 100%;                /* #FFFFFF */
    --card-foreground: 215 25% 15%;
    
    /* Popovers & Dropdowns */
    --popover: 0 0% 100%;
    --popover-foreground: 215 25% 15%;
    
    /* Primary - Deep Navy */
    --primary: 213 54% 24%;           /* #1E3A5F */
    --primary-foreground: 0 0% 100%;
    
    /* Secondary - Light Slate */
    --secondary: 210 40% 93%;         /* #E2E8F0 */
    --secondary-foreground: 215 25% 27%;
    
    /* Muted - Subtle backgrounds */
    --muted: 210 40% 96%;             /* #F1F5F9 */
    --muted-foreground: 215 16% 47%;  /* #64748B */
    
    /* Accent - Amber/Orange */
    --accent: 38 92% 50%;             /* #F59E0B */
    --accent-foreground: 213 54% 24%;
    
    /* Destructive - Error states */
    --destructive: 0 84% 60%;         /* #EF4444 */
    --destructive-foreground: 0 0% 100%;
    
    /* Success - Confirmations */
    --success: 142 76% 36%;           /* #16A34A */
    --success-foreground: 0 0% 100%;
    
    /* Warning - Alerts */
    --warning: 38 92% 50%;            /* #F59E0B - Same as accent */
    --warning-foreground: 213 54% 24%;
    
    /* Borders & Inputs */
    --border: 214 32% 91%;            /* #E2E8F0 */
    --input: 214 32% 91%;
    --ring: 213 54% 24%;              /* Focus ring - Primary */
    
    /* Radius */
    --radius: 0.5rem;
  }
  
  .dark {
    --background: 222 47% 11%;        /* #0F172A - Dark slate */
    --foreground: 210 40% 98%;
    
    --card: 217 33% 17%;              /* #1E293B */
    --card-foreground: 210 40% 98%;
    
    --popover: 217 33% 17%;
    --popover-foreground: 210 40% 98%;
    
    --primary: 38 92% 50%;            /* Amber becomes primary in dark */
    --primary-foreground: 222 47% 11%;
    
    --secondary: 217 33% 17%;
    --secondary-foreground: 210 40% 80%;
    
    --muted: 217 33% 17%;
    --muted-foreground: 215 20% 55%;
    
    --accent: 213 54% 45%;            /* Lighter blue in dark mode */
    --accent-foreground: 210 40% 98%;
    
    --destructive: 0 62% 50%;
    --destructive-foreground: 0 0% 100%;
    
    --border: 217 33% 25%;
    --input: 217 33% 25%;
    --ring: 38 92% 50%;
  }
}
```

### 2.3 Semantic Color Usage

| Color Token | Use Case |
|-------------|----------|
| `--primary` | Headers, navigation, primary buttons, links |
| `--accent` | CTAs ("Get Free Estimate", "Unlock"), highlights, badges |
| `--secondary` | Secondary buttons, card backgrounds, tags |
| `--muted` | Disabled states, placeholder text, subtle backgrounds |
| `--destructive` | Error messages, delete actions |
| `--success` | Success messages, "Unlocked" badge, confirmations |
| `--warning` | Warnings, pending states |

### 2.4 Tier Badge Colors

```css
/* For the 3-tier estimate badges */
--tier-low: 142 76% 36%;      /* Green - #16A34A */
--tier-mid: 38 92% 50%;       /* Amber - #F59E0B */
--tier-high: 262 83% 58%;     /* Purple - #8B5CF6 */
```

### 2.5 Extended Palette (Tailwind Classes)

```javascript
// tailwind.config.js extension
colors: {
  navy: {
    50: '#F0F4F8',
    100: '#D9E2EC',
    200: '#BCCCDC',
    300: '#9FB3C8',
    400: '#829AB1',
    500: '#627D98',
    600: '#486581',
    700: '#334E68',
    800: '#243B53',
    900: '#1E3A5F',  // Primary
    950: '#102A43',
  },
  amber: {
    50: '#FFFBEB',
    100: '#FEF3C7',
    200: '#FDE68A',
    300: '#FCD34D',
    400: '#FBBF24',
    500: '#F59E0B',  // Accent
    600: '#D97706',
    700: '#B45309',
    800: '#92400E',
    900: '#78350F',
  }
}
```

---

## 3. Typography

### 3.1 Font Stack

**Primary Font: Inter**
- Modern, highly legible sans-serif
- Designed for screens
- Excellent at all sizes
- Wide language support

**Monospace: Geist Mono** (for code, prices, tokens)
- Clean, modern monospace
- Pairs well with Inter

```css
/* Font imports */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Or using Next.js font optimization */
import { Inter } from 'next/font/google';

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
});
```

### 3.2 Type Scale

```css
/* Headings */
--text-xs: 0.75rem;      /* 12px */
--text-sm: 0.875rem;     /* 14px */
--text-base: 1rem;       /* 16px - Body */
--text-lg: 1.125rem;     /* 18px */
--text-xl: 1.25rem;      /* 20px */
--text-2xl: 1.5rem;      /* 24px */
--text-3xl: 1.875rem;    /* 30px */
--text-4xl: 2.25rem;     /* 36px */
--text-5xl: 3rem;        /* 48px - Hero */

/* Line Heights */
--leading-tight: 1.25;
--leading-normal: 1.5;
--leading-relaxed: 1.625;

/* Font Weights */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

### 3.3 Typography Classes

```jsx
// Headings
<h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground">
  Know Your Renovation Cost
</h1>

<h2 className="text-2xl md:text-3xl font-semibold text-foreground">
  Section Title
</h2>

<h3 className="text-xl font-semibold text-foreground">
  Card Title
</h3>

// Body Text
<p className="text-base text-muted-foreground leading-relaxed">
  Body text with good readability...
</p>

// Small/Caption
<span className="text-sm text-muted-foreground">
  Caption or helper text
</span>

// Price Display (Monospace)
<span className="font-mono text-2xl font-bold text-foreground">
  $42,500
</span>
```

### 3.4 Responsive Typography

```css
/* Mobile-first responsive headings */
.hero-title {
  @apply text-3xl font-bold tracking-tight;
  @apply md:text-4xl lg:text-5xl;
}

.section-title {
  @apply text-xl font-semibold;
  @apply md:text-2xl lg:text-3xl;
}
```

---

## 4. Spacing & Layout

### 4.1 Spacing Scale

Based on 4px base unit (Tailwind default):

```css
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-5: 1.25rem;   /* 20px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */
--space-10: 2.5rem;   /* 40px */
--space-12: 3rem;     /* 48px */
--space-16: 4rem;     /* 64px */
--space-20: 5rem;     /* 80px */
--space-24: 6rem;     /* 96px */
```

### 4.2 Container Widths

```jsx
// Max widths for content
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
  {/* Main content container */}
</div>

// Narrower for text-heavy content
<div className="max-w-3xl mx-auto">
  {/* Blog posts, documentation */}
</div>

// Cards grid
<div className="max-w-6xl mx-auto">
  {/* Marketplace grid */}
</div>
```

### 4.3 Grid System

```jsx
// Marketplace Project Cards
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {projects.map(project => (
    <ProjectCard key={project.id} {...project} />
  ))}
</div>

// Two-column layout (Chat + Preview)
<div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
  <ChatContainer />
  <EstimatePreview />
</div>
```

### 4.4 Section Spacing

```jsx
// Page sections
<section className="py-16 md:py-24">
  {/* Hero, Features, etc. */}
</section>

// Compact sections
<section className="py-8 md:py-12">
  {/* Smaller sections */}
</section>
```

---

## 5. Component Library

### 5.1 Buttons

```jsx
// Primary CTA (Orange/Amber)
<Button className="bg-accent hover:bg-accent-hover text-accent-foreground font-semibold px-6 py-3 rounded-lg shadow-sm hover:shadow-md transition-all">
  Get Free Estimate
</Button>

// Secondary (Navy outline)
<Button variant="outline" className="border-primary text-primary hover:bg-primary hover:text-primary-foreground">
  I'm a Contractor
</Button>

// Ghost (Subtle)
<Button variant="ghost" className="text-muted-foreground hover:text-foreground">
  Learn More
</Button>

// Destructive
<Button variant="destructive">
  Cancel Project
</Button>
```

### 5.2 Cards

```jsx
// Project Card (Marketplace)
<Card className="border border-border bg-card rounded-xl overflow-hidden hover:shadow-lg transition-shadow">
  <CardHeader className="pb-3">
    <div className="flex items-center justify-between">
      <CardTitle className="text-lg font-semibold">
        Modern Kitchen Renovation
      </CardTitle>
      <Badge variant="outline" className="text-muted-foreground">
        🔒 Locked
      </Badge>
    </div>
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <MapPin className="w-4 h-4" />
      <span>90210</span>
      <span>•</span>
      <Clock className="w-4 h-4" />
      <span>about 2 hours ago</span>
    </div>
  </CardHeader>
  <CardContent>
    <div className="flex gap-2 mb-3">
      <Badge className="bg-secondary text-secondary-foreground">
        Kitchen Remodel
      </Badge>
      <Badge className="bg-amber-100 text-amber-800">
        Mid Tier
      </Badge>
    </div>
    <p className="text-2xl font-bold font-mono text-foreground mb-2">
      $42,500
    </p>
    <p className="text-sm text-muted-foreground line-clamp-2">
      Complete kitchen remodel with new cabinets, quartz countertops...
    </p>
  </CardContent>
  <CardFooter className="border-t border-border pt-4">
    <Button className="w-full bg-accent hover:bg-accent-hover text-accent-foreground font-semibold">
      Unlock Full Scope — $199
    </Button>
  </CardFooter>
</Card>
```

### 5.3 Badges/Tags

```jsx
// Tier Badges
<Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">
  Low Tier
</Badge>
<Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100">
  Mid Tier
</Badge>
<Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100">
  High Tier
</Badge>

// Status Badges
<Badge className="bg-green-500 text-white">
  ✓ UNLOCKED
</Badge>
<Badge variant="outline" className="text-muted-foreground">
  🔒 Locked
</Badge>

// Project Type Tags
<Badge className="bg-secondary text-secondary-foreground">
  Kitchen Remodel
</Badge>
<Badge className="bg-secondary text-secondary-foreground">
  Bathroom Renovation
</Badge>
```

### 5.4 Input Fields

```jsx
// Text Input
<div className="space-y-2">
  <Label htmlFor="zipcode" className="text-sm font-medium">
    ZIP Code
  </Label>
  <Input 
    id="zipcode"
    placeholder="Enter 5-digit ZIP"
    className="border-input focus:ring-2 focus:ring-ring focus:border-transparent"
  />
</div>

// Search with Icon
<div className="relative">
  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
  <Input 
    placeholder="Search by ZIP code..."
    className="pl-10"
  />
</div>
```

### 5.5 Chat Bubbles

```jsx
// AI Message
<div className="flex gap-3 max-w-[80%]">
  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
    <Bot className="w-4 h-4 text-primary-foreground" />
  </div>
  <div className="bg-muted rounded-2xl rounded-tl-none px-4 py-3">
    <p className="text-foreground">
      Great! Let's start with the basics. What type of renovation are you planning?
    </p>
  </div>
</div>

// User Message
<div className="flex gap-3 max-w-[80%] ml-auto flex-row-reverse">
  <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
    <User className="w-4 h-4 text-accent-foreground" />
  </div>
  <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-none px-4 py-3">
    <p>I want to renovate my kitchen</p>
  </div>
</div>
```

---

## 6. Icons

### 6.1 Icon Library

**Primary: Lucide React**
- Clean, consistent stroke-based icons
- Perfect for UI interfaces
- Good accessibility

```bash
npm install lucide-react
```

### 6.2 Common Icons

```jsx
import {
  // Navigation
  Home, Menu, X, ChevronDown, ChevronRight, ArrowRight,
  
  // Actions
  Search, Filter, Download, Upload, Share, Copy, Edit, Trash,
  
  // Status
  Check, CheckCircle, XCircle, AlertCircle, Info, Clock, Lock, Unlock,
  
  // Domain-specific
  Hammer, Ruler, PaintBucket, Wrench, HardHat,
  MapPin, DollarSign, Camera, Image, FileText,
  
  // Users
  User, Users, Building2, Phone, Mail,
  
  // Misc
  Sparkles, Zap, Star, Heart, ThumbsUp
} from 'lucide-react';
```

### 6.3 Icon Sizing

```jsx
// Small (inline with text)
<Check className="w-4 h-4" />

// Default (buttons, list items)
<Home className="w-5 h-5" />

// Medium (cards, features)
<Hammer className="w-6 h-6" />

// Large (empty states, heroes)
<FileText className="w-12 h-12" />
```

---

## 7. Imagery & Media

### 7.1 Image Guidelines

- **Aspect Ratios**: 16:9 for hero images, 4:3 for project photos, 1:1 for thumbnails
- **Quality**: Optimize for web (WebP preferred, JPEG fallback)
- **Alt Text**: Always descriptive for accessibility

### 7.2 Placeholder States

```jsx
// Image loading placeholder
<div className="aspect-video bg-muted animate-pulse rounded-lg" />

// Empty state illustration
<div className="flex flex-col items-center justify-center py-12 text-center">
  <FileText className="w-12 h-12 text-muted-foreground mb-4" />
  <h3 className="text-lg font-medium text-foreground mb-2">
    No projects yet
  </h3>
  <p className="text-muted-foreground">
    Projects you submit will appear here.
  </p>
</div>
```

---

## 8. Motion & Animation

### 8.1 Animation Principles

- **Subtle**: Animations should enhance, not distract
- **Fast**: Keep durations short (150-300ms)
- **Purposeful**: Every animation should have a reason

### 8.2 Tailwind Animation Classes

```jsx
// Fade in on load
<div className="animate-in fade-in duration-300">

// Slide up on appear
<div className="animate-in slide-in-from-bottom-4 duration-300">

// Hover transitions
<Button className="transition-all duration-200 hover:scale-105">

// Loading spinner
<Loader2 className="w-5 h-5 animate-spin" />

// Pulse for loading states
<div className="animate-pulse bg-muted rounded-lg h-4 w-24" />
```

### 8.3 Framer Motion (Optional)

```jsx
import { motion } from 'framer-motion';

// Card hover effect
<motion.div
  whileHover={{ y: -4, boxShadow: '0 10px 30px rgba(0,0,0,0.1)' }}
  transition={{ duration: 0.2 }}
>
  <ProjectCard />
</motion.div>

// Staggered list animation
const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 }
};
```

---

## 9. Dark Mode

### 9.1 Strategy

- Support system preference by default
- Allow manual toggle
- Store preference in localStorage

### 9.2 Implementation

```jsx
// In layout or root component
import { ThemeProvider } from 'next-themes';

function App({ children }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </ThemeProvider>
  );
}

// Theme toggle button
import { Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
    >
      <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
    </Button>
  );
}
```

---

## 10. Accessibility

### 10.1 Requirements

- **WCAG 2.1 AA** compliance minimum
- Color contrast ratio: 4.5:1 for normal text, 3:1 for large text
- Keyboard navigation support
- Screen reader compatibility

### 10.2 Color Contrast

All color combinations in this guide meet WCAG AA standards:

| Combination | Ratio | Pass |
|-------------|-------|------|
| Navy (#1E3A5F) on White | 10.5:1 | ✅ AAA |
| Amber (#F59E0B) on Navy | 5.8:1 | ✅ AA |
| Muted text (#64748B) on White | 4.7:1 | ✅ AA |
| White on Navy | 10.5:1 | ✅ AAA |

### 10.3 Focus States

```css
/* Visible focus ring */
*:focus-visible {
  outline: 2px solid hsl(var(--ring));
  outline-offset: 2px;
}

/* Skip link for keyboard users */
.skip-link {
  @apply sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4;
  @apply bg-background text-foreground px-4 py-2 rounded-md;
}
```

---

## 11. Implementation

### 11.1 File Structure

```
frontend/
├── src/
│   ├── styles/
│   │   ├── globals.css      # CSS variables, base styles
│   │   └── themes.css       # Theme definitions
│   ├── lib/
│   │   └── utils.ts         # cn() helper, etc.
│   └── components/
│       └── ui/              # shadcn/ui components
```

### 11.2 globals.css Setup

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* Paste the color tokens from Section 2.2 */
  }
  
  .dark {
    /* Paste dark mode tokens */
  }
  
  * {
    @apply border-border;
  }
  
  body {
    @apply bg-background text-foreground font-sans antialiased;
  }
}
```

### 11.3 Tailwind Config

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'monospace'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
```

### 11.4 shadcn/ui Installation

```bash
# Initialize shadcn/ui
npx shadcn@latest init

# Add components as needed
npx shadcn@latest add button card badge input label
npx shadcn@latest add dialog dropdown-menu select
npx shadcn@latest add toast sonner
```

---

## Quick Reference

### Color Cheat Sheet

| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| Background | `#F8FAFC` | `#0F172A` |
| Card | `#FFFFFF` | `#1E293B` |
| Primary (Navy) | `#1E3A5F` | `#F59E0B` (swap) |
| Accent (Amber) | `#F59E0B` | `#3B82F6` |
| Text Primary | `#1E293B` | `#F8FAFC` |
| Text Muted | `#64748B` | `#94A3B8` |

### Font Cheat Sheet

| Use | Size | Weight |
|-----|------|--------|
| Hero Title | 48px (3rem) | Bold (700) |
| Section Title | 30px (1.875rem) | Semibold (600) |
| Card Title | 20px (1.25rem) | Semibold (600) |
| Body | 16px (1rem) | Normal (400) |
| Small/Caption | 14px (0.875rem) | Normal (400) |
| Price | 24px (1.5rem) | Bold (700) + Mono |

---

*Last updated: December 2024*