# UX Flow Analysis & User Journey Evaluation

This document traces and evaluates the actual user flows implemented in **Ask My Docs**. Each evaluation follows the required pattern:
**Current Flow → Observed Problem → Recommended Improvement → Expected Benefit** (or explicitly **Keep As Is** where the flow is already intuitive and robust).

---

## Flow 1: First-Time User Onboarding & Document Upload

### 1. Context & User Intent
- **Starting Point:** User visits the web application with an empty session storage and no previous user-uploaded documents.
- **User Goal:** Understand what the platform does, upload their own document (e.g., an internal PDF or company handbook), and verify that it has been indexed.

### 2. Step-by-Step Sequence
1. User lands on central stage showing dynamic greeting (*"Good morning" / "Good afternoon"*) and subtitle *"Ask any question about your document"*.
2. A prominent dashed upload container invites the user: *"Upload a document to get started · Drag & drop or click to browse · PDF, Markdown, HTML or TXT"*.
3. User drags a file or clicks the container to select a file via the native file picker.
4. An immediate loading spinner displays: *"Indexing and processing your document…"*.
5. Ingest job polls backend every 1,000ms via TanStack Query.
6. Upon completion, the screen transitions automatically to the post-upload view:
   - Success icon appears with *"You can ask anything from the document"*.
   - A verified badge displays the filename with a green checkmark and *"Ready"*.
   - The right inspector panel automatically swings open to the *"Document Viewer"* tab, rendering the uploaded PDF or extracted chunks.
   - Four customized starter prompt buttons appear (*"Document summary"*, *"Key findings & requirements"*, *"Important dates & deadlines"*, *"Specific guidelines"*).

### 3. Evaluation
- **Current Flow → Observed Problem:** The transition is smooth and celebratory, but if the user uploads a multi-page PDF, the right panel opens in iframe mode (`DocumentViewer.tsx:L188`). On mobile viewports (<768px), opening this panel shrinks the central conversation stage down to ~55px, crushing the "You can ask anything" greeting and starter buttons.
- **Recommended Improvement:** Keep the desktop transition exactly as is. On mobile devices (<768px), when a document finishes uploading, display a dismissible bottom confirmation toast with an "Inspect Document" action instead of forcibly opening the right drawer and compressing the stage.
- **Expected Benefit:** Mobile users retain a visible, readable chat stage with starter prompts, while desktop users continue to enjoy the immediate split-pane preview.

---

## Flow 2: Question Asking, Streaming, and Citation Discovery

### 1. Context & User Intent
- **Starting Point:** User has either indexed documents or wishes to query the pre-loaded policy corpus.
- **User Goal:** Ask a specific question, observe immediate streaming progress, verify facts against source citations, and check source excerpts.

### 2. Step-by-Step Sequence
1. User types query into floating `AskBox` textarea (or clicks one of the starter prompt cards).
2. User presses `Enter` (or clicks *"Ask"* button).
3. The query appears instantly in an indigo right-aligned chat bubble.
4. Assistant card appears below with an animated indicator: *"Searching and synthesizing verified sources…"*.
5. SSE streaming begins via `useAskStream.ts`:
   - Text streams character-by-character with an animated cursor.
   - If initial citation verification fails, an informative badge displays: *"Re-checking citations and regenerating…"*.
6. Answer stream completes:
   - Text displays inline numbered citation pills (e.g. `[1]`, `[2]`).
   - The right inspector panel automatically activates the *"Sources"* tab, displaying the supporting excerpts.
   - Key shared terms between the cited sentence and the source excerpt are highlighted with amber `<mark>` tags.
   - User clicks citation chip `[1]` in the answer: the corresponding source card in the right drawer highlights with `border-indigo-500 bg-indigo-50`.
7. Card footer shows feedback thumbs (*"Was this helpful?"*), latency (*"1.2 s"*), and token count (*"· 412 tokens"*).

### 3. Evaluation
- **Evaluation:** **Keep As Is** for the core streaming and citation synchronization mechanism. The auto-opening of the Sources drawer and bi-directional citation highlighting is an industry-leading pattern.
- **Current Flow → Observed Problem 1:** When the stream completes, `AskBox.tsx` invokes `textareaRef.current.focus()`. If the user was already reading an excerpt or attempting to highlight text in the assistant answer, their focus is yanked back to the input box.
  - **Recommended Improvement:** Remove the automatic focus-stealing `useEffect` on stream completion. Focus the input on initial page load, but leave user focus undisturbed when reading answers.
  - **Expected Benefit:** Seamless reading experience with no unexpected cursor jumps.
- **Current Flow → Observed Problem 2:** In `CitationPanel.tsx:L90-L98`, the *"Open in viewer →"* link inside the source card is a `<span>` with `onClick` nested inside the outer `<button>` that selects the citation. Clicking this triggers `stopPropagation()`, which works on mouse clicks but is inaccessible via keyboard navigation (cannot tab to it).
  - **Recommended Improvement:** Separate the citation card into an article with two independent sibling buttons: one to highlight the excerpt, and one to open the full document in the viewer tab.
  - **Expected Benefit:** Full keyboard accessibility (Tab, Enter) and standards-compliant HTML.

---

## Flow 3: Document Inspection (PDF vs Reader vs Chunks)

### 1. Context & User Intent
- **Starting Point:** User is either reviewing sources in the inspector panel or browsing the document list in the left sidebar.
- **User Goal:** Read the original document, view raw PDF pages, or search indexed text chunks.

