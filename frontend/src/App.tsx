import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { api, type Citation } from "./api/client";
import AnswerView from "./components/AnswerView";
import AskBox from "./components/AskBox";
import CitationPanel from "./components/CitationPanel";
import DeveloperSettings from "./components/DeveloperSettings";
import DocumentPreview from "./components/DocumentPreview";
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
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const ask = useAskStream();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarTab, setSidebarTab] = useState<"chats" | "docs">("chats");
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [rightPanelTab, setRightPanelTab] = useState<"doc" | "citations">("citations");
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

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
    <div className="flex h-screen overflow-hidden bg-[#FAF9F5] text-[#232220] dark:bg-[#1C1B1A] dark:text-[#F2EFE9]">
      {/* Developer settings modal */}
      <DeveloperSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {/* Claude-style Left Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-[#E6E4DD] bg-[#F4F3EE] transition-all duration-200 dark:border-[#33322E] dark:bg-[#171615] md:static ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:-ml-72"
        }`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between border-b border-[#E6E4DD] px-4 py-3.5 dark:border-[#33322E]">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#C15F3D] text-white shadow-xs">
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" />
              </svg>
            </span>
            <span className="font-serif text-base font-semibold tracking-tight">Ask My Docs</span>
          </div>

          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="Collapse sidebar"
            className="rounded-lg p-1 text-[#6E6C66] hover:bg-[#E6E4DD] hover:text-[#232220] dark:text-[#9E9C94] dark:hover:bg-[#33322E] md:hidden"
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
            className="flex w-full items-center justify-between rounded-xl border border-[#E6E4DD] bg-white px-3.5 py-2.5 text-xs font-medium text-[#232220] shadow-2xs transition hover:border-[#C15F3D] hover:bg-[#FAF9F5] dark:border-[#33322E] dark:bg-[#262524] dark:text-[#F2EFE9] dark:hover:border-[#C15F3D]"
          >
            <span className="flex items-center gap-2">
              <svg className="h-4 w-4 text-[#C15F3D]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              Start new chat
            </span>
            <kbd className="rounded border border-[#E6E4DD] bg-[#F4F3EE] px-1.5 py-0.5 font-mono text-[10px] text-[#6E6C66] dark:border-[#33322E] dark:bg-[#171615]">
              New
            </kbd>
          </button>
        </div>

        {/* Sidebar Nav Tabs */}
        <div className="flex border-b border-[#E6E4DD] px-3 dark:border-[#33322E]">
          <button
            type="button"
            onClick={() => setSidebarTab("chats")}
            className={`flex-1 border-b-2 py-2 text-center text-xs font-medium transition ${
              sidebarTab === "chats"
                ? "border-[#C15F3D] text-[#C15F3D]"
                : "border-transparent text-[#6E6C66] hover:text-[#232220] dark:text-[#9E9C94] dark:hover:text-[#F2EFE9]"
            }`}
          >
            Chats ({sessions.length})
          </button>
          <button
            type="button"
            onClick={() => setSidebarTab("docs")}
            className={`flex-1 border-b-2 py-2 text-center text-xs font-medium transition ${
              sidebarTab === "docs"
                ? "border-[#C15F3D] text-[#C15F3D]"
                : "border-transparent text-[#6E6C66] hover:text-[#232220] dark:text-[#9E9C94] dark:hover:text-[#F2EFE9]"
            }`}
          >
            Documents
          </button>
        </div>

        {/* Sidebar Content */}
        <div className="flex-1 overflow-y-auto p-3">
          {sidebarTab === "chats" ? (
            <div className="space-y-1">
              <div className="flex items-center justify-between px-1.5 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[#6E6C66] dark:text-[#9E9C94]">
                  Session History
                </span>
                {sessions.length > 1 && (
                  <button
                    type="button"
                    onClick={clearAllChats}
                    className="text-[10px] text-[#6E6C66] hover:text-red-600 dark:text-[#9E9C94]"
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
                        ? "bg-white font-medium text-[#232220] shadow-2xs dark:bg-[#262524] dark:text-[#F2EFE9]"
                        : "text-[#6E6C66] hover:bg-[#EAE8E1] dark:text-[#9E9C94] dark:hover:bg-[#262524]/60"
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
                      className="rounded p-1 text-[#6E6C66] opacity-0 hover:text-red-600 focus:opacity-100 group-hover:opacity-100 dark:text-[#9E9C94]"
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
        <div className="border-t border-[#E6E4DD] p-3 text-xs dark:border-[#33322E]">
          <button
            type="button"
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen(true)}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[#6E6C66] transition hover:bg-[#E6E4DD] hover:text-[#232220] dark:text-[#9E9C94] dark:hover:bg-[#262524] dark:hover:text-[#F2EFE9]"
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
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#E6E4DD] bg-[#FAF9F5] px-4 dark:border-[#33322E] dark:bg-[#1C1B1A]">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Toggle sidebar"
              onClick={() => setSidebarOpen((v) => !v)}
              className="rounded-lg p-1.5 text-[#6E6C66] hover:bg-[#EAE8E1] hover:text-[#232220] dark:text-[#9E9C94] dark:hover:bg-[#262524]"
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
            <span className="hidden items-center gap-2 text-xs text-[#6E6C66] dark:text-[#9E9C94] sm:flex">
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
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                rightPanelOpen
                  ? "border-[#C15F3D] bg-[#F9EFEA] text-[#C15F3D] dark:bg-[#C15F3D]/10"
                  : "border-[#E6E4DD] text-[#6E6C66] hover:bg-[#EAE8E1] dark:border-[#33322E] dark:text-[#9E9C94]"
              }`}
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span>{rightPanelTab === "doc" ? "Document" : "Sources"}</span>
            </button>
          </div>
        </header>

        {/* Middle Stage: Chat Thread + Floating Input */}
        <div className="relative flex flex-1 overflow-hidden">
          <main className="flex flex-1 flex-col overflow-y-auto">
            <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col p-4 sm:p-6 pb-36">
              {/* Empty state: Claude-style warm greeting & starters */}
              {activeSession?.turns.length === 0 && !streaming && (
                <div className="my-auto flex flex-col items-center justify-center py-12 text-center">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#F9EFEA] text-[#C15F3D] shadow-2xs dark:bg-[#C15F3D]/20">
                    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" />
                    </svg>
                  </div>
                  <h2 className="font-serif text-3xl font-normal tracking-tight text-[#232220] dark:text-[#F2EFE9]">
                    {getGreeting()}
                  </h2>
                  <p className="mt-2 max-w-md text-sm text-[#6E6C66] dark:text-[#9E9C94]">
                    Ask any question about verified company policies, leave entitlements, travel reimbursement, and IT procedures.
                  </p>

                  <div className="mt-8 grid w-full max-w-xl grid-cols-1 gap-2.5 sm:grid-cols-2">
                    {STARTER_PROMPTS.map((starter) => (
                      <button
                        key={starter.label}
                        type="button"
                        onClick={() => handleAsk(starter.prompt)}
                        className="rounded-xl border border-[#E6E4DD] bg-white p-3.5 text-left text-xs transition hover:border-[#C15F3D] hover:shadow-2xs dark:border-[#33322E] dark:bg-[#262524]"
                      >
                        <p className="font-medium text-[#232220] dark:text-[#F2EFE9]">{starter.label}</p>
                        <p className="mt-1 line-clamp-2 text-[#6E6C66] dark:text-[#9E9C94]">{starter.prompt}</p>
                      </button>
                    ))}
                  </div>
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
                        <div className="max-w-[85%] rounded-2xl bg-[#EAE8E1] px-4 py-2.5 text-sm font-medium text-[#232220] dark:bg-[#262524] dark:text-[#F2EFE9]">
                          {turn.question}
                        </div>
                      </div>

                      {/* Assistant answer card */}
                      <article className="rounded-2xl border border-[#E6E4DD] bg-white p-5 shadow-2xs dark:border-[#33322E] dark:bg-[#262524]">
                        {turn.retried && turnStreaming && (
                          <p className="mb-2 text-xs text-[#6E6C66] dark:text-[#9E9C94]">
                            Re-checking citations and regenerating…
                          </p>
                        )}
                        {turnStreaming && !turn.answer && (
                          <div className="flex items-center gap-2 py-2 text-sm text-[#6E6C66] dark:text-[#9E9C94]">
                            <span className="h-2 w-2 rounded-full bg-[#C15F3D] animate-ping" />
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
                          <footer className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#F4F3EE] pt-3 dark:border-[#33322E]">
                            <Feedback key={turn.queryId} queryId={turn.queryId} />
                            <div className="flex items-center gap-2 text-xs text-[#6E6C66] dark:text-[#9E9C94]">
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

            {/* Floating Claude Input Box */}
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#FAF9F5] via-[#FAF9F5]/90 to-transparent p-4 pt-6 dark:from-[#1C1B1A] dark:via-[#1C1B1A]/90">
              <div className="mx-auto max-w-3xl">
                <AskBox streaming={streaming} onAsk={handleAsk} onStop={handleStop} />
              </div>
            </div>
          </main>

          {/* Right Inspector Drawer (Document Preview & Citations) */}
          <aside
            className={`flex flex-col border-l border-[#E6E4DD] bg-[#FAF9F5] transition-all duration-200 dark:border-[#33322E] dark:bg-[#1C1B1A] ${
              rightPanelOpen ? "w-80 lg:w-96" : "w-0 overflow-hidden"
            }`}
          >
            {/* Panel Tabs */}
            <div className="flex items-center justify-between border-b border-[#E6E4DD] px-3 py-2 dark:border-[#33322E]">
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setRightPanelTab("citations")}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                    rightPanelTab === "citations"
                      ? "bg-[#C15F3D] text-white"
                      : "text-[#6E6C66] hover:bg-[#EAE8E1] dark:text-[#9E9C94] dark:hover:bg-[#262524]"
                  }`}
                >
                  Citations ({latestCitations.length})
                </button>
                <button
                  type="button"
                  onClick={() => setRightPanelTab("doc")}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                    rightPanelTab === "doc"
                      ? "bg-[#C15F3D] text-white"
                      : "text-[#6E6C66] hover:bg-[#EAE8E1] dark:text-[#9E9C94] dark:hover:bg-[#262524]"
                  }`}
                >
                  Document Preview
                </button>
              </div>

              <button
                type="button"
                aria-label="Close inspector"
                onClick={() => setRightPanelOpen(false)}
                className="rounded-lg p-1 text-[#6E6C66] hover:bg-[#EAE8E1] hover:text-[#232220] dark:text-[#9E9C94] dark:hover:bg-[#262524]"
              >
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                </svg>
              </button>
            </div>

            {/* Panel Body */}
            <div className="flex-1 overflow-y-auto p-3">
              {rightPanelTab === "citations" ? (
                latestCitations.length > 0 ? (
                  <CitationPanel
                    citations={latestCitations}
                    active={activeCitation}
                    answer={activeTurn?.answer || ask.text || ""}
                    onSelect={setActiveCitation}
                    onViewDoc={handleSelectDocument}
                  />
                ) : (
                  <div className="flex h-64 flex-col items-center justify-center p-6 text-center text-[#6E6C66] dark:text-[#9E9C94]">
                    <svg className="mb-2 h-8 w-8 stroke-current stroke-1" fill="none" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                    </svg>
                    <p className="text-xs font-medium">No citations yet</p>
                    <p className="mt-1 text-[11px]">Ask a question to see supporting citations here</p>
                  </div>
                )
              ) : (
                <DocumentPreview docId={previewDocId} onClose={() => setRightPanelOpen(false)} />
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
