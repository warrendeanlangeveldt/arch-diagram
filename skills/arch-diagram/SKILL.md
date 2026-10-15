---
name: arch-diagram
description: House-style architecture, infrastructure, and process diagrams as print-grade inline SVG, with a vendor-agnostic icon library (AWS/Azure/GCP components map to concept glyphs). Use when asked for an architecture, deployment, integration, sequence, data-flow, step, state, swimlane, or phase/timeline diagram — especially anything client-facing or destined for a PDF. Also use for C4 diagrams (system context, container, component, deployment, dynamic) and for CoreEA / OrbusInfinity enterprise-architecture viewpoints and SAD views (Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization diagrams, CRUD matrix).
---

# arch-diagram — print-grade architecture SVG

Hand-authored inline SVG beats mermaid for client-facing material:
exact layout, house palette, annotations on the arrows, zero-tooling
embedding in markdown → pandoc → PDF. This skill routes a request to a
diagram type, whose reference file carries the full recipe and an SVG
skeleton.

**When NOT to use:** quick dev-doc sketches where GitHub-native
rendering matters — use mermaid there.

## Routing

Pick the closest type, tell the user which you chose, then **read that
type's reference file before writing any SVG**:

| Type | Use for | Reference |
|---|---|---|
| `deployment` | runtime infra in a cloud account | `references/deployment.md` |
| `system-context` | actors, the system, externals — no internals | `references/system-context.md` |
| `integration` | two platforms and their contract | `references/integration.md` |
| `data-flow` | pipelines, ETL, request paths | `references/data-flow.md` |
| `sequence` | ordered messages over time | `references/sequence.md` |
| `deploy-path` | CI/CD and trust chains | `references/deploy-path.md` |
| `steps` | numbered procedures, onboarding, "step graph" | `references/steps.md` |
| `state` | lifecycles, status machines | `references/state.md` |
| `swimlane` | who does what across parties | `references/swimlane.md` |
| `phases` | roadmaps, work packages, rollouts | `references/phases.md` |

## Methodologies

Default is the house types above. Switch methodology only when the
request names one; it then overrides the type table (its reference maps
back to the house recipes it reuses):

| Request mentions | Methodology | Reference |
|---|---|---|
| C4; context / container / component / code diagram | C4 (Simon Brown) | `references/c4.md` |
| CoreEA, OrbusInfinity, EA viewpoint, SAD view: Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization diagram, CRUD matrix | CoreEA | `references/coreea.md` + `scripts/` |

CoreEA is model-first: build and `validate()` one `model.json`, then
draw every view from it with `scripts/coreea_lib.py`. The design
system below still applies to both.

## Design system (applies to every type)

Theme tokens — override with the project's brand where one exists
(read the app's CSS variables or the document letterhead):

```
accent      #0d9488   (one accent; the 1–2 things the reader sees first)
ink         #0f172a   titles      body   #475569  sub-lines/arrows
muted       #64748b   labels      frame  #94a3b8  outer frames
band-a      #f8fafc   band-b #eef2f7   accent-fill #f0fdfa   line #e2e8f0
```

- Canvas `viewBox="0 0 740 H"`; coordinates and gaps divisible by 4
  where possible.
- Text width ≈ 0.52 × font-size × chars — measure before placing near
  boxes; split or widen rather than shrink fonts.
- Arrows: stroke 1.3 body, orthogonal elbows, `marker-end` head,
  **stop 2px short of the target edge**. Labels 9px muted, never
  crossing a box.
- Unique `<marker>` ids per SVG in the same document (`arr`, `arr2`…).
  Canonical arrowhead (reference skeletons abbreviate this):
  ```svg
  <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"
          markerHeight="7" orient="auto-start-reverse">
    <path d="M 0 1 L 9 5 L 0 9 z" fill="#475569"/>
  </marker>
  ```
- Density 4/10: every node earns its place — the highest-quality move
  is usually deletion. No shadows, no gradients.

## Icons

`icons.svg` holds 40 stroke glyphs (24×24, stroke 1.7, round caps).
Copy a symbol's INNER elements inline within
`<g transform="translate(x y) scale(0.833)">` (→ 20px) and set the
colour to the node's stroke. In a 58-high box: glyph at
(x+14, y+19), text centred at boxX + 34 + (w−34)/2.

**Never vendor logos.** Map component names to concept glyphs with
`references/icon-aliases.md` (AWS/Azure/GCP/generic + web frameworks);
unknown components take the nearest concept or a plain box. BaaS
platforms (Supabase/Firebase) compose from `database` + `bucket` +
`identity` rather than getting one blob.

## Procedure

1. Route to a type; read its reference file; read `icons.svg` for any
   glyphs needed.
2. Spec before SVG: five lines — frames/lanes, nodes, edges + labels,
   annotations. Cut what doesn't serve the diagram's one message.
3. Lay out coordinates from the recipe constants; start from the
   skeleton in the reference file.
4. Wrap in `<div class="diagram">…</div>`; the document CSS should
   carry `.diagram { page-break-inside: avoid }
   .diagram svg { width: 100% }`.
5. **Verify visually — mandatory.** Render and look:

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --headless --disable-gpu --window-size=800,600 \
     --screenshot=/tmp/diagram.png file:///path/to/diagram.html
   ```

   Read the PNG. Check: no text clipped behind boxes, no arrowhead
   piercing a box, no label crossing a line, frames contain children
   with ≥12px padding, band labels have headroom. Fix and re-render
   until clean.

Known failure modes (each has happened): sub-labels clipping behind a
neighbouring box (measure text width); arrowheads touching box edges;
pandoc `<colgroup>` widths fighting document CSS; duplicate marker ids
silently reusing the first definition.
