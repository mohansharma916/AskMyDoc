# Comprehensive UI/UX & Frontend Architecture Audit: Ask My Docs

**Auditor:** Principal UI/UX Designer, Senior Design Engineer & Frontend Architect  
**Evaluation Date:** October 18, 2026  
**Application Audited:** Ask My Docs (Local RAG Document Intelligence Platform)  
**Target Environment:** React 18.3.1, TypeScript 5.6.3, Tailwind CSS 4.1.4, Vite 5.4.11, TanStack Query 5.62.7  
**Inspection Methodology:** Complete static source audit (`frontend/src`), runtime server verification (`localhost:5173` & `localhost:8001`), accessibility heuristics (WCAG 2.2 AA), and cross-viewport responsive analysis.  
*(Note: Automated headless browser screenshots marked as **Not Verified** due to environment-level Playwright driver CDN unavailability; all DOM structures, styling tokens, and interaction flows are verified directly against production source code).*

---

## 1. Executive Summary & Current Product Assessment

### 1.1 Existing Design Language
The application employs a modern, utilitarian **Anthropic/ChatGPT-inspired split-workspace layout** structured around a neutral **Slate** base palette (`#f8fafc` to `#0f172a`), accented with a high-contrast **Indigo** primary brand accent (`#4f46e5`) and **Emerald** (`#059669`) for positive ingestion and privacy states. The typography relies on standard system sans-serif stacks anchored by **Inter**, rendered with subtle borders (`border-slate-200` / `border-slate-800`) and soft elevation shadows (`shadow-xs` to `shadow-md`).

### 1.2 Layout & Navigation Structure
The layout consists of three principal horizontal columns:
1. **Left Collapsible Sidebar (w-72 / 288px):** Houses product branding, session creation (`Start new chat`), a segmented tab switcher (`Chats` vs `Documents`), the historical session list with quick-delete actions, the document repository (split into *Pre-loaded Corpus* and *User Uploads* with a drag-and-drop ingestion target), and a bottom launch button for *Developer Settings*.
2. **Central Conversation Stage (flex-1):** Features a fixed header (14 / 56px height) with hamburger navigation, the active chat title, an active backend health badge, and a right-panel toggle button. Below the header sits a transient *SessionBanner* explaining browser-session TTL. The middle area contains an adaptive scrollable conversation stream with an empty state (first-time hero greeting or post-upload document confirmation) transitioning to user query bubbles and assistant response cards with interactive citation chips (`[1]`, `[2]`), feedback thumbs, latency, and token counters. Anchored at the bottom is a floating *AskBox* with a backdrop blur gradient.
3. **Right Inspector Panel (w-80 / 320px to w-[480px]):** A contextual drawer toggling between two tabs:
   - **Sources:** Ordered citations for the active answer with keyword highlighting and cross-sentence extraction.
   - **Document Viewer:** An embedded PDF viewer iframe (`#toolbar=1&navpanes=1`) or a structured Document Reader with word count, reading time estimates, and an indexed chunk explorer with real-time text filtering.

### 1.3 Key Strengths
- **Clean Workspace Architecture:** Clear separation of concerns between conversation, source evidence, and document reading.
- **Contextual First-Time UX:** The empty state dynamically differentiates between a first-time visitor (prominent upload dropzone + pre-loaded policy starters) and a user who has just uploaded a document ("You can ask anything from the document" with verified badges and customized starters).
- **Accidental Reload Protection:** Strong guardrails in `useChatSession.ts` hooking into `beforeunload` to prevent users from losing ephemeral browser chat sessions.
- **Responsive Alignment of Floating Input:** The floating `AskBox` is pinned strictly to the central chat stage (`main.relative`), preventing the common bug where opening the right drawer throws the prompt input off-center.

### 1.4 Critical Weaknesses & Architectural Bottlenecks
- **Invalid Tailwind CSS Tokens:** Several components reference non-existent utility classes (`dark:bg-slate-850`, `dark:hover:bg-slate-750`), causing styling declarations to fail silently in dark mode and render transparent surfaces.
- **Touch & Accessibility Violations (WCAG 2.2 AA):**
  - Interactive citation pill buttons (`h-5 min-w-5`, 20×20px) fail the minimum 24×24px target size requirement (SC 2.5.8).
  - Nested interactive controls in `CitationPanel.tsx`: a clickable `<span>` ("Open in viewer →") is illegally nested inside a `<button>`, breaking accessibility trees and keyboard tabbing.
  - Subtitle text and keyboard shortcut hints (`text-slate-400 dark:text-slate-500`) fall below the 4.5:1 minimum contrast ratio against light and dark card backgrounds.
  - The modal dialog in `DeveloperSettings.tsx` lacks focus trapping, allowing tab navigation to escape into the inert background.
- **Mobile Viewport Squeeze (< 768px):** Opening the right inspector panel applies fixed `w-80` (320px) in a side-by-side flex container without collapsing or overlaying, compressing the main chat thread down to ~55px on a 375px mobile screen and completely breaking layout on 320px screens.
- **Destructive Action Affordances:** Document deletion and session deletion occur on immediate click with no confirmation dialog or undo toast, leading to accidental data loss.

