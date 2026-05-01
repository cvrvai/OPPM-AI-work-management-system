"""Git integration schemas."""

from pydantic import BaseModel, Field


class GitAccountCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=100)
    github_username: str = Field(min_length=1, max_length=100)
    token: str = Field(min_length=1)


class RepoConfigCreate(BaseModel):
    repo_name: str = Field(min_length=1)
    project_id: str
    github_account_id: str
    webhook_secret: str = Field(min_length=8)


class RepoConfigUpdate(BaseModel):
    repo_name: str | None = Field(default=None, min_length=1)
    project_id: str | None = None
    github_account_id: str | None = None
    webhook_secret: str | None = Field(default=None, min_length=8)
    is_active: bool | None = None
