# ArchiMate 3.2

The Open Group's open modelling language, and the most portable choice. The
model and its views export in the ArchiMate exchange format, which Archi, Sparx
EA, BiZZdesign, BOC ADOIT and MEGA import. OrbusInfinity takes it through its
REST API instead (`exports.md`). Read `ea.md` first for the workflow and View
API.

## Elements

`"metamodel": "archimate"`. All 62 element types of ArchiMate 3.2, by layer
(`ea.py types archimate` prints them with prefixes):

| Layer | Types |
|---|---|
| Strategy | Resource, Capability, Value Stream, Course of Action |
| Business | Business Actor / Role / Collaboration / Interface / Process / Function / Interaction / Event / Service, Business Object, Contract, Representation, Product |
| Application | Application Component / Collaboration / Interface / Function / Interaction / Process / Event / Service, Data Object |
| Technology | Node, Device, System Software, Technology Collaboration / Interface, Path, Communication Network, Technology Function / Process / Interaction / Event / Service, Artifact |
| Physical | Equipment, Facility, Distribution Network, Material |
| Motivation | Stakeholder, Driver, Assessment, Goal, Outcome, Principle, Requirement, Constraint, Meaning, Value |
| Implementation & Migration | Work Package, Deliverable, Implementation Event, Plateau, Gap |
| Other | Location, Grouping, And Junction, Or Junction |

Ids take the type's prefix: `ACMP-01` (Application Component), `BPRC-02`
(Business Process), `NODE-01`, `DOBJ-CASE`.

## Relationships

`composition`, `aggregation`, `assignment`, `realization`, `serving`, `access`,
`influence`, `triggering`, `flow`, `specialization`, `association`.
`validate()` checks every relationship against the ArchiMate 3.2 relationship
table (Appendix B), so a relationship the standard does not allow between two
types fails with the list of the ones it does allow.

Attributes: `access` on access relationships (`read`, `write`, `readwrite`,
`access`; the default draws as write); `modifier` on influence (`+`, `++`, `-`,
`--`, `0`–`10`); `directed` on association. Relationships through one junction
must all be of one type.

ArchiMate has no parent field. Nesting stands for a relationship
(composition, aggregation, assignment, realization or specialization) that
must exist in the model, and the key line names it.

## Notation

Rectangle notation with the type symbol in the top-right corner: square
corners for structure, rounded for behaviour, cut corners for motivation, a
header band on business objects, data objects and contracts (contracts also
have a band near the bottom). Layer colours follow the conventional ArchiMate
palette: business yellow, application blue, technology and physical green,
motivation violet, strategy buff, implementation pink, migration green. The
type is not printed in the box; the symbol and the legend carry it. Pass
`type_labels=True` to `View` for readers new to ArchiMate.

Each relationship draws in its standard style, and the legend shows the ones
used:

| Relationship | Line | Source end | Target end |
|---|---|---|---|
| composition | solid | filled diamond | — |
| aggregation | solid | hollow diamond | — |
| assignment | solid | dot | filled arrow |
| realization | dashed | — | hollow triangle |
| serving | solid | — | open arrow |
| access | dotted | small arrow when read | small arrow when write |
| influence | dashed | — | open arrow |
| triggering | solid | — | filled arrow |
| flow | long dash | — | filled arrow |
| specialization | solid | — | hollow triangle |
| association | solid | — | small arrow when directed |

Lines carry no label by default. Pass `label=(x, y)` to show the relationship's
`name` (a flow's "case events"), an influence modifier, or `label_text`.

## Viewpoints

`View(..., viewpoint="Application Cooperation")` checks the types drawn against
the ArchiMate 3.2 example viewpoints: Organization, Application Structure,
Information Structure, Technology, Layered, Physical, Product, Application
Usage, Technology Usage, Business Process Cooperation, Application Cooperation,
Service Realization, Implementation and Deployment, Stakeholder, Goal
Realization, Requirements Realization, Motivation, Strategy, Capability Map,
Value Stream, Outcome Realization, Resource Map, Project, Migration,
Implementation and Migration. `ea.py viewpoints archimate "<name>"` lists the
types each allows. The viewpoint name goes into the exchange file.

| Request | Viewpoint | Layout recipe |
|---|---|---|
| Solution overview, SAD context | Layered | rows top to bottom: business, application, technology |
| How applications talk | Application Cooperation | `integration`: subject left, partners right |
| What runs where | Implementation and Deployment / Technology | `deployment`: location → node containers |
| Who uses which application | Application Usage | actors top, applications below |
| Capability map | Capability Map | capability grid nested by composition |
| Why we are doing this | Motivation / Goal Realization | columns: drivers → goals → outcomes → requirements |
| Roadmap | Migration / Implementation and Migration | plateaus left to right, gaps between |

## Example

`scripts/examples/archimate/layered.py` draws a Layered view of a small model
and writes the exchange file with the view's diagram in it:

![](../scripts/examples/archimate/out/LAYERED.png)

## Pitfalls

- A nested element without the composition, aggregation or assignment
  relationship behind it says something the model doesn't. Add the
  relationship or move the box out.
- Junctions need a type-consistent set of relationships, and they draw with
  `junction()`, not `node()`.
- Interfaces may be drawn as pills (`pill()`) on the component that composes
  them; serving lines then start at the pill.
