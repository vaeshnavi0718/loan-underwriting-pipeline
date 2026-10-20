"""Helpers shared by the graders."""


def report_text(report: dict) -> str:
    """All of a review report's text fields joined, so graders check every field."""
    parts = []
    for value in report.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
    return "\n".join(parts)
