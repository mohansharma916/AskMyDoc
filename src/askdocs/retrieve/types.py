from dataclasses import dataclass, field


@dataclass
class Candidate:
    """A retrieved chunk with everything needed to rerank, prompt and cite it."""

    chunk_id: str
    doc_id: str
    text: str
    file_name: str = ""
    title: str = ""
    page: int | None = None
    section_path: tuple[str, ...] = ()
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def section(self) -> str:
        return " > ".join(self.section_path)
