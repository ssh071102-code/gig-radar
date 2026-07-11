"""Single source of truth for generated config templates.

config/positioning.example.md in the repo is a rendered copy of POSITIONING_TEMPLATE;
a test asserts they stay in sync.
"""

POSITIONING_TEMPLATE = """# Positioning & Case Studies

## One-line positioning
I help <ideal client> achieve <outcome> using AI integration, automation, and AI video.

## Case cards
### Case 1: <case study title>
- What was built:
- Result:
- Transferable to:

### Case 2: <case study title>
- What was built:
- Result:
- Transferable to:

### Case 3: <case study title>
- What was built:
- Result:
- Transferable to:

## Rate anchor
- $/hr or fixed-price range:

## Tone
-
"""
