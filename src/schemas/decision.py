from dataclasses import dataclass, field


@dataclass
class DecisionRequest:
    """Request payload for LLM decision-making."""

    domain: str
    data: list[dict]
    decisions: list[str]
