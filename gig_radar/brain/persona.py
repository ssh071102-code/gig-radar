"""Persona resolution: who the prompts speak for.

The `persona:` block in config/settings.yaml is interpolated into both the triage
and the drafting prompts, so nothing about a specific person is hardcoded in code.
"""

DEFAULT_PERSONA = {
    "name": "the freelancer",
    "wheelhouse": "AI integration, AI video, automation",
    "experience": "a cold newcomer with no platform rating",
}


def resolve_persona(persona: dict | None) -> dict[str, str]:
    """Merge a (possibly partial or missing) config persona over safe defaults."""
    return {**DEFAULT_PERSONA, **(persona or {})}
