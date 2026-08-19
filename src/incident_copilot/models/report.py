"""Structured incident report models."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from incident_copilot.models.enums import AgentName, EvidenceSource


class EvidenceRef(BaseModel):
    """A pointer to the observation that supports a claim."""

    model_config = ConfigDict(frozen=True)

    source: EvidenceSource
    detail: str


class LikelyCause(BaseModel):
    """One candidate root cause."""

    model_config = ConfigDict(frozen=True)

    title: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: tuple[EvidenceRef, ...]


class IncidentReport(BaseModel):
    """The structured output of an investigation."""

    summary: str
    likely_causes: tuple[LikelyCause, ...]
    next_steps: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _drop_hollow_and_rank(self) -> Self:
        """Discard causes citing no evidence or carrying no real content, then rank.

        A cause with a blank title or rationale is schema-valid but as useless as one
        citing no evidence - the model filled the shape without saying anything. Ranking
        is structural rather than a prompt instruction, so a model that emits causes in
        arbitrary order still produces a correctly ranked report.
        """
        grounded = [
            c
            for c in self.likely_causes
            if c.supporting_evidence and c.title.strip() and c.rationale.strip()
        ]
        ranked = tuple(sorted(grounded, key=lambda c: c.confidence, reverse=True))
        object.__setattr__(self, "likely_causes", ranked)
        return self


class RouteDecision(BaseModel):
    """The supervisor's choice of which specialists to run."""

    model_config = ConfigDict(frozen=True)

    agents: tuple[AgentName, ...] = Field(min_length=1)
    reasoning: str
