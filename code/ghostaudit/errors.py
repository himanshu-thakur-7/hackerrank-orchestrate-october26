"""The solver's error family.

Every error ghostaudit raises on purpose derives from GhostAuditError: the run stops on it rather
than skip evidence or guess. Bugs surface as ordinary Python exceptions, never as one of these.

Decisions: ADR 0007 (an unknown evidence format is a hard error, never silently skipped).
"""


class GhostAuditError(Exception):
    """Base of every deliberate solver error; catching it never hides an unrelated bug."""
