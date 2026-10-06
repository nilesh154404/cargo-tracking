from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.core.identifier import parse_and_identify, IdentificationResult


class CarrierIdentificationTool:
    """Tool used by agents to identify transport mode, carrier, and fallback providers."""

    name = "identify_carrier"
    description = (
        "Analyzes raw tracking number (e.g. 16015246221, MAEU1234567), "
        "identifies transport mode (AIR/SEA), airline prefix (e.g. 160), "
        "carrier identity, and provider execution plan via database or fallback registry."
    )

    @classmethod
    def execute(
        cls,
        query: str,
        explicit_mode: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> IdentificationResult:
        return parse_and_identify(query, explicit_mode=explicit_mode, db=db)
