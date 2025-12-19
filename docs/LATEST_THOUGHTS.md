# Database Design & User Flows - Latest Thoughts

> **Date**: December 18, 2024  
> **Status**: Design Phase - Finalized User Flows & Database Schema  
---

## Table of Contents

1. [Overview](#overview)
2. [Authentication Approach](#authentication-approach)
3. [User Roles](#user-roles)
4. [Token System](#token-system)
5. [Project States](#project-states)
6. [Core Entities](#core-entities)
7. [Complete User Flows](#complete-user-flows)
8. [Email Notifications](#email-notifications)
9. [UI Components](#ui-components)
10. [Database Schema](#database-schema)
11. [Key Design Decisions](#key-design-decisions)
12. [Data Access Patterns](#data-access-patterns)

---

## Overview

RenovationTech is a marketplace connecting homeowners with contractors through AI-powered renovation estimates. The platform operates **without traditional authentication** - instead using a **token-based access system** for both homeowners and contractors.

### Core Principle

**No Login/Registration**: Both homeowners and contractors see the same website. Access to specific projects is controlled via unique tokens that act as both identifiers and authentication.

---

## Authentication Approach

### No Traditional Auth

- ❌ No username/password
- ❌ No OAuth (Google, Facebook, etc.)
- ❌ No user accounts or profiles
- ✅ Token-based access only
- ✅ Email used for notifications, not authentication

### Why This Approach?

1. **Simplicity**: Reduces friction for homeowners getting estimates
2. **Privacy**: No account creation required
3. **Flexibility**: Easy to use, just save a code
4. **Future-proof**: Can add auth later without breaking core flows

---

## User Roles

### Three Types of Visitors

| Role | Behavior | Access |
|------|----------|--------|
| **Homeowner** | Creates project, gets estimate, publishes to marketplace | Uses `PRJ-` tokens |
| **Contractor** | Browses marketplace, unlocks projects, contacts homeowners | Uses `UNL-` tokens |
| **Random Visitor** | Browses public marketplace, sees locked project previews | No token needed |

**Important**: All three see the same website. The role is implicit based on their actions and tokens.

---

## Token System

### Two Token Types

#### 1. Project Token (PRJ-)
- **Format**: `PRJ-7X9K2M` (6 alphanumeric characters)
- **Owner**: Homeowner
- **Purpose**: Access and manage their renovation project
- **Generated**: When homeowner saves project
- **Lifetime**: Permanent (or until project deleted)

#### 2. Unlock Token (UNL-)
- **Format**: `UNL-4B8T3N` (6 alphanumeric characters)
- **Owner**: Contractor
- **Purpose**: Access unlocked project details and homeowner contact info
- **Generated**: When contractor initiates payment
- **Lifetime**: Active until project marked complete by both parties

### Token Design Features

```
PRJ-7X9K2M
│   └─────┘
│     └──── Random alphanumeric (uppercase + numbers)
└────────── Prefix identifies token type (homeowner vs contractor)
```

**Security Considerations**:
- 6 characters = 36^6 = ~2.1 billion combinations
- Uppercase + numbers only (easy to read, no confusion between 0/O, 1/I)
- Prefixes prevent cross-token attacks
- No sequential/guessable patterns

---

## Project States

### State Machine

```
┌─────────┐
│  draft  │ ─────────────────────────────────────┐
└────┬────┘                                      │
     │ User clicks "Save Project"               │
     ▼                                           │
┌───────────┐                                    │
│ completed │ ─────────────────────────────────┐ │
└─────┬─────┘                                  │ │
      │ User clicks "Publish to Marketplace"   │ │
      ▼                                         │ │
┌───────────┐                                   │ │
│ published │◄──┐                               │ │
└─────┬─────┘   │                               │ │
      │         │ (Future: Republish feature)   │ │
      │         │                               │ │
      │ Contractor pays & unlocks              │ │
      ▼         │                               │ │
┌───────────┐   │                               │ │
│ unlocked  │───┘                               │ │
└─────┬─────┘                                   │ │
      │                                         │ │
      │ Both parties mark complete             │ │
      ▼                                         │ │
┌───────────┐                                   │ │
│ completed │                                   │ │
└───────────┘                                   │ │
      │                                         │ │
      │ (Either party clicks "Close")          │ │
      ▼                                         │ │
┌───────────┐                                   │ │
│  closed   │◄──────────────────────────────────┘ │
└───────────┘◄──────────────────────────────────┘
```

### State Definitions

| State | Description | Visible in Marketplace? | Can Edit? | Can Close? |
|-------|-------------|------------------------|-----------|------------|
| **draft** | Chat in progress, estimation incomplete | ❌ No | ✅ Yes | ✅ Yes |
| **completed** | Estimation done, token issued, but not published | ❌ No | ✅ Yes | ✅ Yes |
| **published** | Visible in marketplace with locked details, awaiting unlock | ✅ Yes (preview only) | ❌ No | ✅ Yes (only if not unlocked) |
| **unlocked** | Contractor paid, has access, off marketplace | ❌ No | ❌ No | ❌ No (contractor paid!) |
| **completed** | Both parties marked work as complete | ❌ No | ❌ No | ✅ Yes |
| **closed** | Manually closed or archived | ❌ No | ❌ No | N/A |

### State Transition Rules

**From `draft` → `completed`:**
- Trigger: User clicks "Save Project" button
- Requirements: Estimation completed in chat
- Actions: Generate `PRJ-` token, save conversation state, send email

**From `completed` → `published`:**
- Trigger: User clicks "Publish to Marketplace" 
- Requirements: Homeowner provides name, email, phone
- Actions: Update project with contact info, change status

**From `published` → `unlocked`:**
- Trigger: Contractor completes payment
- Requirements: Payment verified via webhook
- Actions: Create unlock record, change status, remove from marketplace, send emails

**From `unlocked` → `completed`:**
- Trigger: Both homeowner AND contractor mark complete
- Requirements: `homeowner_marked_complete = TRUE` AND `contractor_marked_complete = TRUE`
- Actions: Set `completed_at` timestamp

**From any state → `closed`:**
- Trigger: User clicks "Close Project"
- Requirements: 
  - If `published`: Can close (no contractor paid yet)
  - If `unlocked` or `completed`: Cannot close (contractor paid)
- Actions: Archive project, remove from all views

---

## Core Entities

### Overview

We need **4 main tables**:

1. **Projects** - Renovation project data and metadata
2. **Unlocks** - Tracking which contractors unlocked which projects
3. **ConversationStates** - LangGraph chat state persistence
4. **LLMCosts** - Analytics for AI model usage (optional)

---

## Complete User Flows

### Flow A: Homeowner Journey (Complete)

```
┌──────────────────────────────────────────────────────────────┐
│                    HOMEOWNER JOURNEY                          │
└──────────────────────────────────────────────────────────────┘

STEP 1: Discovery & Estimation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User visits website
  ↓
Clicks "Get Free Estimate"
  ↓
Enters AI chat flow (LangGraph)
  ↓
Answers questions:
  - Project type (kitchen, bathroom, etc.)
  - ZIP code
  - Uploads images
  - Describes renovation vision
  ↓
AI generates 3-tier estimate:
  - Low: $30,000
  - Mid: $45,000
  - High: $65,000
  ↓
User selects preferred tier (e.g., Mid)


STEP 2: Save Project
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Clicks "Save Project" button
  ↓
Popup appears:
┌────────────────────────────────────┐
│  💾 Save Your Project              │
├────────────────────────────────────┤
│  Enter your email to receive       │
│  your project code:                │
│                                    │
│  Email: [________________]         │
│                                    │
│  [Cancel]  [Save & Email Code]     │
└────────────────────────────────────┘
  ↓
User enters: john@example.com
  ↓
Backend processes:
  ├─ Check if project has token
  │  ├─ If NO: Generate PRJ-XXXXXX
  │  └─ If YES: Use existing token
  ├─ Save conversation state to DB
  ├─ Update status: "draft" → "completed"
  ├─ Check if email already sent
  │  ├─ If NO: Send email with token
  │  │  └─ Set homeowner_email_sent = TRUE
  │  └─ If YES: Skip email
  └─ Return success
  ↓
Success popup appears:
┌────────────────────────────────────┐
│  ✅ Project Saved!                 │
├────────────────────────────────────┤
│  Your project code:                │
│                                    │
│  ┌──────────────────────────────┐ │
│  │      PRJ-7X9K2M              │ │
│  │  [Copy]        [Download]    │ │
│  └──────────────────────────────┘ │
│                                    │
│  📧 Code sent to:                  │
│     john@example.com               │
│                                    │
│  💡 Save this code to access       │
│     your project anytime!          │
│                                    │
│  [Go to My Projects]  [Close]      │
└────────────────────────────────────┘


STEP 3: Publish to Marketplace
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Later, user wants to find contractors
  ↓
Goes to "My Projects" page
  ↓
Enters token: PRJ-7X9K2M
  ↓
Views project details:
┌────────────────────────────────────┐
│  🏠 Kitchen Renovation             │
│  Status: Completed                 │
├────────────────────────────────────┤
│  📊 Your Estimate:                 │
│  ✓ Low:  $30,000                   │
│  ✓ Mid:  $45,000 (You selected)    │
│  ✓ High: $65,000                   │
│                                    │
│  📍 Location: ZIP 10001            │
│  📷 Images: 5 uploaded             │
│                                    │
│  [📤 Publish to Marketplace]       │
└────────────────────────────────────┘
  ↓
Clicks "Publish to Marketplace"
  ↓
Form appears:
┌────────────────────────────────────┐
│  📤 Publish Your Project           │
├────────────────────────────────────┤
│  Contractors will see:             │
│  • Project type & location         │
│  • Budget estimate                 │
│  • Brief project description       │
│                                    │
│  Your contact info (required):     │
│                                    │
│  Name:  [John Doe_________]        │
│  Email: john@example.com (saved)   │
│  Phone: [(555) 123-4567___]        │
│                                    │
│  ⚠️ Contact info shown only after  │
│     contractor pays to unlock      │
│                                    │
│  [Cancel]  [Publish Now]           │
└────────────────────────────────────┘
  ↓
User fills form and submits
  ↓
Backend updates:
  ├─ Save homeowner_name, homeowner_phone
  ├─ Update status: "completed" → "published"
  └─ Project now visible in marketplace
  ↓
Success message:
┌────────────────────────────────────┐
│  ✅ Published!                     │
│                                    │
│  Your project is now live in       │
│  the contractor marketplace.       │
│                                    │
│  You'll receive email notifications│
│  when contractors unlock your      │
│  project.                          │
└────────────────────────────────────┘


STEP 4: Waiting for Contractors
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project appears in marketplace (details locked)
  ↓
Homeowner waits...
  ↓
📧 Email notification arrives:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject: A Contractor Has Unlocked Your Project!

Good news! A contractor is interested in your renovation.

Project: Kitchen Renovation
Budget: $45,000

The contractor can now see your contact details
and will reach out soon.

View contractor details:
https://renovationtech.com/projects?token=PRJ-7X9K2M
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


STEP 5: Contractor Unlocked - View Details
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Homeowner goes to My Projects
  ↓
Enters PRJ-7X9K2M
  ↓
Sees updated project:
┌────────────────────────────────────┐
│  🏠 Kitchen Renovation             │
│  Status: ⚡ UNLOCKED               │
├────────────────────────────────────┤
│  ✅ A contractor has unlocked      │
│     your project!                  │
│                                    │
│  👷 Contractor Details:            │
│  • Email: mike@reno.com            │
│  • Waiting for contractor to       │
│    save their details...           │
└────────────────────────────────────┘
  ↓
Later, receives another email:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject: Contractor Details Available

The contractor has saved their contact info:

Name:    Mike's Renovations
Email:   mike@reno.com
Phone:   (555) 987-6543
Company: Mike's Renovations LLC

They can see your details and may contact
you directly.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ↓
Homeowner views updated project:
┌────────────────────────────────────┐
│  🏠 Kitchen Renovation             │
│  Status: ⚡ UNLOCKED               │
├────────────────────────────────────┤
│  👷 Contractor Details:            │
│  • Name:    Mike's Renovations     │
│  • Email:   mike@reno.com          │
│  • Phone:   (555) 987-6543         │
│  • Company: Mike's Renovations LLC │
│                                    │
│  💬 They will contact you soon!    │
│                                    │
│  [✓ Mark as Completed]             │
│                                    │
│  ℹ️ Project closes only when both  │
│     you and contractor mark it     │
│     as completed                   │
└────────────────────────────────────┘


STEP 6: Work & Completion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Contractor contacts homeowner
  ↓
They discuss project, agree on terms
  ↓
Work progresses...
  ↓
Work completed!
  ↓
Homeowner clicks "Mark as Completed"
  ↓
Status updated:
  homeowner_marked_complete = TRUE
  ↓
UI shows:
┌────────────────────────────────────┐
│  ⏳ Waiting for contractor to      │
│     mark as completed...           │
└────────────────────────────────────┘
  ↓
When contractor also marks complete:
  ↓
Backend updates:
  ├─ homeowner_marked_complete = TRUE
  ├─ contractor_marked_complete = TRUE
  ├─ status: "unlocked" → "completed"
  └─ completed_at = NOW()
  ↓
Project marked as complete!
```

---

### Flow B: Contractor Journey (Complete)

```
┌──────────────────────────────────────────────────────────────┐
│                   CONTRACTOR JOURNEY                          │
└──────────────────────────────────────────────────────────────┘

STEP 1: Marketplace Browsing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Visitor goes to "Marketplace" page
  ↓
Sees list of published projects:
┌────────────────────────────────────┐
│  🏪 Contractor Marketplace         │
├────────────────────────────────────┤
│  Filter: [Kitchen ▼] [ZIP: 10001] │
│          [$20k-$50k ▼]             │
├────────────────────────────────────┤
│  ┌──────────────────────────────┐  │
│  │ 🏠 Kitchen Renovation        │  │
│  │ 📍 ZIP: 10001                │  │
│  │ 💰 Budget: $45,000           │  │
│  │ 📅 Posted: 2 days ago        │  │
│  │                              │  │
│  │ 📝 Brief: Full kitchen       │  │
│  │    remodel with new cabinets │  │
│  │                              │  │
│  │ 🔒 Full details locked       │  │
│  │                              │  │
│  │ [🔓 Unlock Full Scope $199]  │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ 🏠 Bathroom Renovation       │  │
│  │ ... (more projects)          │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘


STEP 2: Initiate Unlock
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Clicks "Unlock Full Scope $199"
  ↓
Modal appears:
┌────────────────────────────────────┐
│  🔓 Unlock Project Details         │
├────────────────────────────────────┤
│  Price: $199                       │
│                                    │
│  You'll get access to:             │
│  ✓ Full 3-tier cost breakdown      │
│  ✓ Homeowner contact information   │
│  ✓ All project images              │
│  ✓ Detailed scope & measurements   │
│                                    │
│  Enter your email to receive       │
│  unlock code:                      │
│                                    │
│  Email: [_____________________]    │
│                                    │
│  [Cancel]  [Proceed to Payment]    │
└────────────────────────────────────┘
  ↓
Enters: contractor@example.com
  ↓
Clicks "Proceed to Payment"


STEP 3: Payment Processing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Backend creates unlock record:
  ├─ Generate UNL-XXXXXX token
  ├─ project_id: 123
  ├─ contractor_email: contractor@example.com
  ├─ payment_status: "pending"
  ├─ is_active: FALSE
  └─ contractor_details_saved: FALSE
  ↓
Redirect to Stripe Checkout:
  URL: /payment?unlock_token=UNL-4B8T3N
  Metadata: { unlock_token: "UNL-4B8T3N" }
  ↓
Stripe payment page loads
  (User might refresh, close tab, etc.)
  ↓
User enters card info and pays
  ↓
Stripe webhook fires:
  POST /webhooks/stripe
  {
    "event": "checkout.session.completed",
    "metadata": { "unlock_token": "UNL-4B8T3N" }
  }
  ↓
Backend processes webhook:
  ├─ Find unlock by token UNL-4B8T3N
  ├─ Update unlock:
  │  ├─ payment_status: "completed"
  │  ├─ is_active: TRUE
  │  └─ unlocked_at: NOW()
  ├─ Update project:
  │  └─ status: "published" → "unlocked"
  ├─ Send email to contractor (with unlock code)
  └─ Send email to homeowner (notification)


STEP 4: Receive Unlock Email
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Contractor receives email:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject: Project Unlocked - UNL-4B8T3N

Congratulations! You've unlocked a renovation project.

Your Unlock Code: UNL-4B8T3N

Project Summary:
• Type: Kitchen Renovation
• Budget: $45,000 (Mid Tier)
• Location: ZIP 10001

Homeowner Contact:
• Name:  John Doe
• Email: john@example.com
• Phone: (555) 123-4567

View full details and save your contact info:
https://renovationtech.com/projects?token=UNL-4B8T3N

⚠️ You must save your details so the homeowner
   can reach you!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


STEP 5: Access Project with Token
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Contractor clicks link or goes to My Projects
  ↓
Enters token: UNL-4B8T3N
  ↓
Backend checks:
  ├─ Token exists? YES
  ├─ Payment completed? YES
  ├─ Contractor details saved? NO
  └─ Result: FORCE DETAILS FORM


STEP 6: FORCED Details Form
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before showing homeowner info, form appears:
┌────────────────────────────────────┐
│  👤 Save Your Contact Details      │
│  (Required to view homeowner info) │
├────────────────────────────────────┤
│  All fields required:              │
│                                    │
│  Name:    [___________________]    │
│                                    │
│  Email:   contractor@example.com   │
│           (pre-filled)             │
│                                    │
│  Phone:   [___________________]    │
│                                    │
│  Company: [___________________]    │
│                                    │
│  ℹ️ Homeowner will see these       │
│     details to contact you back    │
│                                    │
│  [Save & View Project]             │
└────────────────────────────────────┘
  ↓
Contractor fills:
  Name:    Mike Smith
  Phone:   (555) 987-6543
  Company: Mike's Renovations LLC
  ↓
Submits form
  ↓
Backend updates:
  ├─ Update unlock record:
  │  ├─ contractor_name: "Mike Smith"
  │  ├─ contractor_phone: "(555) 987-6543"
  │  ├─ contractor_company: "Mike's Renovations LLC"
  │  └─ contractor_details_saved: TRUE
  └─ Send email to homeowner with contractor details
  ↓
Form disappears, project details shown


STEP 7: View Full Project Details
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Full project page loads:
┌────────────────────────────────────┐
│  🏠 Kitchen Renovation - ZIP 10001 │
│  Your Unlock Code: UNL-4B8T3N      │
├────────────────────────────────────┤
│  📊 Full 3-Tier Estimate:          │
│  ┌──────────────────────────────┐  │
│  │ 💵 Low Tier:  $30,000        │  │
│  │ • Basic materials            │  │
│  │ • Standard labor             │  │
│  │ • [View Breakdown]           │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │ 💰 Mid Tier:  $45,000        │  │
│  │ ⭐ Homeowner Selected This    │  │
│  │ • Quality materials          │  │
│  │ • Experienced labor          │  │
│  │ • [View Breakdown]           │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │ 💎 High Tier: $65,000        │  │
│  │ • Premium materials          │  │
│  │ • Expert craftsmen           │  │
│  │ • [View Breakdown]           │  │
│  └──────────────────────────────┘  │
├────────────────────────────────────┤
│  🏠 Homeowner Contact:             │
│  • Name:  John Doe                 │
│  • Email: john@example.com         │
│  • Phone: (555) 123-4567           │
├────────────────────────────────────┤
│  📷 Project Images (5):            │
│  [🖼️] [🖼️] [🖼️] [🖼️] [🖼️]        │
│  [View Gallery]                    │
├────────────────────────────────────┤
│  📝 Detailed Scope:                │
│  Materials:                        │
│  • Cabinets: Maple wood, shaker    │
│  • Countertops: Granite            │
│  • Appliances: Stainless steel     │
│  ...                               │
│                                    │
│  Measurements:                     │
│  • Room: 12' x 14'                 │
│  • Countertop: 8 linear feet       │
│  ...                               │
├────────────────────────────────────┤
│  [✓ Mark as Completed]             │
│                                    │
│  ℹ️ Project closes when both you   │
│     and homeowner mark complete    │
└────────────────────────────────────┘


STEP 8: Contact Homeowner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Contractor calls/emails homeowner
  ↓
Discusses project details
  ↓
Negotiates pricing, timeline
  ↓
Work begins!


STEP 9: Update Details (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If contractor wants to update their info:
  ↓
Goes to My Projects → Enters UNL-4B8T3N
  ↓
Clicks "Edit My Details"
  ↓1
Form appears (pre-filled):
┌────────────────────────────────────┐
│  ✏️ Update Your Contact Details    │
├────────────────────────────────────┤
│  Name:    [Mike Smith_________]    │
│  Email:   contractor@example.com   │
│  Phone:   [(555) 987-6543_____]    │
│  Company: [Mike's Renovations_]    │
│                                    │
│  [Cancel]  [Update]                │
└────────────────────────────────────┘
  ↓
Makes changes and submits
  ↓
Backend updates unlock record
  ↓
Homeowner sees updated details next time


STEP 10: Mark Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Work completed!
  ↓
Contractor goes to My Projects
  ↓
Views project with UNL-4B8T3N
  ↓
Clicks "Mark as Completed"
  ↓
Backend updates:
  contractor_marked_complete = TRUE
  ↓
If homeowner already marked complete:
  ├─ status: "unlocked" → "completed"
  ├─ completed_at: NOW()
  └─ Both parties notified
  ↓
If homeowner has NOT marked complete:
  └─ Show: "Waiting for homeowner..."
```

---

## Email Notifications

### Email 1: Homeowner - Project Saved

**Trigger**: When homeowner clicks "Save Project" (sent only once)

**Recipient**: Homeowner email

**Subject**: Your Project Code - PRJ-7X9K2M

**Body**:
```
Hi!

Your renovation estimate has been saved.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project Code: PRJ-7X9K2M
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Project Details:
• Type: Kitchen Renovation
• Estimated Cost: $45,000 (Mid Tier)
• Location: ZIP 10001

Access your project anytime:
→ https://renovationtech.com/projects?token=PRJ-7X9K2M

───────────────────────────────────
📤 Ready to find contractors?
───────────────────────────────────

To publish your project to the marketplace:
1. Visit "My Projects"
2. Enter your project code
3. Click "Publish to Marketplace"

Your project will be visible to qualified contractors
in your area.

───────────────────────────────────
💡 Important: Save this code!
───────────────────────────────────

You'll need this code to access and manage your
project. We recommend:
• Taking a screenshot
• Saving this email
• Writing it down

Questions? Visit our Help Center or reply to this email.

Best regards,
The RenovationTech Team
```

---

### Email 2: Contractor - Project Unlocked

**Trigger**: After payment webhook confirms successful payment

**Recipient**: Contractor email (entered before payment)

**Subject**: Project Unlocked - UNL-4B8T3N

**Body**:
```
Congratulations! You've unlocked a renovation project.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Your Unlock Code: UNL-4B8T3N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Save this code! You'll use it to access the project
details anytime.

───────────────────────────────────
📋 Project Summary
───────────────────────────────────

Project Type:   Kitchen Renovation
Budget:         $45,000 (Mid Tier)
Location:       ZIP 10001
Posted:         2 days ago

───────────────────────────────────
🏠 Homeowner Contact
───────────────────────────────────

Name:   John Doe
Email:  john@example.com
Phone:  (555) 123-4567

───────────────────────────────────
🔓 View Full Details
───────────────────────────────────

Access the complete project breakdown, images,
and measurements:

→ https://renovationtech.com/projects?token=UNL-4B8T3N

⚠️ IMPORTANT: You must save your contact details
   so the homeowner can reach you!

When you visit the link above, you'll be asked to
provide your name, phone, and company. This allows
the homeowner to contact you back.

───────────────────────────────────
💼 Next Steps
───────────────────────────────────

1. Review the full project details
2. Save your contact information
3. Reach out to the homeowner
4. Discuss the project and provide your quote

Good luck with this project!

Best regards,
The RenovationTech Team
```

---

### Email 3: Homeowner - Project Unlocked Notification

**Trigger**: Immediately after contractor payment confirmed

**Recipient**: Homeowner email

**Subject**: A Contractor Has Unlocked Your Project!

**Body**:
```
Good news! A contractor is interested in your renovation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project: Kitchen Renovation
Budget: $45,000
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A qualified contractor has unlocked your project
and can now see your contact details.

───────────────────────────────────
👷 What Happens Next?
───────────────────────────────────

The contractor has access to:
✓ Your name, email, and phone number
✓ Full project scope and images
✓ Your selected estimate tier

They will reach out to you soon to:
• Discuss the project details
• Ask any clarifying questions
• Provide their professional assessment
• Schedule a site visit (if needed)

───────────────────────────────────
📋 View Contractor Details
───────────────────────────────────

The contractor will save their contact information
shortly. You'll receive another email when their
details are available.

View your project:
→ https://renovationtech.com/projects?token=PRJ-7X9K2M

Your Project Code: PRJ-7X9K2M

───────────────────────────────────
💡 Tips for Working with Contractors
───────────────────────────────────

• Respond promptly to their inquiries
• Ask about licensing and insurance
• Request references from past projects
• Get everything in writing
• Discuss timeline and payment schedule

Questions? Reply to this email or visit our Help Center.

Best regards,
The RenovationTech Team
```

---

### Email 4: Homeowner - Contractor Details Saved

**Trigger**: After contractor submits their contact details

**Recipient**: Homeowner email

**Subject**: Contractor Details Available - Kitchen Renovation

**Body**:
```
The contractor who unlocked your project has saved
their contact details.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project: Kitchen Renovation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

───────────────────────────────────
👷 Contractor Information
───────────────────────────────────

Name:    Mike Smith
Email:   mike@reno.com
Phone:   (555) 987-6543
Company: Mike's Renovations LLC

───────────────────────────────────
💬 Communication
───────────────────────────────────

The contractor can see your contact details and
may reach out directly via phone or email.

You can also contact them using the information above.

View full project details:
→ https://renovationtech.com/projects?token=PRJ-7X9K2M

Your Project Code: PRJ-7X9K2M

───────────────────────────────────
🤝 Next Steps
───────────────────────────────────

• Wait for contractor to reach out, or contact them
• Discuss project scope and expectations
• Ask for detailed quote and timeline
• Check references and credentials
• Finalize agreement and begin work

Once the project is complete, both you and the
contractor can mark it as completed.

Questions? Reply to this email.

Best regards,
The RenovationTech Team
```

---

## UI Components

### Component 1: My Projects Page (Universal)

**URL**: `/projects`

**Purpose**: Single page for both homeowners and contractors

**UI**:
```
┌─────────────────────────────────────────┐
│  🏠 My Projects                         │
├─────────────────────────────────────────┤
│                                         │
│  Enter your project or unlock token:   │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ PRJ-7X9K2M or UNL-4B8T3N          │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [View Project]                         │
│                                         │
│  ───────────────────────────────────   │
│                                         │
│  💡 Tips:                               │
│  • Homeowner tokens start with PRJ-    │
│  • Contractor tokens start with UNL-   │
│  • Check your email for your token     │
│                                         │
└─────────────────────────────────────────┘
```

**Backend Logic**:
```python
def view_project(token: str):
    if token.startswith("PRJ-"):
        # Homeowner view
        project = get_project_by_token(token)
        return render_homeowner_view(project)
    
    elif token.startswith("UNL-"):
        # Contractor view
        unlock = get_unlock_by_token(token)
        
        if not unlock.contractor_details_saved:
            # FORCE details form first
            return render_contractor_details_form(unlock)
        else:
            # Show full project
            return render_contractor_view(unlock)
    
    else:
        return error("Invalid token")
```

---

### Component 2: Marketplace Cards

**Display**: Grid of project cards (status = "published")

**Individual Card**:
```
┌──────────────────────────────────┐
│ 🏠 Kitchen Renovation            │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ 📍 Location: ZIP 10001           │
│ 💰 Budget:   $45,000             │
│ 📅 Posted:   2 days ago          │
│                                  │
│ 📝 Brief Scope:                  │
│    Full kitchen remodel with     │
│    new cabinets, countertops,    │
│    and appliances.               │
│                                  │
│ 🔒 Full details locked           │
│                                  │
│ [🔓 Unlock Full Scope $199]      │
└──────────────────────────────────┘
```

**Query**:
```sql
SELECT id, project_type, zip_code, total_price, 
       brief_scope, created_at
FROM projects
WHERE status = 'published'
ORDER BY created_at DESC
```

---

### Component 3: Homeowner Project View (After Publish)

**When**: Homeowner views published/unlocked project

```
┌────────────────────────────────────────┐
│  🏠 Kitchen Renovation                 │
│  Your Code: PRJ-7X9K2M                 │
├────────────────────────────────────────┤
│  Status: ⚡ UNLOCKED                   │
│                                        │
│  ✅ A contractor has unlocked your     │
│     project and can see your details   │
├────────────────────────────────────────┤
│  📊 Your Selected Estimate:            │
│  • Tier: Mid                           │
│  • Price: $45,000                      │
│  • [View Full Breakdown]               │
├────────────────────────────────────────┤
│  📞 Your Contact Info (visible):       │
│  • Name:  John Doe                     │
│  • Email: john@example.com             │
│  • Phone: (555) 123-4567               │
├────────────────────────────────────────┤
│  👷 Contractor Details:                │
│  • Name:    Mike Smith                 │
│  • Email:   mike@reno.com              │
│  • Phone:   (555) 987-6543             │
│  • Company: Mike's Renovations LLC     │
│                                        │
│  💬 Contractor can contact you!        │
├────────────────────────────────────────┤
│  [✓ Mark as Completed]                 │
│                                        │
│  ℹ️ Project closes when both parties   │
│     mark it as completed               │
└────────────────────────────────────────┘
```

---

### Component 4: Contractor Project View (After Details Saved)

**When**: Contractor views unlocked project

```
┌────────────────────────────────────────┐
│  🏠 Kitchen Renovation - ZIP 10001     │
│  Your Unlock Code: UNL-4B8T3N          │
├────────────────────────────────────────┤
│  📊 Full 3-Tier Estimate:              │
│  ┌──────────────────────────────────┐  │
│  │ 💵 Low:  $30,000                 │  │
│  │    [View Breakdown]              │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │ 💰 Mid:  $45,000 ⭐ Selected     │  │
│  │    [View Breakdown]              │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │ 💎 High: $65,000                 │  │
│  │    [View Breakdown]              │  │
│  └──────────────────────────────────┘  │
├────────────────────────────────────────┤
│  🏠 Homeowner Contact:                 │
│  • Name:  John Doe                     │
│  • Email: john@example.com             │
│  • Phone: (555) 123-4567               │
├────────────────────────────────────────┤
│  📷 Project Images (5):                │
│  [🖼️] [🖼️] [🖼️] [🖼️] [🖼️]            │
│  [View Gallery]                        │
├────────────────────────────────────────┤
│  📝 Detailed Scope:                    │
│  Materials, measurements, preferences  │
│  [View Full Details]                   │
├────────────────────────────────────────┤
│  👤 Your Details:                      │
│  • Name:    Mike Smith                 │
│  • Email:   mike@reno.com              │
│  • Phone:   (555) 987-6543             │
│  • Company: Mike's Renovations LLC     │
│                                        │
│  [Edit My Details]                     │
├────────────────────────────────────────┤
│  [✓ Mark as Completed]                 │
│                                        │
│  ℹ️ Project closes when both parties   │
│     mark it as completed               │
└────────────────────────────────────────┘
```

---

## Database Schema

### Table 1: `projects`

**Purpose**: Store all renovation project data

```sql
CREATE TABLE projects (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token VARCHAR(20) UNIQUE NOT NULL,  -- PRJ-XXXXXX
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- Values: 'draft', 'completed', 'published', 'unlocked', 'completed', 'closed'
    
    -- Homeowner information
    homeowner_name VARCHAR(255),
    homeowner_email VARCHAR(255),
    homeowner_phone VARCHAR(50),
    homeowner_email_sent BOOLEAN DEFAULT FALSE,
    
    -- Project basics (for marketplace preview)
    project_type VARCHAR(100),       -- e.g., "kitchen", "bathroom"
    zip_code VARCHAR(10),
    accepted_tier VARCHAR(10),       -- "low", "mid", "high"
    total_price DECIMAL(10,2),
    brief_scope TEXT,                -- Short description for marketplace
    
    -- Full project data (JSON columns)
    full_estimate JSONB,             -- Complete 3-tier breakdown
    images JSONB,                    -- Array of image objects
    extracted_data JSONB,            -- Materials, measurements, etc.
    renovation_vision JSONB,         -- Homeowner's vision/preferences
    generated_image_url TEXT,        -- AI-generated preview image
    
    -- Completion tracking (two-party system)
    homeowner_marked_complete BOOLEAN DEFAULT FALSE,
    contractor_marked_complete BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP           -- Set when both mark complete
);

-- Indexes for performance
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_token ON projects(token);
CREATE INDEX idx_projects_zip ON projects(zip_code);
CREATE INDEX idx_projects_type ON projects(project_type);
CREATE INDEX idx_projects_created ON projects(created_at DESC);

-- Index for marketplace queries (composite)
CREATE INDEX idx_projects_marketplace 
    ON projects(status, zip_code, project_type, total_price)
    WHERE status = 'published';
```

**Example Row**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "token": "PRJ-7X9K2M",
  "created_at": "2024-12-18T10:00:00Z",
  "updated_at": "2024-12-18T14:30:00Z",
  "status": "unlocked",
  
  "homeowner_name": "John Doe",
  "homeowner_email": "john@example.com",
  "homeowner_phone": "(555) 123-4567",
  "homeowner_email_sent": true,
  
  "project_type": "kitchen",
  "zip_code": "10001",
  "accepted_tier": "mid",
  "total_price": 45000.00,
  "brief_scope": "Full kitchen remodel with new cabinets, countertops, and appliances.",
  
  "full_estimate": {
    "low": { /* tier details */ },
    "mid": { /* tier details */ },
    "high": { /* tier details */ }
  },
  "images": [
    { "id": "img1", "url": "/images/proj1-1.jpg", "analysis": "..." }
  ],
  "extracted_data": {
    "materials": [...],
    "measurements": {...},
    "colors": [...]
  },
  "renovation_vision": {
    "style_preferences": "Modern farmhouse",
    "material_preferences": "Natural wood"
  },
  "generated_image_url": "/images/generated/proj1-preview.jpg",
  
  "homeowner_marked_complete": false,
  "contractor_marked_complete": false,
  "completed_at": null
}
```

---

### Table 2: `unlocks`

**Purpose**: Track contractor unlocks and their details

```sql
CREATE TABLE unlocks (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    unlock_token VARCHAR(20) UNIQUE NOT NULL,  -- UNL-XXXXXX
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    unlocked_at TIMESTAMP,           -- When payment completed
    invalidated_at TIMESTAMP,        -- Future: if republish feature added
    
    -- Payment information
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Values: 'pending', 'completed', 'failed'
    payment_id VARCHAR(100),         -- Stripe payment/checkout session ID
    amount DECIMAL(10,2) DEFAULT 199.00,
    
    -- Contractor details
    contractor_email VARCHAR(255) NOT NULL,
    contractor_name VARCHAR(255),
    contractor_phone VARCHAR(50),
    contractor_company VARCHAR(255),
    contractor_details_saved BOOLEAN DEFAULT FALSE,
    
    -- Status
    is_active BOOLEAN DEFAULT FALSE,
    
    -- Constraint: Only one active unlock per project
    CONSTRAINT one_active_unlock_per_project 
        UNIQUE(project_id) WHERE (is_active = TRUE)
);

-- Indexes
CREATE INDEX idx_unlocks_token ON unlocks(unlock_token);
CREATE INDEX idx_unlocks_project ON unlocks(project_id);
CREATE INDEX idx_unlocks_email ON unlocks(contractor_email);
CREATE INDEX idx_unlocks_payment ON unlocks(payment_id);
```

**Example Row**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "unlock_token": "UNL-4B8T3N",
  
  "created_at": "2024-12-18T14:00:00Z",
  "unlocked_at": "2024-12-18T14:05:00Z",
  "invalidated_at": null,
  
  "payment_status": "completed",
  "payment_id": "cs_test_a1b2c3d4e5f6",
  "amount": 199.00,
  
  "contractor_email": "mike@reno.com",
  "contractor_name": "Mike Smith",
  "contractor_phone": "(555) 987-6543",
  "contractor_company": "Mike's Renovations LLC",
  "contractor_details_saved": true,
  
  "is_active": true
}
```

---

### Table 3: `conversation_states`

**Purpose**: Persist LangGraph conversation state for resume capability

```sql
CREATE TABLE conversation_states (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    state JSONB NOT NULL,            -- Full ProjectState from LangGraph
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for recent updates
CREATE INDEX idx_conversation_updated ON conversation_states(updated_at DESC);
```

**Example Row**:
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": {
    "messages": [...],
    "current_stage": "cost_estimation",
    "project_title": "Kitchen Renovation",
    "project_type": "kitchen",
    "zip_code": "10001",
    "image_analyses": [...],
    "extracted_data": {...},
    "cost_tiers": [...]
  },
  "updated_at": "2024-12-18T13:45:00Z"
}
```

---

### Table 4: `llm_costs` (Optional - Analytics)

**Purpose**: Track AI model usage and costs for analytics

```sql
CREATE TABLE llm_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    session_id VARCHAR(100),
    
    -- Model details
    model VARCHAR(100),              -- e.g., "gemini-2.5-flash"
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost DECIMAL(10,4),              -- Cost in USD
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX idx_llm_costs_project ON llm_costs(project_id);
CREATE INDEX idx_llm_costs_date ON llm_costs(created_at DESC);
CREATE INDEX idx_llm_costs_model ON llm_costs(model);
```

**Example Row**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "sess_abc123",
  "model": "gemini-2.5-flash",
  "input_tokens": 1250,
  "output_tokens": 830,
  "cost": 0.0042,
  "created_at": "2024-12-18T13:30:00Z"
}
```

---

## Key Design Decisions

### ✅ Confirmed Decisions

| Decision | Rationale |
|----------|-----------|
| **No authentication system** | Reduces friction for homeowners, simpler UX |
| **Token-based access** | Both homeowners and contractors use codes, no accounts needed |
| **Universal "My Projects" page** | One page handles both PRJ- and UNL- tokens based on prefix |
| **Force contractor details** | Ensures homeowner can contact back, prevents one-way communication |
| **Two-party completion** | Project closes only when BOTH mark complete, prevents premature closure |
| **Single unlock per project** | Simplifies payments and contractor exclusivity (can add multi-unlock later) |
| **Email-only notifications** | No real-time push/SMS for MVP, keeps infrastructure simple |
| **Save button for state** | Manual save vs auto-save reduces DB writes, user controls when to persist |
| **JSON columns for flexibility** | Estimates, images, extracted data stored as JSONB for schema flexibility |
| **Status-based marketplace** | Only "published" status shown, clean filtering |

---

### 🔄 Future Considerations (Out of Scope for MVP)

| Feature | Why Deferred |
|---------|-------------|
| **Republish after unlock** | Adds complexity; homeowner-contractor ghosting rare in MVP |
| **Multiple unlocks per project** | Requires more complex payment/notification logic |
| **Real-time notifications** | Requires WebSocket infrastructure, email sufficient for MVP |
| **Contractor profiles** | No login system, one-off unlock transactions only |
| **Project reviews/ratings** | Need user accounts first |
| **Admin panel** | Manual DB queries sufficient for MVP monitoring |

---

## Data Access Patterns

### High-Frequency Queries

#### 1. Marketplace Browse
```sql
-- Get all published projects with filters
SELECT id, token, project_type, zip_code, total_price, 
       brief_scope, created_at
FROM projects
WHERE status = 'published'
  AND zip_code = '10001'              -- Optional filter
  AND project_type = 'kitchen'        -- Optional filter
  AND total_price BETWEEN 20000 AND 50000  -- Optional filter
ORDER BY created_at DESC
LIMIT 20;
```

**Frequency**: Very high (every marketplace page load)  
**Optimization**: Composite index on (status, zip_code, project_type, total_price)

---

#### 2. Get Project by Token
```sql
-- Homeowner accessing their project
SELECT * FROM projects
WHERE token = 'PRJ-7X9K2M';
```

**Frequency**: High (every "My Projects" access)  
**Optimization**: Unique index on token column

---

#### 3. Get Unlock by Token
```sql
-- Contractor accessing unlocked project
SELECT u.*, p.*
FROM unlocks u
JOIN projects p ON u.project_id = p.id
WHERE u.unlock_token = 'UNL-4B8T3N'
  AND u.is_active = TRUE;
```

**Frequency**: Medium-high  
**Optimization**: Unique index on unlock_token

---

#### 4. Check if Project Already Unlocked
```sql
-- Before allowing unlock purchase
SELECT id FROM unlocks
WHERE project_id = '550e8400-...'
  AND is_active = TRUE;
```

**Frequency**: Medium (every "Unlock" button click)  
**Optimization**: Index on (project_id, is_active)

---

### Medium-Frequency Queries

#### 5. Update Conversation State
```sql
-- Save chat progress
INSERT INTO conversation_states (project_id, state, updated_at)
VALUES ('550e8400-...', '{"messages": [...]}', NOW())
ON CONFLICT (project_id) 
DO UPDATE SET state = EXCLUDED.state, updated_at = NOW();
```

**Frequency**: Every time user clicks "Save" during chat  
**Optimization**: Primary key on project_id (upsert operation)

---

#### 6. Mark Project Complete
```sql
-- Homeowner marks complete
UPDATE projects
SET homeowner_marked_complete = TRUE,
    updated_at = NOW()
WHERE token = 'PRJ-7X9K2M';

-- Check if both marked complete, then update status
UPDATE projects
SET status = 'completed',
    completed_at = NOW()
WHERE token = 'PRJ-7X9K2M'
  AND homeowner_marked_complete = TRUE
  AND contractor_marked_complete = TRUE;
```

**Frequency**: Low (only at project completion)

---

### Low-Frequency Queries

#### 7. Analytics - Cost by Project
```sql
-- Total LLM costs for a project
SELECT 
    p.token,
    p.project_type,
    SUM(l.cost) as total_cost,
    SUM(l.input_tokens) as total_input_tokens,
    SUM(l.output_tokens) as total_output_tokens
FROM llm_costs l
JOIN projects p ON l.project_id = p.id
WHERE p.id = '550e8400-...'
GROUP BY p.id, p.token, p.project_type;
```

**Frequency**: Very low (admin/analytics only)

---

### Query Performance Summary

| Query Type | Frequency | Index Needed | Estimated QPS |
|------------|-----------|--------------|---------------|
| Marketplace browse | Very High | Composite (status, zip, type, price) | 10-50 |
| Get project by token | High | Unique (token) | 5-20 |
| Get unlock by token | Medium | Unique (unlock_token) | 2-10 |
| Check unlock exists | Medium | (project_id, is_active) | 1-5 |
| Update conversation | Medium | Primary key (project_id) | 1-5 |
| Mark complete | Low | Primary key | <1 |
| Analytics queries | Very Low | Secondary indexes | <0.1 |

**Total estimated peak load**: ~100 QPS for small MVP

---

## Next Steps

### 1. Choose Database Technology

**Options**:
- **PostgreSQL + SQLAlchemy** (recommended for local dev)
- **Firestore** (if client provides access)
- **Hybrid** (PostgreSQL + abstraction layer for future migration)

**Factors to consider**:
- Client requirement (Firestore preference)
- Local development ease (PostgreSQL wins)
- Real-time features (Firestore wins)
- Query complexity (PostgreSQL wins)
- Migration effort (affects timeline)

### 2. Implement Repository Pattern

Create abstract interfaces:
```python
class ProjectRepository(ABC):
    @abstractmethod
    def create_project(self, data: dict) -> Project: ...
    
    @abstractmethod
    def get_by_token(self, token: str) -> Project: ...
    
    @abstractmethod
    def update_status(self, id: UUID, status: str): ...
    
    @abstractmethod
    def get_marketplace_projects(self, filters: dict) -> List[Project]: ...
```

Implementations:
- `PostgreSQLProjectRepository`
- `FirestoreProjectRepository` (future)

### 3. Setup Local Development

- Docker Compose for PostgreSQL
- Alembic for migrations
- pytest fixtures for test data
- Seed scripts for sample projects

### 4. API Endpoints Needed

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/v1/projects/save` | POST | Save project, generate token, send email |
| `GET /api/v1/projects/{token}` | GET | Get project by token (PRJ- or UNL-) |
| `POST /api/v1/projects/{token}/publish` | POST | Publish to marketplace |
| `GET /api/v1/marketplace` | GET | List published projects with filters |
| `POST /api/v1/unlocks/initiate` | POST | Create unlock record, get payment URL |
| `POST /api/v1/webhooks/stripe` | POST | Handle payment confirmation |
| `POST /api/v1/unlocks/{token}/details` | POST | Save contractor details |
| `POST /api/v1/projects/{token}/complete` | POST | Mark project complete |

---

## Questions for Client

Before finalizing implementation:

1. **Firestore Access**: When can you provide Firebase project credentials?
2. **Payment Gateway**: Do you have a Stripe account, or should we use test mode?
3. **Email Service**: Do you have SendGrid/AWS SES, or should we use SMTP?
4. **Domain**: What domain will this be hosted on? (for email links)
5. **Pricing**: Is $199 unlock fee confirmed, or subject to change?
6. **Refunds**: Any refund policy if contractor doesn't reach out?

---

**Document Version**: 1.0  
**Last Updated**: December 18, 2024  
**Status**: Ready for database selection discussion

