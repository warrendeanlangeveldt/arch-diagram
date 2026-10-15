# arch-diagram

A Claude Code plugin for print-grade architecture diagrams. Claude lays out each diagram by hand as inline SVG in one house style, renders it, looks at the render and fixes it before handing it over. The output drops straight into markdown, a Word document or a PDF without any diagramming tool.

It covers three ways of drawing:

- **House diagram types.** Ten recipes, each with layout constants and an SVG skeleton: deployment, system context, integration, data flow, sequence, deploy path, steps, state, swimlane and phases.
- **C4.** System context, container, component, deployment and dynamic views, following C4's rules: one level per diagram, every element labelled with its type and technology, every line labelled, and a key on every diagram.
- **CoreEA.** Enterprise-architecture viewpoints in the CoreEA metamodel used by OrbusInfinity: Application Context, Application Integration, Logical Data, Infrastructure, Capability, Business Strategy, Project Context, Risk Catalogue, Organization diagrams and the CRUD matrix. Every view is drawn from one object model, so an object has the same id, type and name in every view, and the model exports as a catalogue an architecture team can load into their repository.

![A CoreEA Application Context Diagram drawn from the example model](docs/coreea-application-context.png)

## Install

```
/plugin marketplace add warrendeanlangeveldt/arch-diagram
/plugin install arch-diagram@arch-diagram
```

Then ask for a diagram in plain words: "draw the deployment for this service", "a C4 container diagram of the API", "the Application Integration Diagram for the SAD". The skill picks the type, reads that type's recipe and draws it.

## Requirements

- Google Chrome or Chromium, used headless to render each diagram to PNG so Claude can check it visually. On macOS the standard install is found automatically; elsewhere `google-chrome` or `chromium` on the PATH is used, or set `CHROME_PATH`.
- Python 3 for the CoreEA helper library (standard library only).

## What's in it

```
skills/arch-diagram/
  SKILL.md                 routing, design system, icons, procedure
  icons.svg                40 stroke glyphs; vendor components map to concept glyphs
  references/              one recipe per diagram type, plus c4.md and coreea.md
  scripts/coreea_lib.py    CoreEA view helpers and validate(model)
  scripts/model_schema.json
  scripts/example/         a small model and the view built from it
```

## Design rules

- One accent colour for the one or two things the reader should see first; no shadows or gradients.
- Arrows are orthogonal, labelled, and stop short of their target.
- Vendor logos are never drawn. AWS, Azure and GCP components map to concept glyphs through `references/icon-aliases.md`.
- Every diagram is rendered and checked for clipped text, arrowheads piercing boxes and labels crossing lines before it is handed over.
- The theme is a small set of tokens. Override it with your own brand colours.

## CoreEA in practice

Build the object model first (objects with type, id, name and status; relationships with a CoreEA verb), validate it, then draw each view from it. `validate()` reports every problem at once: duplicate ids, a prefix that doesn't match its type, a relationship to a missing object, or a verb used between the wrong types. Views refuse to draw an object or edge that isn't in the model. Proposed or unbuilt objects are drawn dashed. See `skills/arch-diagram/scripts/README.md` for a worked example.

## Licence

MIT
