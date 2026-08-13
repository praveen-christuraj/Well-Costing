"""Rate resolution placeholder."""

from typing import Never


def resolve_rate(context: object) -> Never:
    """Business rule to be confirmed during Excel/business-rule discovery."""

    del context
    raise NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")
