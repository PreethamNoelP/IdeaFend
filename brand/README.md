# IdeaFend brand assets

## Concept

The mark is an asymmetric cut crystal: an idea gets cut and pressure-tested from multiple angles (the independent research and debate agents) before it's judged solid enough to build on — the same way a gem is formed and cut under pressure. The asymmetry is deliberate: a perfectly symmetric hexagon reads as a heraldic shield, which is the overused cliché for "defend/security" tools and not what this mark is after.

Two other directions were explored and set aside:
- **Converge** — a ring of nodes with lines running to a central point, standing for several blind agents resolving to one verdict. Rejected: the dots-and-lines network glyph is one of the most overused motifs in AI/tech branding.
- **IF monogram** — a geometric "IF" built from two strokes, with the F's lower arm cut into an arrow. Clean and very legible small, but it illustrates the name rather than the product's actual mechanism. Kept as a fallback direction, not used.

## Palette

| Role | Hex | Use |
| --- | --- | --- |
| Ink (darkest) | `#14172C` | Body text on light backgrounds, deepest facet |
| Primary | `#1B1F3B` | Dominant brand color, app-icon background |
| Secondary | `#3D4A85` | Mid facet |
| Tint | `#6B7AB8` | Lit facet, light accents on dark backgrounds |
| Accent | `#E8793A` | The single "spark" facet only — used sparingly, never as a dominant color |
| Paper | `#F7F5F0` | Light background, wordmark on dark backgrounds |

Indigo (cool, analytical, trustworthy) carries the identity; amber (warm, friction, insight) is a one-facet accent, not a co-equal brand color. This keeps the mark legible in pure monochrome (`symbol-mono.svg`, single flat fill, no gradients) and distinct from Anthropic/Claude's own warm terracotta-on-cream identity, since this is a third-party, unaffiliated plugin.

## Files

| File | Use |
| --- | --- |
| `logo-light.svg` | Primary lockup (symbol + wordmark) for light backgrounds |
| `logo-dark.svg` | Primary lockup for dark backgrounds |
| `symbol.svg` | Standalone color symbol |
| `symbol-mono.svg` | Single-color symbol (`fill="currentColor"`) for contexts needing one ink color |
| `favicon.svg` | Simplified symbol (no stroke detail) for small sizes; modern browsers support SVG favicons directly |
| `icon.svg` | App/profile icon — symbol on a rounded-square primary-color background |

All files are plain vector SVG, no external fonts or images, transparent backgrounds except `icon.svg`.
