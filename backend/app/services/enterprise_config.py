"""Audited enterprise configuration creation and hierarchy validation."""

from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.models.enterprise_config import (
    CostBreakdownNode,
    CostBreakdownStructure,
    EnterpriseHierarchyRule,
    EnterpriseNode,
    EnterpriseNodeType,
    EstimateTemplate,
    EstimateTemplateLine,
    RateBook,
    RateBookEntry,
    ReportingMapping,
)
from app.models.workflow import WorkflowProfile
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

ModelT = TypeVar("ModelT")


class EnterpriseConfigService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id

    def summary(self) -> EnterpriseConfigSummary:
        return EnterpriseConfigSummary(
            node_types=[
                NodeTypeRead.model_validate(item) for item in self._all(EnterpriseNodeType)
            ],
            hierarchy_rules=[
                HierarchyRuleRead.model_validate(item)
                for item in self._all(EnterpriseHierarchyRule)
            ],
            nodes=[EnterpriseNodeRead.model_validate(item) for item in self._all(EnterpriseNode)],
            cost_structures=[
                VersionedConfigRead.model_validate(item)
                for item in self._all(CostBreakdownStructure)
            ],
            rate_books=[RateBookRead.model_validate(item) for item in self._all(RateBook)],
            estimate_templates=[
                VersionedConfigRead.model_validate(item) for item in self._all(EstimateTemplate)
            ],
            reporting_mappings=[
                ReportingMappingRead.model_validate(item) for item in self._all(ReportingMapping)
            ],
            workflow_profile_count=int(
                self.session.scalar(select(func.count()).select_from(WorkflowProfile)) or 0
            ),
        )

    def create_node_type(self, request: NodeTypeCreate) -> NodeTypeRead:
        item = EnterpriseNodeType(
            code=request.code.strip().upper(),
            name=request.name.strip(),
            level_order=request.level_order,
            description=request.description,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        return NodeTypeRead.model_validate(self._save(item))

    def create_rule(self, request: HierarchyRuleCreate) -> HierarchyRuleRead:
        if request.parent_type_id == request.child_type_id:
            raise BusinessValidationError("Hierarchy parent and child types must differ")
        self._get(EnterpriseNodeType, request.parent_type_id, "Parent node type")
        self._get(EnterpriseNodeType, request.child_type_id, "Child node type")
        item = EnterpriseHierarchyRule(
            parent_type_id=request.parent_type_id,
            child_type_id=request.child_type_id,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        return HierarchyRuleRead.model_validate(self._save(item))

    def create_node(self, request: EnterpriseNodeCreate) -> EnterpriseNodeRead:
        self._get(EnterpriseNodeType, request.node_type_id, "Node type")
        if request.parent_id:
            parent = self._get(EnterpriseNode, request.parent_id, "Parent node")
            rule = self.session.scalar(
                select(EnterpriseHierarchyRule).where(
                    EnterpriseHierarchyRule.parent_type_id == parent.node_type_id,
                    EnterpriseHierarchyRule.child_type_id == request.node_type_id,
                    EnterpriseHierarchyRule.is_active.is_(True),
                )
            )
            if rule is None:
                raise BusinessValidationError(
                    "The configured hierarchy does not permit this parent-child type relationship"
                )
        item = EnterpriseNode(
            node_type_id=request.node_type_id,
            parent_id=request.parent_id,
            code=request.code.strip().upper(),
            name=request.name.strip(),
            description=request.description,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        return EnterpriseNodeRead.model_validate(self._save(item))

    def create_cost_structure(self, request: VersionedConfigCreate) -> VersionedConfigRead:
        return VersionedConfigRead.model_validate(
            self._save(CostBreakdownStructure(**self._versioned(request)))
        )

    def add_cost_node(self, structure_id: UUID, request: CostBreakdownNodeCreate) -> dict[str, Any]:
        structure = self._get(CostBreakdownStructure, structure_id, "Cost structure")
        if structure.lifecycle_status != "draft":
            raise BusinessValidationError("Only draft cost structures can be edited")
        item = CostBreakdownNode(
            structure_id=structure_id,
            **request.model_dump(),
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        saved = self._save(item)
        return {
            "id": saved.id,
            "structure_id": structure_id,
            "code": saved.code,
            "name": saved.name,
        }

    def create_rate_book(self, request: RateBookCreate) -> RateBookRead:
        if (
            request.effective_from
            and request.effective_to
            and request.effective_to < request.effective_from
        ):
            raise BusinessValidationError("Rate-book effective_to cannot precede effective_from")
        values = self._versioned(request)
        values.update(effective_from=request.effective_from, effective_to=request.effective_to)
        return RateBookRead.model_validate(self._save(RateBook(**values)))

    def add_rate(self, rate_book_id: UUID, request: RateBookEntryCreate) -> dict[str, Any]:
        book = self._get(RateBook, rate_book_id, "Rate book")
        if book.lifecycle_status != "draft":
            raise BusinessValidationError("Only draft rate books can be edited")
        saved = self._save(
            RateBookEntry(
                rate_book_id=rate_book_id,
                rate_id=request.rate_id,
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
        )
        return {"id": saved.id, "rate_book_id": rate_book_id, "rate_id": request.rate_id}

    def create_template(self, request: VersionedConfigCreate) -> VersionedConfigRead:
        return VersionedConfigRead.model_validate(
            self._save(EstimateTemplate(**self._versioned(request)))
        )

    def add_template_line(
        self, template_id: UUID, request: EstimateTemplateLineCreate
    ) -> dict[str, Any]:
        template = self._get(EstimateTemplate, template_id, "Estimate template")
        if template.lifecycle_status != "draft":
            raise BusinessValidationError("Only draft estimate templates can be edited")
        saved = self._save(
            EstimateTemplateLine(
                template_id=template_id,
                **request.model_dump(),
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
        )
        return {"id": saved.id, "template_id": template_id, "line_number": saved.line_number}

    def create_mapping(self, request: ReportingMappingCreate) -> ReportingMappingRead:
        item = ReportingMapping(
            **request.model_dump(),
            lifecycle_status="draft",
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        return ReportingMappingRead.model_validate(self._save(item))

    def _versioned(self, request: VersionedConfigCreate) -> dict[str, Any]:
        return {
            "code": request.code.strip().upper(),
            "name": request.name.strip(),
            "version_number": request.version_number,
            "description": request.description,
            "lifecycle_status": "draft",
            "created_by": self.actor_id,
            "updated_by": self.actor_id,
        }

    def _all(self, model: type[ModelT]) -> list[ModelT]:
        return list(self.session.scalars(select(model).order_by(model.created_at)).all())  # type: ignore[attr-defined]

    def _get(self, model: type[ModelT], item_id: UUID, label: str) -> ModelT:
        item = self.session.get(model, item_id)
        if item is None:
            raise NotFoundError(f"{label} not found")
        return item

    def _save(self, item: ModelT) -> ModelT:
        self.session.add(item)  # type: ignore[arg-type]
        self.session.commit()
        self.session.refresh(item)
        return item