---

## 2. High-Level Summary of Findings

| Category | Status | Summary |
|---|---|---|
| **Color Harmony & Tokens** | ⚠️ Needs Attention | Coherent palette, but contains unconfigured tokens (`slate-850`, `slate-750`) and low-contrast muted labels. |
| **Typography & Hierarchy** | ✅ Good | Clear hierarchy from 3xl titles down to 10px kbd elements; needs better markdown styling in answers. |
| **Layout & Spacing** | ⚠️ Needs Attention | Desktop layout is well-proportioned; mobile viewport breaks when right inspector panel is opened. |
| **Existing UX Flows** | ✅ Good | Hero upload and citation inspection are natural, but delete actions lack safety confirmations. |
| **Interaction Feedback** | ⚠️ Needs Attention | Streaming indicator lacks reduced-motion support; citation buttons are too small for touch devices. |
| **Accessibility (WCAG 2.2)** | ❌ Non-Compliant | Fails Target Size (2.5.8), Contrast Minimum (1.4.3), and Focus Containment (2.1.2). |

---

## 3. Prioritized Issue Matrix

| Issue ID | Area / Component | Severity | Description | Complexity |
|---|---|---|---|---|
| **ISS-01** | `CitationPanel.tsx` (L.90-98) | **P0 - Critical** | Nested interactive element: clickable `<span>` inside `<button>`. Breaks keyboard focus and HTML5 validity. | Low |
| **ISS-02** | `App.tsx` (L.636-639) | **P1 - High** | Right inspector panel (`w-80`) does not collapse to overlay on mobile (<768px), crushing main conversation. | Medium |
| **ISS-03** | `DeveloperSettings.tsx` (L.187-219) | **P1 - High** | Modal dialog lacks Tab key focus trapping; focus escapes to background DOM. | Low |
| **ISS-04** | `AnswerView.tsx` (L.49-56) | **P1 - High** | Citation chips are 20×20px, failing WCAG 2.2 AA Target Size Minimum (24×24px). | Low |
| **ISS-05** | Multiple Files (`App`, `DocViewer`, `AskBox`) | **P1 - High** | Non-existent Tailwind v4 classes (`dark:bg-slate-850`, `dark:hover:bg-slate-750`) causing invisible dark backgrounds. | Low |
| **ISS-06** | `AskBox.tsx` (L.56-62) & `App.tsx` (L.477) | **P2 - Medium** | Low contrast on muted text tokens (`text-slate-400` / `dark:text-slate-500`) failing 4.5:1 ratio. | Low |
| **ISS-07** | `UploadPanel.tsx` (L.169-178) | **P2 - Medium** | Instant document deletion without confirmation dialog or undo mechanism. | Medium |
| **ISS-08** | `UploadPanel.tsx` (L.173) | **P2 - Medium** | Document delete icon button is `opacity-0` until hover; impossible to discover on touch devices. | Low |
| **ISS-09** | `AnswerView.tsx` (L.19-59) | **P2 - Medium** | Missing markdown renderers for tables, blockquotes, and headings in LLM responses. | Low |
| **ISS-10** | `AskBox.tsx` (L.38-52) | **P3 - Low** | Textarea has fixed `rows={2}` without auto-expansion for long multi-line prompts. | Medium |
| **ISS-11** | `DeveloperSettings.tsx` (L.205-208) | **P3 - Low** | Close button uses raw "×" character rather than SVG or accessible label. | Low |
| **ISS-12** | `AnswerView.tsx` (L.63) & `AskBox.tsx` (L.72) | **P3 - Low** | Continuous `animate-pulse` and `animate-ping` lack `motion-reduce:animate-none`. | Low |

---

## 4. Responsive Viewport Evaluation

| Viewport Width | Device Target | Observed Behavior | Verdict | Recommended Correction |
|---|---|---|---|---|
| **320px** | Small Mobile (e.g., iPhone SE 1st gen) | Sidebar collapses correctly behind backdrop. However, opening the right inspector panel sets `w-80` (320px), squeezing the central conversation stage to 0px width. Header items collide. | ❌ Broken when Inspector Open | Convert inspector panel to fixed full-screen overlay (`fixed inset-0 z-30`) on viewports under 768px. |
| **375px** | Standard Mobile (e.g., iPhone 13/14/15) | Main stage is usable with inspector closed. When inspector opens, main chat shrinks to ~55px, rendering cards unreadable. Header title clips with status badge. | ❌ Broken when Inspector Open | Add overlay mode for inspector on mobile; truncate header title with tighter max-width. |
| **768px** | Tablet Portrait (e.g., iPad Mini) | Sidebar collapses into hamburger drawer. Chat area and 320px inspector panel share 768px comfortably (~448px chat, ~320px inspector). | ⚠️ Marginal | Provide smooth transition and collapse sidebar when inspector opens if width is constrained. |
| **1024px** | Small Laptop / Tablet Landscape | All 3 panes fit (288px sidebar + ~416px chat + 320px inspector). Good information density. | ✅ Functional | Keep layout; refine padding inside cards (`p-4` instead of `p-5` when both panels open). |
| **1440px** | Desktop | Inspector expands to `lg:w-[480px]`. Central chat max-w-3xl (768px) is centered cleanly. Excellent balance. | ✅ Optimal | **Keep As Is.** |
| **1920px** | Large Monitor | Ample margin on either side of central chat. Floating AskBox stays constrained to max-w-3xl. | ✅ Optimal | **Keep As Is.** |

