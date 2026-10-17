import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-lg font-semibold">Ask My Docs</h1>
        <span className="text-xs text-slate-500">
          {health.data ? `${health.data.documents} documents · ${health.data.llm.model}` : "Connecting…"}
        </span>
      </header>
    </div>
  );
}
