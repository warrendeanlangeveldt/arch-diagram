---
name: arch-diagram
description: House-style architecture, infrastructure, and process diagrams as print-grade inline SVG, with the official AWS, Azure and Google Cloud icon packs plus generic glyphs for everything else. Use when asked for an architecture, deployment, integration, sequence, data-flow, step, state, swimlane, or phase/timeline diagram — especially anything client-facing or destined for a PDF. Also use for C4 diagrams (system context, container, component, deployment, dynamic); for enterprise-architecture views in ArchiMate 3.2, the TOGAF Content Metamodel (catalogs, matrices, diagrams), the Essential Meta-Model, or CoreEA / OrbusInfinity viewpoints and SAD views (Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization diagrams, CRUD matrix); for BPMN 2.0 process diagrams; for writing those views as text in a view language that lays itself out (diagrams as code, like Mermaid); and for exporting a model to EA tools (ArchiMate exchange XML, BPMN XML, CSV catalogues, OrbusInfinity import).
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
request names one or clearly needs one; it then overrides the type table
(its reference maps back to the house recipes it reuses):

| Request mentions | Methodology | Reference |
|---|---|---|
| C4; context / container / component / code diagram | C4 (Simon Brown) | `references/c4.md` |
| ArchiMate; layered, application cooperation, capability map, motivation, migration view | ArchiMate 3.2 | `references/ea.md` + `references/archimate.md` |
| TOGAF; ADM phase deliverables; catalog / matrix; Business Footprint, Application Communication, Environments and Locations, Project Context | TOGAF Content Metamodel | `references/ea.md` + `references/togaf.md` |
| Essential, Essential Project / EAS; capability-to-application, application provider, technology reference model | Essential Meta-Model | `references/ea.md` + `references/essential.md` |
| CoreEA, OrbusInfinity, EA viewpoint, SAD view: Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization diagram, CRUD matrix | CoreEA | `references/ea.md` + `references/coreea.md` |
| BPMN; business process, pools and lanes, events and gateways, process to import into Camunda / Signavio | BPMN 2.0 | `references/ea.md` + `references/bpmn.md` |
| Import into / export for an EA tool: Archi, Sparx, BiZZdesign, ADOIT, OrbusInfinity, Essential, Camunda | exports | `references/exports.md` |

The EA frameworks are model-first: build one `model.json`, validate it with
`scripts/ea.py validate`, then write the views as a view file (`views.ead`,
`references/dsl.md`) and draw them with `scripts/ea.py render`, which lays
them out. Place a view by hand with the `scripts/ealib` View API only as the
exception: `render` warned about it (`layout:` warnings), the PNG confirms the
problem, and the hints in `dsl.md` didn't fix it, or the view needs something
the language can't say. Keep that view in the view file as
`view ID script="file.py"` so one `render` still draws every view, and tell the
person which view is placed by hand and why.
When the person names no framework, SAD views and EA viewpoints stay in
CoreEA as in 1.x; for anything else, ask when the choice changes the result,
and say which framework you used. The design system below
applies to all of them.

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

Read `references/icons.md`. In short:

- Platform components (S3, Cosmos DB, Cloud Run …) use the official AWS,
  Azure or Google Cloud icon when that pack is fetched
  (`scripts/icons.py status`; fetching needs the person to accept the
  vendor's terms, `icons.py fetch aws --accept-terms`).
- Everything else, and platform components whose pack isn't fetched, uses
  the 64 generic glyphs in `icons.svg` (24×24, stroke 1.7, round caps).
- `scripts/icons.py resolve "<component>"` picks the icon;
  `icons.py svg "<component>" --x X --y Y --size 20` prints the fragment to
  paste into hand-laid SVG. In a 58-high box: icon at (x+14, y+19), text
  centred at boxX + 34 + (w−34)/2.
- Never draw product logos (Salesforce, Kafka, React); they map to generic
  glyphs through `scripts/icon_aliases.json`.

## Procedure

1. Route to a type; read its reference file; resolve the icons needed
   (`scripts/icons.py resolve`).
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

   (Elsewhere use `google-chrome` / `chromium`, or `CHROME_PATH`. EA and
   BPMN views render themselves: `ea.py render` and `View.save()` write the
   PNG.)

   Read the PNG. Check: no text clipped behind boxes, no arrowhead
   piercing a box, no label crossing a line, frames contain children
   with ≥12px padding, band labels have headroom. Fix and re-render
   until clean.

Known failure modes (each has happened): sub-labels clipping behind a
neighbouring box (measure text width); arrowheads touching box edges;
pandoc `<colgroup>` widths fighting document CSS; duplicate marker ids
silently reusing the first definition.
