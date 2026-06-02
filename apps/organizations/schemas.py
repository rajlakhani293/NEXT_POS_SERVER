from typing import Optional

from ninja import Schema
from pydantic import Field


class CompanyUpdateIn(Schema):
    name: str = Field(..., description="Display company name shown in the product after onboarding.", example="Raj Retail Private Limited")
    legal_name: Optional[str] = Field("", description="Registered legal business name.", example="Raj Retail Private Limited")
    email: Optional[str] = Field("", description="Primary company email address.", example="owner@rajretail.com")
    phone: Optional[str] = Field("", description="Primary company phone number.", example="9999999999")
    gst_number: Optional[str] = Field("", description="GST or tax number.", example="24ABCDE1234F1Z5")
    city_name: Optional[str] = Field("", description="Company city name.", example="Surat")
    state_id: Optional[int] = Field(None, description="Company state master id.", example=11)
    address: Optional[str] = Field("", description="Company address.", example="Ring Road, Surat, Gujarat")
    logo: Optional[str] = Field("", description="Company logo URL.", example="https://example.com/logo.png")


class BranchUpdateIn(Schema):
    name: str = Field(..., description="Branch display name. The first branch starts as Main Branch.", example="Main Branch")
    phone: Optional[str] = Field("", description="Branch contact phone.", example="9999999999")
    address: Optional[str] = Field("", description="Branch street address.", example="Ground Floor, Ring Road")
    city: Optional[str] = Field("", description="Branch city.", example="Surat")
    state_id: Optional[int] = Field(None, description="Branch state master id.", example=11)
    postal_code: Optional[str] = Field("", description="Branch postal code.", example="395002")


class BranchIn(BranchUpdateIn):
    code: Optional[str] = Field("", description="Optional branch code. Auto-generated from branch name when blank.", example="main")


class BranchPatchIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state_id: Optional[int] = None
    postal_code: Optional[str] = None
    is_head_office: Optional[bool] = None
    status: Optional[int] = None


class OrganizationSetupIn(Schema):
    company: CompanyUpdateIn = Field(
        ...,
        description="Company profile data that replaces the placeholder company created during onboarding.",
        example={
            "name": "Raj Retail Private Limited",
            "legal_name": "Raj Retail Private Limited",
            "email": "owner@rajretail.com",
            "phone": "9999999999",
            "gst_number": "24ABCDE1234F1Z5",
            "city_name": "Surat",
            "state_id": 11,
            "address": "Ring Road, Surat, Gujarat",
            "logo": "https://example.com/logo.png",
        },
    )
    branch: BranchUpdateIn = Field(
        ...,
        description="Primary branch data. The initial branch starts as Main Branch and can be renamed later.",
        example={
            "name": "Main Branch",
            "phone": "9999999999",
            "address": "Ground Floor, Ring Road",
            "city": "Surat",
            "state_id": 11,
            "postal_code": "395002",
        },
    )
