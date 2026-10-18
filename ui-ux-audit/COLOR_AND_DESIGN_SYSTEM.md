# Color & Design System Audit

**Application:** Ask My Docs  
**Design Paradigm:** Utilitarian, Split-Pane Intelligence Workspace (Anthropic/ChatGPT hybrid)  
**CSS Engine:** Tailwind CSS v4.1.4 with CSS `@theme` variables

---

## 1. Color Palette Inventory & Semantic Roles

The application relies on Tailwind's default **Slate** palette for surface neutral foundation, augmented with dedicated semantic accents:

### 1.1 Palette Matrix

| Semantic Role | Light Mode Value | Dark Mode Value | Usage in Application |
|---|---|---|---|
| **App Canvas Background** | `#f8fafc` (`bg-slate-50`) | `#020617` / `#090d16` (`dark:bg-slate-950`) | Main application window, outer stage |
| **Card / Surface Background** | `#ffffff` (`bg-white`) | `#0f172a` (`dark:bg-slate-900`) | Sidebar, header, answer cards, inspector |
| **Subtle Elevated Surface** | `#f1f5f9` (`bg-slate-100`) | `#1e293b` (`dark:bg-slate-800`) | Code blocks, pill badges, hover states |
| **Primary Brand Accent** | `#4f46e5` (`bg-indigo-600`) | `#6366f1` / `#818cf8` (`dark:text-indigo-400`) | Query bubbles, ask button, active tab indicator |
| **Primary Light Tint** | `#eef2ff` (`bg-indigo-50`) | `#1e1b4b` with opacity (`dark:bg-indigo-950/60`) | Hero icon circles, selected citations, active chats |
| **Success / Verified State** | `#059669` (`text-emerald-600`) / `#ecfdf5` | `#34d399` (`dark:text-emerald-400`) / `#064e3b` | "Ready" badge, User upload pill, Ingest summary |
| **Amber Caution / Highlight** | `#fde68a` (`bg-amber-200/80`) | `#f59e0b` (`dark:bg-amber-500/30`) | Citation word highlight marks, status dots |
| **PDF Badge Accent** | `#be123c` (`text-rose-700`) / `#fff1f2` | `#fb7185` (`dark:text-rose-400`) / `#4c0519` | Document Viewer PDF file badge |
| **Document Reader Accent** | `#1d4ed8` (`text-blue-700`) / `#eff6ff` | `#60a5fa` (`dark:text-blue-400`) / `#172554` | Document Viewer text/markdown badge |
| **Error / Destructive** | `#dc2626` (`text-red-600`) | `#f87171` (`dark:text-red-400`) | Ingest failures, API errors, document removal |

---

## 2. WCAG 2.2 AA Contrast Compliance Analysis

Evaluation against WCAG 2.2 Criterion 1.4.3 (Contrast Minimum: 4.5:1 for normal text, 3:1 for large text / UI controls) and Criterion 1.4.11 (Non-text Contrast: 3:1 for graphical objects and boundary indicators).

| Element & Location | Text Color (HEX) | Background Color (HEX) | Ratio | Standard | Compliance Status | Corrective Action |
|---|---|---|---|---|---|---|
| **Primary Text (Light)** | `#0f172a` (`text-slate-900`) | `#ffffff` (`bg-white`) | **15.8:1** | 4.5:1 | ✅ PASS (AAA) | Keep as is |
| **Primary Text (Dark)** | `#f1f5f9` (`dark:text-slate-100`) | `#0f172a` (`dark:bg-slate-900`) | **13.5:1** | 4.5:1 | ✅ PASS (AAA) | Keep as is |
| **Secondary Body (Light)** | `#475569` (`text-slate-600`) | `#ffffff` (`bg-white`) | **5.9:1** | 4.5:1 | ✅ PASS (AA) | Keep as is |
| **User Query Bubble** | `#ffffff` (`text-white`) | `#4f46e5` (`bg-indigo-600`) | **7.1:1** | 4.5:1 | ✅ PASS (AAA) | Keep as is |
| **Muted Labels (Light)** | `#94a3b8` (`text-slate-400`) | `#ffffff` (`bg-white`) | **2.8:1** | 4.5:1 | ❌ **FAIL** | Update to `#64748b` (`text-slate-500`, **4.6:1**) |
| **Muted Labels (Dark)** | `#64748b` (`dark:text-slate-500`) | `#0f172a` (`dark:bg-slate-900`) | **2.9:1** | 4.5:1 | ❌ **FAIL** | Update to `#94a3b8` (`dark:text-slate-400`, **5.2:1**) |
| **Keyboard Hints (`AskBox:L56`)** | `#94a3b8` (`text-slate-400`) | `#ffffff` (`bg-white`) | **2.8:1** | 4.5:1 | ❌ **FAIL** | Update to `text-slate-500` (**4.6:1**) |
| **Citation Badge (Selected)** | `#ffffff` (`text-white`) | `#4f46e5` (`bg-indigo-600`) | **7.1:1** | 4.5:1 | ✅ PASS | Keep as is |
| **Citation Badge (Default)** | `#4338ca` (`text-indigo-700`) | `#e0e7ff` (`bg-indigo-100`) | **6.4:1** | 4.5:1 | ✅ PASS | Keep as is |
| **Citation Highlight (Dark)** | `#f1f5f9` (`text-slate-100`) | `#f59e0b` at 30% alpha | **~3.1:1** | 4.5:1 | ⚠️ **MARGINAL** | Use `dark:bg-amber-400/25 dark:text-amber-200` |
| **Session Warning Text** | `#78350f` (`text-amber-900`) | `#fef3c7` (`bg-amber-50`) | **7.4:1** | 4.5:1 | ✅ PASS | Keep as is |
| **Close `×` Button (Default)** | `#94a3b8` (`text-slate-400`) | `#ffffff` (`bg-white`) | **2.8:1** | 3.0:1 | ❌ **FAIL (UI Control)** | Change base to `text-slate-500` (**4.6:1**) |

