"""Shared read models for a well's configuration.

Both Rig & Well Management (which owns the configuration) and AFE Management
(which estimates against it) need the same section → phase → days view, so the
builder lives here instead of being copied into each route module.
"""

from decimal import Decimal

from app.models.rig_well import Well
from app.schemas.rig_well import PhaseOut, SectionOut, WellConfigurationOut


def well_totals(well: Well) -> tuple[Decimal | None, Decimal]:
    """``(total_depth, total_days)`` for a well.

    Total depth is the ``to_depth`` of the last ordered section; total days is
    the sum of every phase's day count across all sections.
    """

    total_depth: Decimal | None = None
    total_days = Decimal("0")
    for section in well.sections:
        total_depth = section.to_depth
        for phase in section.phases:
            total_days += phase.days
    return total_depth, total_days


def build_configuration_out(well: Well) -> WellConfigurationOut:
    """Serialise a well's configuration (sections, phases, days, totals)."""

    total_depth, total_days = well_totals(well)
    sections: list[SectionOut] = []
    for section in well.sections:
        phases: list[PhaseOut] = []
        section_days = Decimal("0")
        for phase in section.phases:
            section_days += phase.days
            phases.append(
                PhaseOut(
                    id=phase.id,
                    phase_id=phase.phase_id,
                    phase_code=phase.phase.phase_code if phase.phase else None,
                    phase_name=phase.phase.phase_name if phase.phase else None,
                    days=phase.days,
                    remarks=phase.remarks,
                )
            )
        sections.append(
            SectionOut(
                id=section.id,
                section_id=section.section_id,
                section_code=section.section.section_code if section.section else None,
                section_name=section.section.section_name if section.section else None,
                from_depth=section.from_depth,
                to_depth=section.to_depth,
                remarks=section.remarks,
                total_days=section_days,
                phases=phases,
            )
        )
    return WellConfigurationOut(
        well_id=well.id,
        well_code=well.well_code,
        well_name=well.well_name,
        rig_code=well.rig.rig_code if well.rig else None,
        rig_name=well.rig.rig_name if well.rig else None,
        status=well.status,
        config_status=well.config_status,
        depth_unit=well.depth_unit,
        total_depth=total_depth,
        total_days=total_days,
        sections=sections,
    )
