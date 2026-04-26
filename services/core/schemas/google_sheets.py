"""Schemas for the Google Sheets OPPM MVP."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class GoogleSheetLinkUpsert(BaseModel):
    spreadsheet_id: Optional[str] = Field(default=None, min_length=10)
    spreadsheet_url: Optional[str] = Field(default=None, min_length=10)

    @model_validator(mode="after")
    def validate_one_input(self) -> "GoogleSheetLinkUpsert":
        if not self.spreadsheet_id and not self.spreadsheet_url:
            raise ValueError("spreadsheet_id or spreadsheet_url is required")
        return self


class GoogleSheetLinkResponse(BaseModel):
    connected: bool
    spreadsheet_id: Optional[str] = None
    spreadsheet_url: Optional[str] = None
    backend_configured: bool
    service_account_email: Optional[str] = None
    backend_configuration_error: Optional[str] = None


class GoogleSheetsSetupStatusResponse(BaseModel):
    backend_configured: bool
    service_account_email: Optional[str] = None
    backend_configuration_error: Optional[str] = None
    credential_source: Optional[str] = None


class GoogleSheetsSetupUpsert(BaseModel):
    service_account_json: str = Field(min_length=20)


class GoogleSheetPushTaskOwner(BaseModel):
    member_id: str
    priority: str


class GoogleSheetPushTimelineItem(BaseModel):
    week_start: str
    status: Optional[str] = None
    quality: Optional[str] = None


class GoogleSheetPushTaskItem(BaseModel):
    index: str
    title: str
    deadline: Optional[str] = None
    status: Optional[str] = None
    is_sub: bool
    owners: list[GoogleSheetPushTaskOwner] = Field(default_factory=list)
    timeline: list[GoogleSheetPushTimelineItem] = Field(default_factory=list)


class GoogleSheetPushMemberItem(BaseModel):
    id: str
    slot: int
    name: str


class GoogleSheetPushRequest(BaseModel):
    fills: dict[str, Optional[str]]
    tasks: list[GoogleSheetPushTaskItem] = Field(default_factory=list)
    members: list[GoogleSheetPushMemberItem] = Field(default_factory=list)


class GoogleSheetPushResponse(BaseModel):
    spreadsheet_id: str
    spreadsheet_url: str
    updated_sheets: list[str]
    rows_written: dict[str, int]