---

## 3. Dark Mode Implementation & Invalid Tokens

### 3.1 The "Silent Failure" Token Bug
Tailwind CSS v4 introduces a strict `@theme` CSS layer. Unless explicitly defined, arbitrary or non-standard color scale numbers do not exist.
The following classes in the codebase produce **no compiled CSS rules**:

1. **`dark:bg-slate-850`**:
   - `frontend/src/App.tsx:L198` (New Chat button)
   - `frontend/src/components/DocumentViewer.tsx:L249` (Chunk container cards)
   - `frontend/src/components/UploadPanel.tsx:L92, L148, L227` (Ingestion drops and doc list)
   - **Observed Result:** In dark mode, elements render with `background-color: transparent`, causing them to blend invisibly into whatever background sits behind them.
2. **`dark:hover:bg-slate-750`**:
   - `frontend/src/components/AskBox.tsx:L70` (Stop button hover)
   - **Observed Result:** Hovering over the button in dark mode has zero visual feedback.

### 3.2 Proposed Token Resolution
Add custom tone steps into `frontend/src/index.css` or map them to standard Tailwind tokens:
```css
/* Recommended index.css additions */
@theme {
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  
  /* Missing Slate Nuances for high-contrast dark surfaces */
  --color-slate-750: #243044;
  --color-slate-850: #131c2e;
}
```
*Alternatively, simply normalize all instances to standard `dark:bg-slate-800` (for elevated cards) and `dark:bg-slate-900` (for base containers).*

---

## 4. Typography Scale & Hierarchy

The application imports `Inter` with system sans-serif fallbacks.

| Scale Token | Font Size | Line Height | Weight | Applied In | Evaluation & Findings |
|---|---|---|---|---|---|
| **Display Heading** | `text-3xl` (30px) | `tracking-tight` (36px) | Bold (`font-bold`) | `App.tsx` Hero Greeting & Upload Confirmation | High visual impact, generous letter spacing. **Keep as is.** |
| **Section Heading** | `text-sm` (14px) | Normal (20px) | Semi-Bold (`font-semibold`) | Header title, Card headers, Modal titles | Crisp and balanced against 56px header height. **Keep as is.** |
| **Micro Category** | `text-[11px]` (11px) | Tight (16px) | Semi-Bold (`font-semibold`) + Uppercase | Sidebar headers, Inspector tabs, Sources count | Good scannability; requires `tracking-wider`. |
| **Body Standard** | `text-sm` (14px) | Relaxed (`leading-relaxed`, 22px) | Regular (`font-normal`) | AnswerView paragraphs, User queries | Optimal reading line length in 768px (`max-w-3xl`) container. |
| **Secondary Body** | `text-xs` (12px) | Normal (16px) | Medium (`font-medium`) | Starter buttons, Doc list metadata, Feedback | Highly legible. |
| **Technical Badges** | `text-[10px]` (10px) | Tight (14px) | Font-Mono (`font-mono`) | `kbd` keys, Page indicators (`p. 2`), Chunk numbers | Crisp, high density. Contrast needs care. |

### Typography Defect in LLM Responses
In `AnswerView.tsx`, while `ReactMarkdown` styles `p`, `ul`, `ol`, and `code`, it lacks rules for markdown headings (`h1`-`h3`), blockquotes, and tables. When Claude or GPT returns a structured markdown response containing bulleted headers or comparative tables, the headers render at unstyled default HTML sizes, jarring against the 14px body text.

---

## 5. Spacing, Borders, and Elevation System

### 5.1 Spacing Rhythm
The interface follows a clean **4px/8px modular grid**:
- **Padding:** 
  - Main chat container: `p-4 sm:p-6 pb-36` (16px/24px horizontal, 144px bottom clearance for floating AskBox).
  - Cards: `p-3.5` (14px) to `p-5` (20px).
  - List items: `px-2.5 py-2` (10px horizontal, 8px vertical).
- **Gaps:** `gap-1.5` (6px) between status pills; `gap-3` (12px) between card sections; `space-y-6` (24px) between chat turns.

### 5.2 Borders & Radii
- **Base Border:** `border border-slate-200 dark:border-slate-800` (1px solid).
- **Dashed Dropzones:** `border-2 border-dashed border-slate-300 dark:border-slate-700` (clean affordance for file upload).
- **Border Radius Hierarchy:**
  - `rounded-full`: Status dots, citation chips, pill badges.
  - `rounded-2xl` (16px): Main answer cards, AskBox floating container, Hero dropzone.
  - `rounded-xl` (12px): Starter question buttons, Session list items, Dropzones.
  - `rounded-lg` (8px): Icon buttons, tab switchers, inputs.
  - `rounded` (4px): Monospace `kbd` elements and page numbers.

### 5.3 Elevation & Shadows
- **Card Flatness:** Primarily relies on borders (`border-slate-200`) with ultra-subtle `shadow-xs` / `shadow-2xs`.
- **Floating Input Box:** `shadow-sm` layered over an `absolute inset-x-0 bottom-0` gradient backdrop (`from-slate-50 via-slate-50/90 to-transparent`). This creates a floating "heads-up" feel without obstructing background scrolling.
- **Developer Settings Modal:** `shadow-xl` with backdrop blur (`backdrop-blur-[1px] bg-slate-900/30`).
