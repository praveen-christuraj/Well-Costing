"""Escape database URLs for Alembic's ini-backed configuration."""


def escape_for_alembic(url: str) -> str:
    """Double ``%`` characters so Alembic can store a URL without errors.

    ``alembic.config.Config.set_main_option`` writes into a
    :class:`configparser.ConfigParser` with basic interpolation enabled, where
    a single ``%`` starts an interpolation reference. Any URL containing one —
    most commonly a percent-encoded password character such as ``%25`` for a
    literal ``%`` — otherwise raises ``ValueError: invalid interpolation
    syntax`` before migrations can run. Doubling the character is
    configparser's own escaping rule; the value read back contains the
    original single ``%`` again, so SQLAlchemy receives the intended URL.
    """

    return url.replace("%", "%%")
