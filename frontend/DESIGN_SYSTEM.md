# RenovationTech Design System - Quick Reference

This document provides quick examples for using the design system in components.

## 🎨 Colors

### Usage in Components

```tsx
// Backgrounds
<div className="bg-background">         // Main page background (#F8FAFC)
<div className="bg-card">                // Card background (white)
<div className="bg-muted">               // Subtle background (#F1F5F9)

// Text Colors
<h1 className="text-foreground">         // Primary text (#1E293B)
<p className="text-muted-foreground">    // Secondary text (#64748B)

// Brand Colors
<button className="bg-primary text-primary-foreground">    // Navy button
<button className="bg-accent text-accent-foreground">     // Orange/Amber CTA button

// Status Colors
<div className="text-success">           // Green for success
<div className="text-destructive">       // Red for errors
<div className="text-warning">           // Amber for warnings

// Tier Badges
<span className="bg-green-100 text-green-800">Low Tier</span>
<span className="bg-amber-100 text-amber-800">Mid Tier</span>
<span className="bg-purple-100 text-purple-800">High Tier</span>
```

## 📝 Typography

```tsx
// Headings
<h1 className="text-4xl md:text-5xl font-bold tracking-tight">
  Hero Title (48px)
</h1>

<h2 className="text-2xl md:text-3xl font-semibold">
  Section Title (30px)
</h2>

<h3 className="text-xl font-semibold">
  Card Title (20px)
</h3>

// Body Text
<p className="text-base text-muted-foreground leading-relaxed">
  Regular paragraph text with good readability
</p>

// Small Text
<span className="text-sm text-muted-foreground">
  Caption or helper text
</span>

// Price Display (uses monospace)
<span className="font-mono text-2xl font-bold">
  $42,500
</span>
```

## 🔘 Buttons

```tsx
// Primary CTA (Orange/Amber)
<button className="px-8 py-4 bg-accent hover:bg-accent/90 text-accent-foreground font-semibold rounded-lg shadow-sm hover:shadow-md transition-all duration-200 hover:scale-105">
  Get Free Estimate
</button>

// Secondary (Navy Outline)
<button className="px-8 py-4 border-2 border-primary text-primary hover:bg-primary hover:text-primary-foreground font-semibold rounded-lg transition-all duration-200">
  I'm a Contractor
</button>

// Ghost/Subtle
<button className="px-4 py-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors">
  Learn More
</button>

// Destructive
<button className="px-4 py-2 bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90">
  Delete
</button>
```

## 🃏 Cards

```tsx
// Basic Card
<div className="bg-card border border-border rounded-xl p-6 shadow-sm hover:shadow-lg transition-shadow">
  <h3 className="text-xl font-semibold mb-2">Card Title</h3>
  <p className="text-muted-foreground">Card content goes here</p>
</div>

// Project Card (Marketplace)
<div className="bg-card border border-border rounded-xl overflow-hidden hover:shadow-lg transition-shadow">
  <div className="p-6 pb-3">
    <div className="flex items-center justify-between mb-2">
      <h3 className="text-lg font-semibold">Modern Kitchen Renovation</h3>
      <span className="text-sm text-muted-foreground">🔒 Locked</span>
    </div>
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span>90210</span>
      <span>•</span>
      <span>2 hours ago</span>
    </div>
  </div>
  <div className="px-6 pb-6">
    <div className="flex gap-2 mb-3">
      <span className="px-3 py-1 bg-secondary text-secondary-foreground rounded-full text-sm">
        Kitchen Remodel
      </span>
      <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm">
        Mid Tier
      </span>
    </div>
    <p className="text-2xl font-bold font-mono mb-2">$42,500</p>
    <p className="text-sm text-muted-foreground line-clamp-2">
      Complete kitchen remodel with new cabinets...
    </p>
  </div>
  <div className="px-6 py-4 border-t border-border">
    <button className="w-full bg-accent hover:bg-accent/90 text-accent-foreground font-semibold py-3 rounded-lg transition-colors">
      Unlock Full Scope — $199
    </button>
  </div>
</div>
```

## 🏷️ Badges

