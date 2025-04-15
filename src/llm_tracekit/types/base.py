from typing import Any

from pydantic import BaseModel


class SpanAttributeGeneratingType(BaseModel):
    """Base class for types from which gen AI span attributes can be generated."""

    def generate_span_attributes(self) -> dict[str, Any]:
        """Generate span attributes from the data in this type."""
        return {}
