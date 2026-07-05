"""Base class for structured database element values.

Kept in its own module so the localized-string types and the
element/list types can both depend on it without an import cycle.
"""


class DBElementValue:
    """Marker base for DBList and LocalizedString values."""
