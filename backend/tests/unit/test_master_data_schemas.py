"""Output schemas must tolerate NULL columns from legacy master-data tables."""

from app.schemas.master_data import ActivityOut, CurrencyOut, HoleSectionOut


class _LegacyCurrency:
    id = 1
    currency_code = "USD"
    currency_name = "US Dollar"
    currency_symbol = None
    description = None
    is_deleted = None
    deleted_at = None
    created_at = None
    updated_at = None


class _LegacyActivity:
    id = 2
    activity_code = "DRL"
    activity_name = None
    description = None
    is_deleted = False
    deleted_at = None
    created_at = None
    updated_at = None


class _LegacyHoleSection:
    id = 3
    section_code = None
    section_name = "17-1/2 in"
    description = None
    is_deleted = False
    deleted_at = None
    created_at = None
    updated_at = None


def test_currency_out_coerces_null_symbol() -> None:
    out = CurrencyOut.model_validate(_LegacyCurrency())
    assert out.currency_code == "USD"
    assert out.currency_symbol == ""
    assert out.is_deleted is False
    assert out.created_at is None


def test_activity_out_coerces_null_name() -> None:
    out = ActivityOut.model_validate(_LegacyActivity())
    assert out.activity_code == "DRL"
    assert out.activity_name == ""


def test_hole_section_out_coerces_null_code() -> None:
    out = HoleSectionOut.model_validate(_LegacyHoleSection())
    assert out.section_code == ""
    assert out.section_name == "17-1/2 in"