```tsx
// Status Badges
<span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-500 text-white">
  ✓ UNLOCKED
</span>

<span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border border-border text-muted-foreground">
  🔒 Locked
</span>

// Tier Badges
<span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
  Low Tier
</span>
<span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium">
  Mid Tier
</span>
<span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm font-medium">
  High Tier
</span>

// Category Tags
<span className="px-3 py-1 bg-secondary text-secondary-foreground rounded-full text-sm">
  Kitchen Remodel
</span>
```

## 📥 Input Fields

```tsx
// Text Input with Label
<div className="space-y-2">
  <label htmlFor="zipcode" className="text-sm font-medium text-foreground">
    ZIP Code
  </label>
  <input
    id="zipcode"
    type="text"
    placeholder="Enter 5-digit ZIP"
    className="w-full px-4 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
  />
</div>

// Search Input with Icon
<div className="relative">
  <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" /* search icon */>
  <input
    type="search"
    placeholder="Search by ZIP code..."
    className="w-full pl-10 pr-4 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
  />
</div>
```

## 💬 Chat Bubbles

```tsx
// AI Message
<div className="flex gap-3 max-w-[80%]">
  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
    <span className="text-primary-foreground">🤖</span>
  </div>
  <div className="bg-muted rounded-2xl rounded-tl-none px-4 py-3">
    <p className="text-foreground">AI message content here</p>
  </div>
</div>

// User Message (right-aligned)
<div className="flex gap-3 max-w-[80%] ml-auto flex-row-reverse">
  <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
    <span className="text-accent-foreground">👤</span>
  </div>
  <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-none px-4 py-3">
    <p>User message content here</p>
  </div>
</div>
```

## 📐 Layout & Spacing

```tsx
// Container with responsive padding
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
  {/* Main content */}
</div>

// Section spacing
<section className="py-16 md:py-24">
  {/* Hero, Features, etc. */}
</section>

<section className="py-8 md:py-12">
  {/* Smaller sections */}
</section>

// Grid Layouts
// 3-column grid for cards
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {/* Project cards */}
</div>

// 2-column layout
<div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
  {/* Chat + Preview */}
</div>
```

## ✨ Animations

```tsx
// Fade in on mount
<div className="animate-in fade-in duration-300">
  {/* Content */}
</div>

// Slide up animation
<div className="animate-in slide-in-from-bottom-4 duration-300">
  {/* Content */}
</div>

// Hover scale effect
<button className="transition-all duration-200 hover:scale-105">
  Click me
</button>

// Smooth color transitions
<div className="transition-colors duration-200 hover:bg-muted">
  {/* Hover effect */}
</div>

// Loading spinner
<svg className="animate-spin h-5 w-5" /* ... */>
  {/* Spinner icon */}
</svg>

// Pulse for loading states
<div className="animate-pulse bg-muted rounded-lg h-4 w-24" />
```

## 🎯 Common Patterns

### Hero Section
```tsx
<section className="py-16 md:py-24 bg-background">
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
    <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
      Hero Title with <span className="text-accent">Accent</span>
    </h1>
    <p className="text-lg md:text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
      Subtitle text here
    </p>
    <div className="flex gap-4 justify-center">
      {/* CTA buttons */}
    </div>
  </div>
</section>
```

### Empty State
```tsx
<div className="flex flex-col items-center justify-center py-12 text-center">
  <div className="w-12 h-12 text-muted-foreground mb-4">
    {/* Icon */}
  </div>
  <h3 className="text-lg font-medium text-foreground mb-2">
    No projects yet
  </h3>
  <p className="text-muted-foreground mb-6">
    Projects you submit will appear here.
  </p>
  <button className="px-6 py-2 bg-accent text-accent-foreground rounded-lg">
    Get Started
  </button>
</div>
```

## 🌙 Dark Mode (Ready for Future)

The design system is structured to support dark mode. When implementing:

1. Add dark mode class to root element: `<html class="dark">`
2. Uncomment dark mode variables in `src/index.css`
3. All color classes will automatically adapt

---

**Note**: Always use semantic color tokens (like `bg-primary`, `text-muted-foreground`) instead of hard-coded colors. This ensures consistency and makes dark mode implementation easy.

