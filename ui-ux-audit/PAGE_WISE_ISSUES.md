# Page-by-Page & Component UI/UX Audit Issues

This document itemizes every issue discovered across the actual, implemented components of **Ask My Docs**. All issues cite exact file paths, code references, severity levels, UX impacts, and specific proposed fixes.

---

## 1. Top Header & Session Banner

**Files:** [App.tsx:L315-L368](file:///Users/user/Documents/Projects/RAG/frontend/src/App.tsx#L315-L368), [SessionBanner.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/SessionBanner.tsx)

| Area / Component | Current Issue | UX Impact | Recommended Fix | Severity |
|---|---|---|---|---|
| **Header Title & Status** (`App.tsx:L327-L344`) | On mobile viewports (<375px), the chat title (`max-w-[200px]`), system status, and panel toggle button crowd the 56px header, causing awkward truncation or overflow. | Critical controls feel cramped; status details can wrap unexpectedly on narrow screens. | Hide the status badge text on viewports `< 640px` (preserving only the live indicator dot), and set `max-w-[140px]` on mobile for the chat title. | Medium |
| **Inspector Toggle Button** (`App.tsx:L351-L366`) | Button label toggles between `"Document Viewer"` and `"Sources"` based on the internal panel tab, but clicking it opens or closes the panel without clearly indicating current open/closed status. | Users cannot tell whether clicking will open the drawer or change views if the drawer is already open. | Add `aria-expanded={rightPanelOpen}` and display a clear toggle state or icon (e.g., panel-right icon with active highlight). | Medium |
| **Session Banner Warning** (`SessionBanner.tsx:L28-L34`) | When session timeout warning triggers (`remainingMs <= 60_000`), text prompts: *"Move the mouse or press a key to stay."* However, on mobile/touch devices there is no mouse movement. | Touch users who read the screen without scrolling may lose their session unexpectedly because touch events aren't mentioned. | Update copy to *"Tap, scroll, or press any key to extend session"* and verify touch listener handles session keep-alive. | Low |
| **End Session Affordance** (`SessionBanner.tsx:L50-L56`) | *"End session now"* link has low contrast in dark mode against `dark:bg-slate-900/60` and triggers immediate termination without confirmation. | Accidental click immediately destroys all user uploads and session state. | Add confirmation modal or alert before invoking `endSession()`. | High |

---

## 2. Left Collapsible Sidebar

**Files:** [App.tsx:L160-L310](file:///Users/user/Documents/Projects/RAG/frontend/src/App.tsx#L160-L310), [UploadPanel.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/UploadPanel.tsx)

| Area / Component | Current Issue | UX Impact | Recommended Fix | Severity |
|---|---|---|---|---|
| **New Chat Button** (`App.tsx:L198`) | Uses `dark:bg-slate-850`, which is not a defined Tailwind v4 token. | Renders with a transparent background in dark mode, losing visual depth against the sidebar container. | Replace `dark:bg-slate-850` with `dark:bg-slate-800` or `dark:bg-slate-900`. | High |
| **Chat History Delete Action** (`App.tsx:L277-L287`) | The `×` delete button is `opacity-0` until hovered (`group-hover:opacity-100`). On touch devices, there is no hover capability. | Touch users cannot discover or easily tap the delete button for chat sessions. | Display the delete button with semi-transparent default opacity (`opacity-60 hover:opacity-100` on mobile, or media query `@media (hover: hover)`). | Medium |
| **Chat Session Deletion Safety** (`App.tsx:L277-L287`) | Tapping `×` immediately deletes the chat session and its entire turn history with zero confirmation. | Severe risk of accidental data loss when aiming for the chat title on mobile. | Require confirmation modal, double-tap confirmation ("Delete?"), or provide an undo toast notification. | High |
| **Document List Selection** (`UploadPanel.tsx:L147-L180`) | The document `<li>` item is clickable via `onClick`, but lacks `role="button"` and `tabIndex={0}`. | Keyboard-only users cannot navigate down the document list using Tab or arrow keys to open a document in the viewer. | Add `tabIndex={0}`, `role="button"`, and `onKeyDown={(e) => e.key === "Enter" && onSelectDocument(d.doc_id)}`. | High |
| **Document Delete Button** (`UploadPanel.tsx:L166-L178`) | Hidden with `opacity-0 group-hover:opacity-100`. Clicking triggers immediate deletion via `remove.mutate(d.doc_id)`. | Invisible on touch screens; instant deletion removes document and all vector embeddings with no recovery option. | Remove `opacity-0` on touchscreens; introduce confirmation dialog before document deletion. | High |
| **Upload Dropzone Empty State** (`UploadPanel.tsx:L73-L114`) | Accepts multiple files, but provides no file size limit indicator or explicit visual rejection when an unsupported file type is dragged over. | Users dragging large or unsupported files receive no immediate affordance until backend ingestion fails. | Add visual indicator of allowed file types and size limits (e.g., *Max 25MB per file*). | Low |

---

## 3. Central Conversation Stage & Empty States

**Files:** [App.tsx:L371-L547](file:///Users/user/Documents/Projects/RAG/frontend/src/App.tsx#L371-L547)

| Area / Component | Current Issue | UX Impact | Recommended Fix | Severity |
|---|---|---|---|---|
| **First-Time Hero Upload Box** (`App.tsx:L404-L469`) | The large dashed dropzone is a `<div>` with `role="button" tabIndex={0}`. While accessible, dragging over the border triggers `border-indigo-500`, but dragging an invalid file displays no error. | Users dragging images or unsupported archives don't get immediate drag-over validation feedback. | Inspect `e.dataTransfer.items` on dragover and display warning state if file extension is unsupported. | Low |
| **Starter Prompts Separation Line** (`App.tsx:L477`) | Text *"Or ask about pre-loaded policies"* uses `text-slate-400 dark:bg-slate-950` with contrast ratio of only 2.8:1 against white/slate-50 background. | Muted label fails WCAG 2.2 AA text contrast requirement. | Update to `text-slate-500 dark:text-slate-400` to achieve > 4.5:1 contrast. | Medium |
| **Post-Upload Document Badge** (`App.tsx:L514-L523`) | Displays `justUploadedDocName` with `max-w-xs truncate`. If the filename is very long, it truncates without a tooltip or full title on hover. | Users cannot verify which specific file version was uploaded if the suffix is cut off. | Add `title={justUploadedDocName}` attribute to the container for native browser tooltip on hover. | Low |
| **Starter Buttons Touch Targets** (`App.tsx:L483-L494`) | In mobile single-column view, cards have `p-3 text-xs`. Spacing between cards is `gap-2` (8px). | Fast tapping can cause accidental selection of the adjacent starter question on small touchscreens. | Increase card spacing to `gap-3` and increase vertical padding to `p-3.5` on mobile. | Low |

---

## 4. Conversation Stream & Response Cards

**Files:** [App.tsx:L549-L622](file:///Users/user/Documents/Projects/RAG/frontend/src/App.tsx#L549-L622), [AnswerView.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/AnswerView.tsx), [Feedback.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/Feedback.tsx), [NotFoundState.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/NotFoundState.tsx)

| Area / Component | Current Issue | UX Impact | Recommended Fix | Severity |
|---|---|---|---|---|
| **Citation Chip Button Size** (`AnswerView.tsx:L49-L56`) | Citation buttons in markdown stream are sized as `h-5 min-w-5` (20×20px). | Fails WCAG 2.2 SC 2.5.8 (Target Size Minimum, 24×24px). Frequent mis-taps on mobile devices when citations are clustered (e.g. `[1][2]`). | Increase button size to `h-6 min-w-6 px-1.5 text-xs` (24×24px) with `mx-0.5` spacing. | High |
| **External Markdown Links** (`AnswerView.tsx:L35-L38`) | Standard hyperlinks open with `target="_blank"`, but have no visual external-link icon or `aria-label` stating they open in a new window. | Screen reader users and sighted users are unexpectedly redirected away without warning. | Append an external link icon SVG and `aria-label="... (opens in new tab)"`. | Medium |
| **Markdown Element Coverage** (`AnswerView.tsx:L19-L59`) | Custom markdown components only define `p`, `ul`, `ol`, `li`, `strong`, `code`, and `a`. Headers (`h1-h4`), blockquotes, tables, and horizontal rules are not customized. | If the LLM generates a table or header in a policy answer, it renders with unstyled, overflowing HTML elements. | Add Tailwind typography styles or explicit component mappings for `table`, `thead`, `th`, `td`, `blockquote`, and `h1-h3`. | Medium |
| **Streaming Animation & Reduced Motion** (`AnswerView.tsx:L63`, `App.tsx:L574`) | The streaming cursor and waiting dot use `animate-pulse` and `animate-ping` unconditionally. | Users with vestibular disorders who configure `prefers-reduced-motion` still see flashing elements. | Add `motion-reduce:animate-none` to all pulsing and pinging indicators. | Low |
| **Turn Card Metadata Alignment** (`App.tsx:L604-L617`) | Feedback buttons ("Was this helpful?") and latency/token counters wrap onto multiple lines inconsistently on small widths. | Creates uneven vertical card heights and visually cluttered card footers. | Use flex layout with `items-center justify-between gap-2` and truncate token counts on narrow viewports. | Low |

---

## 5. Floating Bottom Input Box (AskBox)

**Files:** [AskBox.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/AskBox.tsx), [App.tsx:L626-L632](file:///Users/user/Documents/Projects/RAG/frontend/src/App.tsx#L626-L632)

| Area / Component | Current Issue | UX Impact | Recommended Fix | Severity |
|---|---|---|---|---|
| **Stop Button Dark State** (`AskBox.tsx:L70`) | Uses `dark:hover:bg-slate-750`, an invalid Tailwind class. | Hovering over the Stop button in dark mode does not change the background color. | Replace with `dark:hover:bg-slate-700`. | High |
| **Keyboard Hint Text Contrast** (`AskBox.tsx:L56-L62`) | `text-slate-400 dark:text-slate-500` for *"Press Enter ↵ to send"* has contrast of 2.8:1 on light mode and 2.9:1 in dark mode. | Difficult to read for low-vision users; fails WCAG 2.2 AA. | Change to `text-slate-500 dark:text-slate-400`. | Medium |
| **Textarea Auto-Expansion** (`AskBox.tsx:L38-L52`) | Textarea has hardcoded `rows={2}`. When pasting or typing a longer question, a native vertical scrollbar appears inside the cramped 2-line box. | Difficult to review and edit complex queries before sending. | Implement auto-sizing textarea (e.g. adjust `element.style.height = element.scrollHeight + 'px'` up to a `max-h-36` limit). | Medium |
| **Aggressive Auto-Focus Shift** (`AskBox.tsx:L23-L27`) | `useEffect` refocuses the textarea automatically whenever `streaming` changes from `true` to `false`. | If the user is selecting text in an answer or clicking a citation while an answer finishes streaming, focus is abruptly stolen back to the input box. | Only auto-focus on initial mount or when the user explicitly triggers an action, not automatically after background stream completion. | Medium |
| **Bottom Padding Clearance** (`App.tsx:L377`) | The scrollable conversation list has `pb-36` (144px). If the prompt input grows or the user expands the AskBox, the last message card can be obscured behind the floating gradient overlay. | Users cannot see the bottom-most citations or feedback buttons without awkward scrolling. | Dynamically measure AskBox height or set safe clearance `pb-44` (176px). | Low |

---

## 6. Right Inspector Panel & Document Viewer

**Files:** [App.tsx:L634-L705](file:///Users/user/Documents/Projects/RAG/frontend/src/App.tsx#L634-L705), [CitationPanel.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/CitationPanel.tsx), [DocumentViewer.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/DocumentViewer.tsx)

| Area / Component | Current Issue | UX Impact | Recommended Fix | Severity |
|---|---|---|---|---|
| **Mobile Layout Destruction** (`App.tsx:L636-L639`) | Right panel uses fixed `w-80` (320px) in a flex row alongside the chat stage. On a 320px or 375px mobile screen, opening the panel crushes the chat area down to 0-55px. | Complete layout breakage on mobile devices whenever a citation or document is opened. | Make the inspector panel a fixed full-width overlay on mobile: `fixed inset-0 z-30 md:static md:w-80 lg:w-[480px]`. | **P0 - Critical** |
| **Nested Interactive Elements** (`CitationPanel.tsx:L90-L98`) | A clickable `<span>` ("Open in viewer →") with `onClick` is nested inside an outer `<button type="button" onClick="...">`. | Violates W3C HTML5 specification. Screen readers cannot expose the inner action; keyboard users cannot Tab to "Open in viewer". | Change the outer card to a non-button `<article>` and provide two sibling buttons: one to select/highlight citation and one to open document. | **P0 - Critical** |
| **Dark Mode Utility in Chunks** (`DocumentViewer.tsx:L249`) | Chunk cards use `dark:bg-slate-850`, which fails to compile in Tailwind v4. | Dark mode renders transparent or uneven chunk background surfaces. | Replace with `dark:bg-slate-800` or define `slate-850` in `@theme`. | High |
| **PDF Mobile Iframe Usability** (`DocumentViewer.tsx:L188-L193`) | Uses standard `<iframe>` for PDF rendering. On mobile Safari and Android Chrome, embedded iframes do not support natural pinch-to-zoom or multi-page navigation. | Mobile users cannot read or navigate multi-page PDF policies inside the embedded viewer. | On small viewports, display a prominent "Open PDF in Native Viewer" banner and default to the "Chunks" extracted text view. | High |
| **Citation Keyword Contrast** (`CitationPanel.tsx:L28`) | Shared terms highlighted with `<mark className="bg-amber-200/80 ... dark:bg-amber-500/30">`. In dark mode, light text over `amber-500/30` has low contrast. | Strains readability when scanning highlighted evidence in dark mode. | Update dark mode class to `dark:bg-amber-400/25 dark:text-amber-200`. | Medium |

---

## 7. Developer Settings Modal

**Files:** [DeveloperSettings.tsx](file:///Users/user/Documents/Projects/RAG/frontend/src/components/DeveloperSettings.tsx)

| Area / Component | Current Issue | UX Impact | Recommended Fix | Severity |
|---|---|---|---|---|
| **Missing Focus Trap** (`DeveloperSettings.tsx:L187-L219`) | While the dialog has `role="dialog"` and handles `Escape`, pressing Tab allows keyboard focus to cycle out of the dialog into background page elements. | Violates WCAG 2.2 SC 2.1.2 (No Keyboard Trap) and SC 2.4.3 (Focus Order). Disorienting for keyboard and screen-reader users. | Add keyboard Tab trap loop within dialog boundaries or use native HTML `<dialog>` with `showModal()`. | High |
| **Raw Symbol Close Button** (`DeveloperSettings.tsx:L205-L208`) | Uses raw character `×` inside `<button>`. | Screen readers announce "multiplication sign" or "times" instead of "Close". | Add `aria-label="Close developer settings"` and use an accessible SVG icon `<path d="..." />`. | Low |
| **API Key Security Feedback** (`DeveloperSettings.tsx:L112-L127`) | Input is `type="password"` with placeholder showing whether key is set, but no "Show/Hide" toggle or copy prevention. | Users pasting keys cannot visually confirm whether trailing spaces or mistakes exist. | Add a toggleable eye icon to briefly reveal the key during entry. | Low |
| **Memory-Only Ephemeral Warning** (`DeveloperSettings.tsx:L166`) | Notice *"Changes live in server memory and reset when the API restarts"* is rendered in `text-[11px] text-slate-400` at the very bottom. | Users miss this warning and are confused when settings revert after container restart. | Position as an informative callout box or subtle banner near the save button. | Low |
