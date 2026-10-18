import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Citation } from "./api/client";
import AnswerView from "./components/AnswerView";
import AskBox from "./components/AskBox";
import CitationPanel from "./components/CitationPanel";
import DeveloperSettings from "./components/DeveloperSettings";
import DocumentViewer from "./components/DocumentViewer";
import Feedback from "./components/Feedback";
import NotFoundState from "./components/NotFoundState";
import UploadPanel from "./components/UploadPanel";
import { useAskStream } from "./hooks/useAskStream";
import { useChatSession } from "./hooks/useChatSession";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const STARTER_PROMPTS = [
  { label: "Parental leave policy", prompt: "How long is parental leave for primary caregivers?" },
  { label: "Working remotely", prompt: "Can employees work remotely and what are the core hours?" },
  { label: "Travel & expenses", prompt: "Within how many days must expense receipts be submitted in Expensify?" },
  { label: "Sick leave days", prompt: "How many days of paid sick leave do employees get per year?" },
];

export default function App() {
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const documentsQuery = useQuery({ queryKey: ["documents"], queryFn: api.documents });
  const ask = useAskStream();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarTab, setSidebarTab] = useState<"chats" | "docs">("chats");
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [rightPanelTab, setRightPanelTab] = useState<"doc" | "citations">("citations");
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

  const [heroDragging, setHeroDragging] = useState(false);
  const heroFileInput = useRef<HTMLInputElement>(null);
  const [heroJobId, setHeroJobId] = useState<string | null>(null);
  const [justUploadedDocName, setJustUploadedDocName] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem("askdocs_last_uploaded_doc") || null;
    } catch {
      return null;
    }
  });

  const heroJob = useQuery({
    queryKey: ["heroIngest", heroJobId],
    queryFn: () => api.ingestJob(heroJobId!),
    enabled: heroJobId !== null,
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status) ? false : 1000),
  });

  const heroUpload = useMutation({
    mutationFn: api.ingest,
    onSuccess: (started) => setHeroJobId(started.job_id),
  });

  useEffect(() => {
    if (heroJob.data?.status === "completed") {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
      const uploadedFile = heroJob.data.results[0]?.file_name || "your document";
      setJustUploadedDocName(uploadedFile);
      try {
        sessionStorage.setItem("askdocs_last_uploaded_doc", uploadedFile);
      } catch {}
      const newDocId = heroJob.data.results[0]?.doc_id;
      if (newDocId) {
        setPreviewDocId(newDocId);
        setRightPanelTab("doc");
        setRightPanelOpen(true);
      }
    }
  }, [heroJob.data?.status, heroJob.data?.results, queryClient]);

  const allDocs = documentsQuery.data ?? [];
  const userUploads = allDocs.filter((d) => d.source_type === "user_upload");

  const streaming = ask.status === "streaming";
  const {
    sessions,
    activeSession,
    newChat,
    selectChat,
    deleteChat,
    clearAllChats,
    startTurn,
    updateStreamingTurn,
    completeTurn,
    failTurn,
    stopTurn,
  } = useChatSession(streaming);

  const [currentTurnId, setCurrentTurnId] = useState<string | null>(null);

  const handleSelectDocument = useCallback((docId: string) => {
    setPreviewDocId(docId);
    setRightPanelTab("doc");
    setRightPanelOpen(true);
  }, []);

  const handleAsk = useCallback(
    (question: string) => {
      const turnId = startTurn(question);
      setCurrentTurnId(turnId);
      ask.ask(question);
    },
    [ask, startTurn]
  );

  const handleStop = useCallback(() => {
    ask.stop();
    if (currentTurnId) {
      stopTurn(currentTurnId);
      setCurrentTurnId(null);
    }
  }, [ask, currentTurnId, stopTurn]);

  // Sync ask stream updates with active session turn
  useEffect(() => {
    if (!currentTurnId) return;

    if (ask.status === "streaming") {
      updateStreamingTurn(currentTurnId, ask.text, ask.retried);
    } else if (ask.status === "done" && ask.result) {
      completeTurn(currentTurnId, ask.result);
      if (ask.result.citations.length > 0) {
        setActiveCitation(ask.result.citations[0].n);
        setRightPanelTab("citations");
        setRightPanelOpen(true);
      }
      setCurrentTurnId(null);
    } else if (ask.status === "error" && ask.error) {
      failTurn(currentTurnId, ask.error.message);
      setCurrentTurnId(null);
    } else if (ask.status === "stopped") {
      stopTurn(currentTurnId);
      setCurrentTurnId(null);
    }
  }, [ask.status, ask.text, ask.retried, ask.result, ask.error, currentTurnId, updateStreamingTurn, completeTurn, failTurn, stopTurn]);

  // Derive latest citations from active session or current stream
  const activeTurn = activeSession?.turns[activeSession.turns.length - 1];
  const latestCitations: Citation[] = ask.result?.citations ?? activeTurn?.citations ?? [];

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {/* Developer settings modal */}
      <DeveloperSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {/* Left Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-slate-200 bg-white transition-all duration-200 dark:border-slate-800 dark:bg-slate-900 md:static ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:-ml-72"
        }`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3.5 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-xs">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
                />
              </svg>
            </span>
            <span className="text-sm font-bold tracking-tight">Ask My Docs</span>
          </div>

          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="Collapse sidebar"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 md:hidden"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3 pb-2">
          <button
            type="button"
            onClick={newChat}
            className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-800 shadow-2xs transition hover:border-indigo-400 hover:bg-white hover:text-indigo-600 dark:border-slate-800 dark:bg-slate-850 dark:text-slate-200 dark:hover:border-indigo-500"
          >
            <span className="flex items-center gap-2">
              <svg className="h-4 w-4 text-indigo-600 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              Start new chat
            </span>
            <kbd className="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-slate-500 dark:border-slate-700 dark:bg-slate-800">
              New
            </kbd>
          </button>
        </div>

        {/* Sidebar Navigation Tabs */}
        <div className="flex border-b border-slate-200 px-3 dark:border-slate-800">
          <button
            type="button"
            onClick={() => setSidebarTab("chats")}
            className={`flex-1 border-b-2 py-2 text-center text-xs font-semibold transition ${
              sidebarTab === "chats"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            Chats ({sessions.length})
          </button>
          <button
            type="button"
            onClick={() => setSidebarTab("docs")}
            className={`flex-1 border-b-2 py-2 text-center text-xs font-semibold transition ${
              sidebarTab === "docs"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            Documents
          </button>
        </div>

        {/* Sidebar Content Area */}
        <div className="flex-1 overflow-y-auto p-3">
          {sidebarTab === "chats" ? (
            <div className="space-y-1">
              <div className="flex items-center justify-between px-1.5 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Browser Session History
                </span>
                {sessions.length > 1 && (
                  <button
                    type="button"
                    onClick={clearAllChats}
                    className="text-[10px] text-slate-400 hover:text-red-600 transition"
                  >
                    Clear all
                  </button>
                )}
              </div>

              {sessions.map((s) => {
                const isActive = s.id === activeSession?.id;
                return (
                  <div
                    key={s.id}
                    onClick={() => selectChat(s.id)}
                    className={`group flex items-center justify-between rounded-lg px-2.5 py-2 text-xs transition cursor-pointer ${
                      isActive
                        ? "bg-indigo-50 font-semibold text-indigo-950 dark:bg-slate-800 dark:text-indigo-300"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/60"
                    }`}
                  >
                    <span className="truncate pr-1" title={s.title}>
                      {s.title}
                    </span>
                    <button
                      type="button"
                      aria-label="Delete chat"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteChat(s.id);
                      }}
                      className="rounded p-1 text-slate-400 opacity-0 hover:text-red-600 focus:opacity-100 group-hover:opacity-100 transition"
                    >
                      <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                      </svg>
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <UploadPanel onSelectDocument={handleSelectDocument} activeDocId={previewDocId} />
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="border-t border-slate-200 p-3 text-xs dark:border-slate-800">
          <button
            type="button"
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen(true)}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>Developer settings</span>
          </button>
        </div>
      </aside>

      {/* Main Conversation Stage */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Navigation Bar */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Toggle sidebar"
              onClick={() => setSidebarOpen((v) => !v)}
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:hover:bg-slate-800"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h7" />
              </svg>
            </button>
            <h1 className="text-sm font-semibold truncate max-w-[200px] sm:max-w-md">
              {activeSession?.title || "Ask My Docs"}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            {/* System Status */}
            <span className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              <span
                aria-hidden
                className={`h-2 w-2 rounded-full ${
                  health.data?.status === "ok" ? "bg-emerald-500" : health.isError ? "bg-red-500" : "bg-amber-500"
                }`}
              />
              {health.data
                ? `${health.data.documents} docs · ${health.data.chunks} chunks · ${health.data.llm.model}`
                : "Connecting…"}
            </span>

            {/* Toggle Right Inspector Panel */}
            <button
              type="button"
              aria-label="Toggle inspector panel"
              onClick={() => setRightPanelOpen((v) => !v)}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition ${
                rightPanelOpen
                  ? "border-indigo-600 bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"
                  : "border-slate-200 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-400"
              }`}
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span>{rightPanelTab === "doc" ? "Document Viewer" : "Sources"}</span>
            </button>
          </div>
        </header>

        {/* Middle Stage: Chat Section + Right Inspector Panel */}
        <div className="flex flex-1 overflow-hidden">
          {/* Main Chat Section (constrained and isolated from right panel) */}
          <main className="relative flex flex-1 flex-col overflow-hidden">
            {/* Scrollable Conversation Content */}
            <div className="flex-1 overflow-y-auto">
              <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col p-4 sm:p-6 pb-36">
              {/* Empty state */}
              {activeSession?.turns.length === 0 && !streaming && (
                <div className="my-auto flex flex-col items-center justify-center py-8 text-center">
                  {!justUploadedDocName && userUploads.length === 0 ? (
                    /* First-Time User View */
                    <>
                      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 shadow-xs dark:bg-indigo-950/60 dark:text-indigo-400">
                        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
                          />
                        </svg>
                      </div>

                      <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                        {getGreeting()}
                      </h2>

                      <p className="mt-1.5 text-base font-medium text-slate-600 dark:text-slate-300">
                        Ask any question about your document
                      </p>

                      {/* Prominent Upload Field for First Time User */}
                      <div className="mt-6 w-full max-w-lg">
                        <div
                          role="button"
                          tabIndex={0}
                          aria-label="Upload document"
                          onClick={() => heroFileInput.current?.click()}
                          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && heroFileInput.current?.click()}
                          onDragOver={(e) => {
                            e.preventDefault();
                            setHeroDragging(true);
                          }}
                          onDragLeave={() => setHeroDragging(false)}
                          onDrop={(e) => {
                            e.preventDefault();
                            setHeroDragging(false);
                            if (e.dataTransfer.files?.length) {
                              heroUpload.mutate(Array.from(e.dataTransfer.files));
                            }
                          }}
                          className={`group relative cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-all ${
                            heroDragging
                              ? "border-indigo-500 bg-indigo-50/70 dark:border-indigo-400 dark:bg-indigo-950/30"
                              : "border-slate-300 bg-white hover:border-indigo-500 hover:bg-slate-50/60 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-indigo-400"
                          }`}
                        >
                          <input
                            ref={heroFileInput}
                            type="file"
                            multiple
                            accept=".pdf,.md,.markdown,.html,.htm,.txt"
                            hidden
                            onChange={(e) => {
                              if (e.target.files?.length) {
                                heroUpload.mutate(Array.from(e.target.files));
                                e.target.value = "";
                              }
                            }}
                          />

                          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50 text-indigo-600 group-hover:scale-110 transition-transform dark:bg-indigo-950/60 dark:text-indigo-400">
                            {heroUpload.isPending || (heroJob.data && heroJob.data.status !== "completed" && heroJob.data.status !== "failed") ? (
                              <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
                            ) : (
                              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                              </svg>
                            )}
                          </div>

                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                            {heroUpload.isPending || (heroJob.data && heroJob.data.status !== "completed" && heroJob.data.status !== "failed")
                              ? "Indexing and processing your document…"
                              : "Upload a document to get started"}
                          </p>
                          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            Drag & drop or click to browse · PDF, Markdown, HTML or TXT
                          </p>

                          {heroUpload.isError && (
                            <p className="mt-2 text-xs text-red-600">{heroUpload.error.message}</p>
                          )}
                          {heroJob.data?.status === "failed" && (
                            <p className="mt-2 text-xs text-red-600">Failed: {heroJob.data.error}</p>
                          )}
                        </div>
                      </div>

                      {/* Or ask about pre-loaded policies */}
                      <div className="mt-8 w-full max-w-xl">
                        <div className="relative mb-4 flex items-center justify-center">
                          <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-slate-200 dark:border-slate-800" />
                          </div>
                          <span className="relative bg-slate-50 px-3 text-[11px] font-medium uppercase tracking-wider text-slate-400 dark:bg-slate-950">
                            Or ask about pre-loaded policies
                          </span>
                        </div>

                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          {STARTER_PROMPTS.map((starter) => (
                            <button
                              key={starter.label}
                              type="button"
                              onClick={() => handleAsk(starter.prompt)}
                              className="rounded-xl border border-slate-200 bg-white p-3 text-left text-xs transition hover:border-indigo-400 hover:shadow-xs dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-500"
                            >
                              <p className="font-semibold text-slate-800 dark:text-slate-200">{starter.label}</p>
                              <p className="mt-0.5 line-clamp-1 text-slate-500 dark:text-slate-400">{starter.prompt}</p>
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  ) : (
                    /* Post-Upload View: "You can ask anything from the document" */
                    <>
                      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 shadow-xs dark:bg-emerald-950/60 dark:text-emerald-400">
                        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                        </svg>
                      </div>

                      <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                        You can ask anything from the document
                      </h2>

                      <p className="mt-1.5 max-w-md text-sm text-slate-500 dark:text-slate-400">
                        Your document is verified and indexed. Ask any question below or pick a quick suggestion to explore.
                      </p>

                      {/* Uploaded document badge */}
                      <div className="mt-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-700 shadow-2xs dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 text-[11px] font-bold dark:bg-emerald-950 dark:text-emerald-400">
                          ✓
                        </span>
                        <span className="font-medium truncate max-w-xs font-mono text-[11px]">
                          {justUploadedDocName || userUploads[0]?.title || userUploads[0]?.file_name}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">Ready</span>
                      </div>

                      {/* Quick starter questions tailored to the document */}
                      <div className="mt-6 grid w-full max-w-xl grid-cols-1 gap-2.5 sm:grid-cols-2">
                        {[
                          { label: "Document summary", prompt: "Can you provide a summary of the main points in this document?" },
                          { label: "Key findings & requirements", prompt: "What are the most important requirements or takeaways?" },
                          { label: "Important dates & deadlines", prompt: "Are there any specific dates, deadlines or timeframes mentioned?" },
                          { label: "Specific guidelines", prompt: "What are the specific guidelines or procedures outlined?" },
                        ].map((starter) => (
                          <button
                            key={starter.label}
                            type="button"
                            onClick={() => handleAsk(starter.prompt)}
                            className="rounded-xl border border-slate-200 bg-white p-3 text-left text-xs transition hover:border-indigo-500 hover:shadow-xs dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-400"
                          >
                            <p className="font-semibold text-slate-800 dark:text-slate-200">{starter.label}</p>
                            <p className="mt-0.5 line-clamp-1 text-slate-500 dark:text-slate-400">{starter.prompt}</p>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Chat turns */}
              <div className="space-y-6">
                {activeSession?.turns.map((turn) => {
                  const turnStreaming = turn.streaming;
                  const turnAbstained = turn.abstained;
                  const turnCitations = turn.citations ?? [];

                  return (
                    <div key={turn.id} className="space-y-4">
                      {/* User query bubble */}
                      <div className="flex justify-end">
                        <div className="max-w-[85%] rounded-2xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-xs">
                          {turn.question}
                        </div>
                      </div>

                      {/* Assistant answer card */}
                      <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs dark:border-slate-800 dark:bg-slate-900">
                        {turn.retried && turnStreaming && (
                          <p className="mb-2 text-xs text-slate-500">
                            Re-checking citations and regenerating…
                          </p>
                        )}
                        {turnStreaming && !turn.answer && (
                          <div className="flex items-center gap-2 py-2 text-sm text-slate-500">
                            <span className="h-2 w-2 rounded-full bg-indigo-600 animate-ping" />
                            <span>Searching and synthesizing verified sources…</span>
                          </div>
                        )}

                        {turn.error && (
                          <p role="alert" className="text-sm text-red-600">
                            {turn.error}
                          </p>
                        )}

                        {turnAbstained ? (
                          <NotFoundState reason={turn.abstainReason ?? null} />
                        ) : (
                          turn.answer && (
                            <AnswerView
                              text={turn.answer}
                              streaming={Boolean(turnStreaming)}
                              activeCitation={activeCitation}
                              availableCitations={new Set(turnCitations.map((c) => c.n))}
                              onSelectCitation={(n) => {
                                setActiveCitation(n);
                                setRightPanelTab("citations");
                                setRightPanelOpen(true);
                              }}
                            />
                          )
                        )}

                        {turn.queryId && (
                          <footer className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                            <Feedback key={turn.queryId} queryId={turn.queryId} />
                            <div className="flex items-center gap-2 text-xs text-slate-400">
                              {turn.latencyMs?.total && (
                                <span>{(turn.latencyMs.total / 1000).toFixed(1)} s</span>
                              )}
                              {turn.usage && turn.usage.input_tokens > 0 && (
                                <span>
                                  · {turn.usage.input_tokens + turn.usage.output_tokens} tokens
                                </span>
                              )}
                            </div>
                          </footer>
                        )}
                      </article>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

            {/* Floating Bottom Input Box (anchored strictly to chat section) */}
            <div className="absolute inset-x-0 bottom-0 pointer-events-none bg-gradient-to-t from-slate-50 via-slate-50/90 to-transparent p-4 pt-6 dark:from-slate-950 dark:via-slate-950/90">
              <div className="mx-auto max-w-3xl pointer-events-auto">
                <AskBox streaming={streaming} onAsk={handleAsk} onStop={handleStop} />
              </div>
            </div>
          </main>

          {/* Right Inspector Panel (PDF Viewer / Document Viewer & Citations) */}
          <aside
            className={`flex flex-col border-l border-slate-200 bg-white transition-all duration-200 dark:border-slate-800 dark:bg-slate-900 ${
              rightPanelOpen ? "w-80 lg:w-[480px]" : "w-0 overflow-hidden"
            }`}
          >
            {/* Panel Mode Switcher Tabs */}
            <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-800">
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setRightPanelTab("citations")}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                    rightPanelTab === "citations"
                      ? "bg-indigo-600 text-white shadow-2xs"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                  }`}
                >
                  Sources ({latestCitations.length})
                </button>
                <button
                  type="button"
                  onClick={() => setRightPanelTab("doc")}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                    rightPanelTab === "doc"
                      ? "bg-indigo-600 text-white shadow-2xs"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                  }`}
                >
                  Document Viewer
                </button>
              </div>

              <button
                type="button"
                aria-label="Close inspector"
                onClick={() => setRightPanelOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
              >
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                </svg>
              </button>
            </div>

            {/* Panel Body */}
            <div className="flex-1 overflow-hidden">
              {rightPanelTab === "citations" ? (
                <div className="h-full overflow-y-auto p-3">
                  {latestCitations.length > 0 ? (
                    <CitationPanel
                      citations={latestCitations}
                      active={activeCitation}
                      answer={activeTurn?.answer || ask.text || ""}
                      onSelect={setActiveCitation}
                      onViewDoc={handleSelectDocument}
                    />
                  ) : (
                    <div className="flex h-64 flex-col items-center justify-center p-6 text-center text-slate-400">
                      <svg className="mb-2 h-8 w-8 stroke-current stroke-1" fill="none" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                      </svg>
                      <p className="text-xs font-medium">No sources active</p>
                      <p className="mt-1 text-[11px]">Ask a question to see supporting citations here</p>
                    </div>
                  )}
                </div>
              ) : (
                <DocumentViewer docId={previewDocId} onClose={() => setRightPanelOpen(false)} />
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
