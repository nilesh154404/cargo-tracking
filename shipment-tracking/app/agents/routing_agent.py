from typing import Optional
from sqlalchemy.orm import Session
from app.tools.carrier_tools import CarrierIdentificationTool
from app.core.identifier import IdentificationResult


class RoutingAgent:
    """Agent responsible for identifying carrier, mode, and planning provider execution with fallback strategy."""

    def __init__(self):
        self.identification_tool = CarrierIdentificationTool

    def route(
        self,
        query: str,
        explicit_mode: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> IdentificationResult:
        return self.identification_tool.execute(
            query=query,
            explicit_mode=explicit_mode,
            db=db,
        )