### 2. Step-by-Step Sequence
1. User clicks a document title in the sidebar (under *"User Uploads"* or *"Pre-loaded Corpus"*), or clicks *"Open in viewer →"* from a citation card.
2. The right drawer switches to the *"Document Viewer"* tab.
3. Top bar displays document type badge (*"PDF"* in rose, or *"Document"* in blue), source type (*"Corpus"* vs *"User Upload"*), chunk count, and title.
4. If the document is a PDF:
   - Sub-header provides a toggle: `[PDF Viewer]` vs `[Chunks (N)]`.
   - Reader mode displays native browser PDF viewer with toolbar and page navigation inside an iframe.
   - An external icon button allows opening the PDF in a dedicated browser tab.
5. If the document is Markdown/HTML/Text:
   - Displays reading stats (*"842 words · ~4 min read"*).
   - Reader mode renders formatted Markdown.
6. User clicks `[Chunks (N)]`:
   - An integrated search box appears: *"Search inside this document…"*.
   - User types keywords (e.g. *"expenses"*): chunks filter instantly in real-time, displaying section paths (`Travel › Reimbursement`) and page numbers.

### 3. Evaluation
- **Evaluation:** **Keep As Is** for desktop viewing and chunk searching. The chunk search with section breadcrumbs is exceptionally useful for auditability.
- **Current Flow → Observed Problem:** On iOS Safari and some Android browsers, iframes rendering raw PDFs either fail to scroll beyond page 1 or block touch gestures.
- **Recommended Improvement:** Add browser feature detection; if a touch/mobile agent is detected viewing a PDF, default the viewer to the extracted *"Chunks"* tab with an option banner: *"Viewing extracted text chunks. Tap here to open original PDF in a new tab"*.
- **Expected Benefit:** Eliminates stuck mobile iframes and improves document readability on small screens.

---

## Flow 4: Session Chat Management & Accidental Reload Prevention

### 1. Context & User Intent
- **Starting Point:** User has conducted a multi-turn conversation in their current browser session.
- **User Goal:** Create new chats, review previous chat sessions, switch between them, and ensure conversations aren't lost by accidentally refreshing the page.

### 2. Step-by-Step Sequence
1. User clicks *"Start new chat"* in the sidebar (or presses `Cmd/Ctrl + K`).
2. A fresh chat session is generated with title *"New chat"*.
3. When the user asks the first question, the session title dynamically updates from *"New chat"* to the first 36 characters of their question.
4. Sessions persist in `sessionStorage` under `askdocs_browser_sessions`.
5. User clicks browser refresh button (or presses `Cmd+R` / `F5`):
   - A native browser confirmation dialog interrupts: *"Leave site? Changes you made may not be saved."*
   - If user cancels, the conversation remains intact.
6. User can switch between sessions by clicking the session title in the sidebar.
7. User hovers over a session item and clicks `×` to delete it.

### 3. Evaluation
- **Evaluation:** **Keep As Is** for the `beforeunload` confirmation guardrail and session naming logic. This directly solves the problem of accidental data loss in ephemeral browser-based LLM sessions.
- **Current Flow → Observed Problem:** Deleting a chat session (`useChatSession.ts:L92-L107`) is triggered immediately upon clicking the `×` icon without confirmation. On mobile devices where sidebar items are compact, tapping slightly to the right of a chat title accidentally triggers delete, wiping the conversation permanently.
- **Recommended Improvement:** Add a secondary confirmation step (e.g., clicking `×` changes the button to a red *"Delete?"* confirm button for 3 seconds before executing, or opens a modal dialog).
- **Expected Benefit:** Prevents accidental deletion of chat sessions.

---

## Flow 5: Developer Settings Configuration & Hot-Swapping

### 1. Context & User Intent
- **Starting Point:** User or developer wants to switch LLM models (e.g., test Groq `llama-3.3-70b` vs Anthropic `claude-sonnet-5-5`) or enter an API key without modifying `.env` or restarting Docker containers.
- **User Goal:** Open developer settings, select provider, configure model, test or update keys, and apply changes in real-time.

### 2. Step-by-Step Sequence
1. User clicks *"Developer settings"* at the bottom of the sidebar.
2. A right-anchored modal drawer slides out with a dimmed backdrop (`bg-slate-900/30 backdrop-blur-[1px]`).
3. Settings query fetches current server state from `/api/v1/settings`.
4. Provider dropdown allows switching between Anthropic, OpenAI, Groq, and Ollama.
5. Changing provider automatically updates model suggestions in the datalist.
6. An API key field shows whether a key is already configured on the server (`•••••••• (set)`), allowing override.
7. User clicks *"Save"*: settings update via `POST /api/v1/settings` and invalidate backend `/api/v1/health` cache.
8. Status message confirms: *"Saved. Applies to the next question."*
9. User closes dialog via *"Close"* button, backdrop click, or `Escape` key.

### 3. Evaluation
- **Evaluation:** **Keep As Is** for the backend hot-swapping and model datalist suggestion architecture. The in-memory override design without requiring a server restart is outstanding for developer testing.
- **Current Flow → Observed Problem 1:** Focus is not trapped inside the modal dialog. Pressing `Tab` repeatedly moves focus out of the modal into the invisible buttons and inputs on the page behind the backdrop.
  - **Recommended Improvement:** Implement standard Tab loop focus containment on the dialog container.
  - **Expected Benefit:** WCAG 2.2 SC 2.1.2 compliance and reliable keyboard navigation.
- **Current Flow → Observed Problem 2:** The close button in the header (`DeveloperSettings.tsx:L205`) uses a raw unicode `×` character without an accessible SVG or label.
  - **Recommended Improvement:** Replace with an accessible SVG close icon with `aria-label="Close developer settings"`.
  - **Expected Benefit:** High visual polish and correct screen reader announcements.
