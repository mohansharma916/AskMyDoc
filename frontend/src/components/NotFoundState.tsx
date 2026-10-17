const REASONS: Record<string, string> = {
  low_confidence: "None of the indexed passages were relevant enough to answer this.",
  no_results: "No indexed passages matched this question.",
  not_in_documents: "The most relevant passages don't contain the answer.",
  citation_check_failed: "An answer couldn't be fully supported with citations, so it was withheld.",
};

export default function NotFoundState({ reason }: { reason: string | null }) {
  return (
    <div role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
      <p className="font-medium text-amber-900 dark:text-amber-200">Not found in your documents</p>
      <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">
        {(reason && REASONS[reason]) ?? "The documents don't cover this question."} Try rephrasing, or upload a
        document that covers it.
      </p>
    </div>
  );
}
