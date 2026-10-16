# Icons: platform packs and generic glyphs

Two sources, chosen per component:

- Platform packs: the official AWS Architecture Icons, Azure Public Service
  Icons and Google Cloud icons. Use them when the diagram shows a component
  running on that platform, so readers see the icon they know from the
  console.
- Generic glyphs (`icons.svg`, 64 stroke glyphs): everything that isn't a
  platform service (people, browsers, mobile apps, SaaS products, on-premises
  kit, open-source software such as Kafka or Postgres) and any platform
  component whose pack hasn't been fetched.

Vendor product logos (Salesforce, Kafka, React) are never drawn; those map to
the nearest generic glyph.

## Fetching the platform packs

The vendors allow their icons in architecture diagrams and documentation but
not redistribution in a tool, so the plugin doesn't ship them. Each person
fetches them once, after reading the vendor's terms:

```bash
python3 scripts/icons.py status
python3 scripts/icons.py fetch aws --accept-terms      # also: azure, gcp, all
```

`fetch` reads the vendor's icon page for the current download link
(aws.amazon.com/architecture/icons, learn.microsoft.com/azure/architecture/icons,
cloud.google.com/icons), downloads the pack and indexes the SVGs into
`~/.cache/arch-diagram/icons` (`ARCH_DIAGRAM_ICONS` overrides). Ask the person
before passing `--accept-terms`; it records that they agreed. Behind a proxy, or
when a page has changed, download the zip by hand and run
`icons.py fetch aws --from-zip FILE --accept-terms`.

What gets indexed: AWS service icons (48 px set), resource icons (light
variants), group icons (`group-aws-cloud`, `group-region`,
`group-virtual-private-cloud-vpc`, `group-private-subnet` …) and category icons;
every Azure service icon; Google Cloud product, core-product and category icons.

## Resolving a component to an icon

```bash
python3 scripts/icons.py resolve "S3"                  # aws:amazon-simple-storage-service
python3 scripts/icons.py resolve "Cosmos DB"           # azure:azure-cosmos-db
python3 scripts/icons.py resolve "Kafka"               # generic:stream
python3 scripts/icons.py resolve Postgres --platform azure   # azure:sql-database
python3 scripts/icons.py search "kinesis video"        # browse a pack
python3 scripts/icons.py sheet S3 Lambda "Entra ID" users --out /tmp/icons   # look before using
```

Order: an explicit `pack:slug` reference; then `scripts/icon_aliases.json`,
where platform terms ("S3", "Cosmos DB", "Cloud Pub/Sub") win over neutral ones
("object storage", "Kafka", "pub/sub"); then a close name match in the
fetched packs; then a generic glyph of that name. A platform term whose pack
isn't fetched falls back to its concept's generic glyph, and `resolve` says so.
Add a term to `icon_aliases.json` rather than hard-coding a slug in a diagram.

## Using icons

In EA views: `node(..., icon="S3")`, `container(..., icon="EKS")`,
`frame(..., icon="aws:group-virtual-private-cloud-vpc")`.

In hand-laid SVG (the house recipes and C4):

```bash
python3 scripts/icons.py svg "Lambda" --x 34 --y 79 --size 20
```

prints a fragment to paste. Generic glyphs come as
`<g transform="translate(x y) scale(0.833)">` in the node's stroke colour.
Vendor icons come as a nested `<svg>` with their own colours and every internal
id prefixed, so two copies of one icon never collide. In a 58-high box the icon
sits at (x + 14, y + 19) and the text centres at boxX + 34 + (w − 34) / 2.

Platform icons carry their own colour, which is the one exception to the
one-accent rule. Use one family per diagram where possible, and don't mix two
platforms' icons for the same concept.

## Generic glyphs

| Glyph | Use for |
|---|---|
| `user-browser`, `mobile`, `laptop` | web, mobile and desktop clients |
| `identity`, `users` | a person, a group of people |
| `building`, `datacenter`, `cloud`, `globe` | office or site, on-premises data centre, a cloud, a region |
| `gateway`, `waf`, `firewall`, `cdn`, `dns`, `network`, `lock` | edge and network |
| `api`, `server`, `container`, `orchestrator`, `compute`, `function` | services and compute |
| `database`, `cache`, `bucket`, `files`, `warehouse`, `backup` | storage and data |
| `queue`, `stream`, `etl`, `workflow`, `scheduler`, `webhook`, `realtime` | messaging and integration |
| `secrets`, `key`, `certificate` | security material |
| `logs`, `metrics`, `alert`, `test` | operations and quality |
| `ai`, `bot`, `search`, `rules` | AI, agents, search, rules engines |
| `notify`, `email`, `sms`, `payment`, `saas`, `plug` | outbound channels and third parties |
| `pipeline`, `git`, `terminal` | delivery and tooling |
| `document`, `print`, `image`, `video`, `font`, `chart`, `map`, `cube`, `iot` | content, media and devices |

BaaS platforms (Supabase, Firebase) compose from `database` + `bucket` +
`identity` as separate nodes, or one `database` node labelled with the platform
name when it plays a single role.