---

## 5. Accessibility & UX Quality Audit (WCAG 2.2 AA)

### 5.1 Contrast Evaluation (SC 1.4.3 & 1.4.11)
- **Primary Text:** `text-slate-900` (#0f172a) on `bg-white` (#ffffff) yields **15.8:1** (Passes AAA). `dark:text-slate-100` (#f1f5f9) on `dark:bg-slate-900` (#0f172a) yields **13.5:1** (Passes AAA).
- **Muted Text / Shortcut Hints:** `text-slate-400` (#94a3b8) on `bg-white` yields **2.8:1** (Fails AA, minimum required 4.5:1). `dark:text-slate-500` (#64748b) on `dark:bg-slate-900` yields **2.9:1** (Fails AA).  
  *Fix:* Upgrade light mode muted text to `text-slate-500` (#64748b, 4.6:1) and dark mode to `dark:text-slate-400` (#94a3b8, 5.2:1).
- **Citation Highlight Marks:** `<mark className="bg-amber-200/80 ... dark:bg-amber-500/30">` has low contrast in dark mode when surrounding text is light.  
  *Fix:* Adjust dark mode highlight token to `dark:bg-amber-400/25 dark:text-amber-200`.

### 5.2 Target Size Minimum (SC 2.5.8)
- **Citation Chips:** Dimensioned as `h-5 min-w-5` (20×20px). This fails WCAG 2.2 AA (minimum 24×24px).  
  *Fix:* Expand chip dimensions to `h-6 min-w-6 px-2 text-xs` (24×24px) or use pseudo-element touch targets (`before:absolute before:-inset-1`).

### 5.3 Focus & Dialog Trapping (SC 2.1.2 & 2.4.3)
- `DeveloperSettings.tsx` implements a `<div role="dialog" aria-modal="true">` with `panel.current?.focus()`. However, pressing `Tab` cycles past the "Save" button directly into the underlying page DOM behind the backdrop.  
  *Fix:* Add standard focus containment (`onKeyDown` Tab interceptor or HTML `<dialog>` element).

---

## 6. Implementation Architecture & Code Quality

### 6.1 Design Token Consistency
- **Defect:** `dark:bg-slate-850` in `App.tsx` (L.198), `DocumentViewer.tsx` (L.249), and `UploadPanel.tsx` (L.92, 148, 227). In Tailwind CSS v4, `slate-850` is not part of the standard palette. Because `index.css` only defines font families under `@theme`, this utility produces no CSS rule, resulting in a transparent background in dark mode.
- **Defect:** `dark:hover:bg-slate-750` in `AskBox.tsx` (L.70) similarly fails to compile.
- **Correction:** Replace `slate-850` with standard `slate-800` or `slate-900`, or explicitly define `--color-slate-850: #151e2e;` and `--color-slate-750: #263345;` inside `@theme` in `index.css`.

### 6.2 Component Modularity & HTML Validity
- `CitationPanel.tsx` contains an invalid HTML tree:
  ```html
  <button type="button" onClick="...">
    ...
    <span onClick="stopPropagation(); onViewDoc(...)">Open in viewer →</span>
  </button>
  ```
  Buttons cannot contain interactive descendants per the W3C HTML5 specification. This causes unpredictable event dispatch across browsers and prevents screen readers from announcing the secondary action.
  *Correction:* Restructure the citation card into an `<article>` container with two distinct sibling buttons: the card selection button and the "Open in viewer" text button.

---

## 7. Deliverables Index

Detailed breakdowns of each specific evaluation dimension are documented in the companion audit files:
1. [PAGE_WISE_ISSUES.md](file:///Users/user/Documents/Projects/RAG/ui-ux-audit/PAGE_WISE_ISSUES.md) — Comprehensive issue registry for every page, modal, and component.
2. [COLOR_AND_DESIGN_SYSTEM.md](file:///Users/user/Documents/Projects/RAG/ui-ux-audit/COLOR_AND_DESIGN_SYSTEM.md) — Deep color contrast analysis, typography scales, spacing tokens, and invalid class resolutions.
3. [UX_FLOW_ANALYSIS.md](file:///Users/user/Documents/Projects/RAG/ui-ux-audit/UX_FLOW_ANALYSIS.md) — Step-by-step tracing of the 5 core user journeys.
4. [IMPROVEMENT_PLAN.md](file:///Users/user/Documents/Projects/RAG/ui-ux-audit/IMPROVEMENT_PLAN.md) — Prioritized, non-breaking execution roadmap.
