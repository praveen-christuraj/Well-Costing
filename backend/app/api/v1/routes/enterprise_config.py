"""Bootstrap-admin enterprise configuration routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser, SystemAdministrator
from app.db.session import get_db
from app.schemas.enterprise_config import (
    CostBreakdownNodeCreate,
    EnterpriseConfigSummary,
    EnterpriseNodeCreate,
    EnterpriseNodeRead,
    EstimateTemplateLineCreate,
    HierarchyRuleCreate,
    HierarchyRuleRead,
    NodeTypeCreate,
    NodeTypeRead,
    RateBookCreate,
    RateBookEntryCreate,
    RateBookRead,
    ReportingMappingCreate,
    ReportingMappingRead,
    VersionedConfigCreate,
    VersionedConfigRead,
)
from app.services.enterprise_config import EnterpriseConfigService

router = APIRouter(prefix="/enterprise-config", tags=["enterprise configuration"])


@router.get("/summary", response_model=EnterpriseConfigSummary)
def summary(
    current_user: CurrentUser, session: Annotated[Session, Depends(get_db)]
) -> EnterpriseConfigSummary:
    return EnterpriseConfigService(session, current_user.id).summary()


def service(session: Session, admin: SystemAdministrator) -> EnterpriseConfigService:
    return EnterpriseConfigService(session, admin.id)


@router.post("/node-types", response_model=NodeTypeRead, status_code=status.HTTP_201_CREATED)
def create_node_type(
    request: NodeTypeCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> NodeTypeRead:
    return service(session, admin).create_node_type(request)


@router.post("/hierarchy-rules", response_model=HierarchyRuleRead, status_code=201)
def create_rule(
    request: HierarchyRuleCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> HierarchyRuleRead:
    return service(session, admin).create_rule(request)


@router.post("/nodes", response_model=EnterpriseNodeRead, status_code=201)
def create_node(
    request: EnterpriseNodeCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> EnterpriseNodeRead:
    return service(session, admin).create_node(request)


@router.post("/cost-structures", response_model=VersionedConfigRead, status_code=201)
def create_cost_structure(
    request: VersionedConfigCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> VersionedConfigRead:
    return service(session, admin).create_cost_structure(request)


@router.post("/cost-structures/{item_id}/nodes", response_model=dict[str, Any], status_code=201)
def add_cost_node(
    item_id: UUID,
    request: CostBreakdownNodeCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    return service(session, admin).add_cost_node(item_id, request)


@router.post("/rate-books", response_model=RateBookRead, status_code=201)
def create_rate_book(
    request: RateBookCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> RateBookRead:
    return service(session, admin).create_rate_book(request)


@router.post("/rate-books/{item_id}/rates", response_model=dict[str, Any], status_code=201)
def add_rate(
    item_id: UUID,
    request: RateBookEntryCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    return service(session, admin).add_rate(item_id, request)


@router.post("/estimate-templates", response_model=VersionedConfigRead, status_code=201)
def create_template(
    request: VersionedConfigCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> VersionedConfigRead:
    return service(session, admin).create_template(request)


@router.post("/estimate-templates/{item_id}/lines", response_model=dict[str, Any], status_code=201)
def add_template_line(
    item_id: UUID,
    request: EstimateTemplateLineCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    return service(session, admin).add_template_line(item_id, request)


@router.post("/reporting-mappings", response_model=ReportingMappingRead, status_code=201)
def create_mapping(
    request: ReportingMappingCreate,
    admin: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> ReportingMappingRead:
    return service(session, admin).create_mapping(request)
