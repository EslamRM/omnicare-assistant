from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, field_validator
class ClaimType(str, Enum):
    WATER_DAMAGE = "Water Damage"
    PERSONAL_PROPERTY = "Personal Property"
    FIRE = "Fire"
    THEFT = "Theft"
    OTHER = "Other"
class ClaimStatusRequest(BaseModel): claim_id: str = Field(..., pattern=r"^CLM-\d{3,10}$")
class ClaimStatusResult(BaseModel):
    found: bool; claim_id: str; policy_number: str|None=None; claim_type: str|None=None; status: str|None=None; amount: Decimal|None=None
class SubmitClaimRequest(BaseModel):
    policy_number: str = Field(..., pattern=r"^POL-\d{3,10}$")
    claim_type: ClaimType
    amount: Decimal = Field(..., gt=0, le=Decimal('100000'), decimal_places=2)
    description: str = Field(..., min_length=10, max_length=1000)
    @field_validator('description')
    @classmethod
    def strip_and_check(cls,v):
        v=v.strip()
        if not v: raise ValueError('description cannot be empty')
        return v
class SubmitClaimResult(BaseModel):
    confirmation_id:str; claim_id:str; status:str; duplicate:bool=False
