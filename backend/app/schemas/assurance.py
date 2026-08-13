"""Phase 11 structural assurance status contracts."""

from pydantic import BaseModel


class AssuranceCheck(BaseModel):
    key: str
    label: str
    status: str
    violations: int
    detail: str


class AssuranceBlocker(BaseModel):
    key: str
    status: str
    detail: str


class AssuranceStatus(BaseModel):
    status: str
    migration_head: str
    reporting_contract_version: str
    checks: list[AssuranceCheck]
    blockers: list[AssuranceBlocker]
