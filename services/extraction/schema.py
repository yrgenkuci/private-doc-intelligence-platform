"""Invoice data models for structured extraction.

Based on industry-standard invoice schemas and best practices.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceData(BaseModel):
    """Structured invoice data extracted from document.

    Schema based on common invoice fields found in financial documents.
    """

    invoice_number: str | None = Field(None, description="Unique invoice identifier")
    invoice_date: date | None = Field(None, description="Date invoice was issued")
    due_date: date | None = Field(None, description="Payment due date")

    # Supplier information
    supplier_name: str | None = Field(None, description="Supplier/vendor company name")
    supplier_address: str | None = Field(None, description="Supplier address")

    # Customer information
    customer_name: str | None = Field(None, description="Customer/buyer company name")

    # Financial details
    subtotal: Decimal | None = Field(None, description="Subtotal before tax")
    tax_amount: Decimal | None = Field(None, description="Tax amount")
    total_amount: Decimal | None = Field(None, description="Total amount including tax")
    currency: str | None = Field("USD", description="Currency code (ISO 4217)")

    # Confidence tracking
    confidence_score: float | None = Field(
        None, description="Overall extraction confidence (0-1)", ge=0, le=1
    )
