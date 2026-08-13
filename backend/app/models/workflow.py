"""Versioned workflow configuration, estimate workflow state, and review audit records."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.estimates import EstimateVersion
from app.models.role import Role


class WorkflowProfile(TimestampMixin, AuditMixin, Base):
    __tablename__ = "workflow_profiles"
    __table_args__ = (
        UniqueConstraint("code", "version_number", name="uq_workflow_profiles_code_version"),
        CheckConstraint("version_number >= 1", name="positive_version"),
        CheckConstraint(
            "lifecycle_status IN ('draft','validated','published','retired')",
            name="valid_lifecycle_status",
        ),
        Index("ix_workflow_profiles_record_lifecycle", "record_type", "lifecycle_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    record_type: Mapped[str] = mapped_column(String(50), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    states: Mapped[list["WorkflowState"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )
    transitions: Mapped[list["WorkflowTransitionDefinition"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkflowState(TimestampMixin, AuditMixin, Base):
    __tablename__ = "workflow_states"
    __table_args__ = (
        UniqueConstraint("profile_id", "state_key", name="uq_workflow_states_profile_key"),
        CheckConstraint("sort_order >= 0", name="non_negative_sort_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_profiles.id", ondelete="CASCADE"), index=True
    )
    state_key: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    profile: Mapped[WorkflowProfile] = relationship(back_populates="states")


class WorkflowTransitionDefinition(TimestampMixin, AuditMixin, Base):
    __tablename__ = "workflow_transition_definitions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "from_state_key",
            "action_key",
            name="uq_workflow_transitions_profile_from_action",
        ),
        CheckConstraint("sort_order >= 0", name="non_negative_sort_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_profiles.id", ondelete="CASCADE"), index=True
    )
    action_key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(100))
    from_state_key: Mapped[str] = mapped_column(String(50))
    to_state_key: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    requires_comment: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    profile: Mapped[WorkflowProfile] = relationship(back_populates="transitions")
    role_mappings: Mapped[list["WorkflowTransitionRole"]] = relationship(
        back_populates="transition", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkflowTransitionRole(TimestampMixin, AuditMixin, Base):
    __tablename__ = "workflow_transition_roles"
    __table_args__ = (
        UniqueConstraint("transition_id", "role_id", name="uq_workflow_transition_roles_pair"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    transition_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_transition_definitions.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)

    transition: Mapped[WorkflowTransitionDefinition] = relationship(back_populates="role_mappings")
    role: Mapped[Role] = relationship(lazy="joined")


class EstimateWorkflowInstance(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_workflow_instances"
    __table_args__ = (
        UniqueConstraint("estimate_version_id", name="uq_estimate_workflow_instances_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    workflow_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_profiles.id", ondelete="RESTRICT"), index=True
    )
    current_state_key: Mapped[str] = mapped_column(String(50), index=True)

    estimate_version: Mapped[EstimateVersion] = relationship(lazy="joined")
    workflow_profile: Mapped[WorkflowProfile] = relationship(lazy="joined")


class WorkflowTransitionAttempt(TimestampMixin, AuditMixin, Base):
    __tablename__ = "workflow_transition_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('completed','blocked','denied','failed')", name="valid_status"),
        Index(
            "ix_workflow_transition_attempts_version_created",
            "estimate_version_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    workflow_instance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("estimate_workflow_instances.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow_profile_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_profiles.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    requested_action: Mapped[str] = mapped_column(String(100))
    from_state_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_state_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    estimate_version: Mapped[EstimateVersion] = relationship(lazy="joined")
    workflow_instance: Mapped[EstimateWorkflowInstance | None] = relationship(lazy="joined")
    workflow_profile: Mapped[WorkflowProfile | None] = relationship(lazy="joined")


class EstimateReviewComment(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_review_comments"
    __table_args__ = (
        Index("ix_estimate_review_comments_version_created", "estimate_version_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)

    estimate_version: Mapped[EstimateVersion] = relationship(lazy="joined")
