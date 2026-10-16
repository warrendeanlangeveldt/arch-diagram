# Getting the model into the person's EA tool

Every export reads the same validated `model.json`, so ids, names and types
match the diagrams.

| Target | Format | How |
|---|---|---|
| Archi, Sparx EA, BiZZdesign, BOC ADOIT, MEGA and other ArchiMate tools | ArchiMate exchange format (Open Group 3.1 schema, used for 3.2) | `write_archimate_xml(model, path, views=[v1, v2])` from the view script, or `ea.py export model.json --format archimate` for the model without diagrams |
| Camunda Modeler, bpmn.io, Signavio, Bizagi, ARIS and other BPMN tools | BPMN 2.0 XML with diagram interchange | `write_bpmn_xml(model, path, view=v)`, or `ea.py export model.json --format bpmn` without layout |
| OrbusInfinity | REST API import payload (any framework; CoreEA maps most directly) | `ea.py orbus …`, below |
| Essential, spreadsheets, any repository with a CSV import | catalogue CSVs | `ea.py export model.json --format csv` |

## ArchiMate exchange file

Elements, relationships (with access type, influence modifier and association
direction), and properties for status, owner, source reference, category,
document section and every key in `properties`. Each view passed in becomes a
diagram with its viewpoint, node positions and sizes, nesting (a node drawn
inside a container is a child node) and connection bendpoints, so the views
open in the target tool laid out as drawn. Relationships shown by nesting have
no connection, which is how ArchiMate tools draw them too. The file validates
against the Open Group XSD (`tests/test_exports.py` checks it).

## BPMN XML

One process per pool, a collaboration with the participants and message
flows, lane sets with their flow-node references, event definitions, boundary
events, default and conditional flows, data objects, data stores and their
associations, annotations, and BPMNDI shapes and edges from the view. It
validates against the OMG BPMN 2.0 XSD.

## Catalogue CSVs

`<name>.objects.csv` (id, type, framework class, layer, name, description,
status, owner, ref, parent, category, then one column per `properties` key) and
`<name>.relationships.csv` (id, from and to with names and types,
relationship, framework class, name, note, crud, access). For Essential the
`class` columns carry the meta-class and slot or relation class names, ready to
map in Essential's import utility.

## OrbusInfinity

OrbusInfinity publishes an OData REST API: `POST /odata/Objects`,
`POST /odata/Relationships`, `PATCH` on both, and paged `GET`s, with an OAuth 2
bearer token and a limit of 100 calls a minute. Object and relationship type
ids belong to each tenant, so the import runs in three steps.

```bash
export ORBUS_API_URL=https://<tenant>-api.orbusinfinity.com
export ORBUS_TOKEN=<OAuth 2 access token for the API>

# 1. Read the tenant's types and objects; draft the mapping; match existing objects
python3 scripts/ea.py orbus discover --model model.json --map-out orbus-map.json \
        --types-out orbus-types.json --ledger orbus-ledger.json

# 2. Fill in any empty ids in orbus-map.json (orbus-types.json lists what exists), then
python3 scripts/ea.py orbus plan model.json --map orbus-map.json --ledger orbus-ledger.json

# 3. Load it
python3 scripts/ea.py orbus push out/<name>.orbus.json --map orbus-map.json --ledger orbus-ledger.json
```

The mapping file:

```json
{"apiUrl": "https://<tenant>-api.orbusinfinity.com",
 "modelId": "<guid of the Orbus model to load into>",
 "objectTypes": {"Application Component": "<guid>", "Business Process": "<guid>"},
 "relationshipTypes": {"serving": "<guid>",
                       "realization": {"id": "<guid>", "pairId": "<guid>", "reverse": false}},
 "attributes": {"description": "Description", "status": "Lifecycle Status",
                "classification": "Classification", "name": "Label"}}
```

`discover` matches tenant types to model types by name, ignoring case and
spaces, and leaves the rest empty. It only sees types that already have at
least one object or relationship in the tenant, so a new tenant needs its type
ids copied from OrbusInfinity's metamodel settings. `reverse` swaps lead and
member for a relationship type that Orbus defines the other way round.
`attributes` maps model fields and `properties` keys to Orbus attribute names;
anything unmapped is left out of the payload.

`plan` fails listing every unmapped type at once. Its output,
`<name>.orbus.json`, is the import payload: every request in order, objects
first, then relationships with `{{model-id}}` placeholders for GUIDs that only
exist once the objects are created. It's readable on its own, so the person can
review it, or hand it to whoever owns the repository, before anything is
written.

`push` runs the payload with throttling (under 100 calls a minute, retrying
429s with their Retry-After), records each new GUID in the ledger after every
call, and fills placeholders from it. An interrupted push resumes without
duplicating anything. Run with the ledger, a second `plan` turns into PATCH
updates, so the model can be maintained in `model.json` and re-pushed.
`discover --ledger` seeds the ledger with objects that already exist in the
tenant (same name and mapped type, exactly one match), so the first push
updates those instead of adding duplicates.

Before a first push into a production repository, push into a sandbox model
(a different `modelId`) and check the result in OrbusInfinity. The adapter has
been tested against a local server that implements the published API contract,
but not against a live tenant, so the field names in Orbus's responses are read
case-insensitively and a response without the expected id stops the push with
the response shown.

Never put the token in the mapping file or commit the ledger alongside
credentials. The ledger holds only model ids and Orbus GUIDs.
