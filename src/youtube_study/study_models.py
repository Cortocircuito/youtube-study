from __future__ import annotations

from dataclasses import dataclass

from .transcript import Cue

ANALYSIS_FORMAT_VERSION = 2


@dataclass(frozen=True)
class SourceFragment:
    """Exact portion of one transcript cue used as study evidence."""

    cue_index: int
    timestamp: str
    start: int
    end: int
    text: str

    def __post_init__(self) -> None:
        if self.cue_index < 0:
            raise ValueError("cue_index debe ser >= 0")
        if self.start < 0 or self.end < self.start:
            raise ValueError("El rango del fragmento fuente es inválido")
        if self.end - self.start != len(self.text):
            raise ValueError("El texto del fragmento no coincide con su rango fuente")


@dataclass(frozen=True)
class SourceExcerpt:
    """Extractive evidence with stable links to its source transcript cues."""

    text: str
    fragments: tuple[SourceFragment, ...]

    def __post_init__(self) -> None:
        if not self.text.strip() or not self.fragments:
            raise ValueError("Un extracto fuente necesita texto y al menos un fragmento")
        if " ".join(fragment.text for fragment in self.fragments) != self.text:
            raise ValueError("El texto del extracto no coincide con sus fragmentos fuente")

    @property
    def timestamp(self) -> str:
        return self.fragments[0].timestamp

    @property
    def cue_positions(self) -> tuple[int, ...]:
        return tuple(fragment.cue_index for fragment in self.fragments)


@dataclass(frozen=True)
class StudyIdea:
    evidence: SourceExcerpt

    @property
    def text(self) -> str:
        return self.evidence.text

    @property
    def timestamp(self) -> str:
        return self.evidence.timestamp


@dataclass(frozen=True)
class ToolMention:
    name: str
    count: int
    description: str
    category: str = "tool"
    kind: str = "known"


@dataclass
class ConceptMention:
    name: str
    score: int
    count: int
    timestamps: list[str]


@dataclass(frozen=True)
class StudyQuestion:
    question: str
    evidence: SourceExcerpt
    category: str

    @property
    def answer(self) -> str:
        return self.evidence.text

    @property
    def timestamp(self) -> str:
        return self.evidence.timestamp

    @property
    def source_excerpt(self) -> str:
        return self.evidence.text


@dataclass(frozen=True)
class Flashcard:
    question: str
    evidence: SourceExcerpt
    tags: str

    @property
    def answer(self) -> str:
        return self.evidence.text

    @property
    def timestamp(self) -> str:
        return self.evidence.timestamp

    @property
    def source_excerpt(self) -> str:
        return self.evidence.text


@dataclass
class AnalysisResult:
    cues: list[Cue]
    keywords: list[tuple[str, int]]
    tools: list[ToolMention]
    ideas: list[StudyIdea]
    sections: list[tuple[str, str, list[str]]]
    concepts: list[ConceptMention]
    questions: dict[str, list[StudyQuestion]]
    cards: list[Flashcard]
    format_version: int = ANALYSIS_FORMAT_VERSION


def flatten_questions(questions: dict[str, list[StudyQuestion]]) -> list[StudyQuestion]:
    return [question for group in questions.values() for question in group]
