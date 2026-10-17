"""LLM judge for citation precision: does each cited excerpt support its sentence?"""

import anthropic
from pydantic import BaseModel, Field

JUDGE_SYSTEM = (
    "You are a strict evaluator of citations in answers generated from documents. For each listed "
    "(sentence, excerpt) pair, decide whether that excerpt by itself states the facts in the sentence. "
    "Paraphrase is fine; facts that appear only in other excerpts or nowhere do not count."
)


class PairVerdict(BaseModel):
    pair: int = Field(description="The pair number from the list")
    supported: bool


class CitationVerdicts(BaseModel):
    verdicts: list[PairVerdict]


class CitationJudge:
    def __init__(self, model: str = "claude-opus-5-5", client: anthropic.Anthropic | None = None, effort="medium"):
        self.model = model
        self.effort = effort
        self._client = client or anthropic.Anthropic()

    def judge(self, pairs: list[tuple[str, int]], excerpts: list[str]) -> list[bool]:
        """One verdict per pair; citations to missing excerpts are unsupported without asking."""
        if not pairs:
            return []
        valid = [i for i, (_, n) in enumerate(pairs) if 1 <= n <= len(excerpts)]
        verdicts = [False] * len(pairs)
        if not valid:
            return verdicts
        listed = "\n\n".join(
            f"Pair {k}:\nSentence: {pairs[i][0]}\nExcerpt [{pairs[i][1]}]: {excerpts[pairs[i][1] - 1]}"
            for k, i in enumerate(valid, start=1)
        )
        response = self._client.messages.parse(
            model=self.model,
            max_tokens=8000,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": listed}],
            output_format=CitationVerdicts,
            output_config={"effort": self.effort},
        )
        by_pair = {v.pair: v.supported for v in response.parsed_output.verdicts}
        for k, i in enumerate(valid, start=1):
            verdicts[i] = by_pair.get(k, False)
        return verdicts
