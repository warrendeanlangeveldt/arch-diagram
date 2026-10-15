# deployment — runtime infra in a cloud account

Nested trust frames, zone bands, icon boxes. The WP7/Azure shape.

## Recipe
- Canvas 740 × 520–570. Internet pill (130×36, rx 18) top-left-ish, arrow down into the entry box.
- Account frame: solid `frame` stroke, rx 10, label "YOUR AWS ACCOUNT · region" 10.5px UPPERCASE muted, inside top-left.
- Network frame (VPC/VNet): dashed `5 4` accent, rx 8, inside account, ~62% of width; regional/managed services live in a right column OUTSIDE it (heading "REGIONAL SERVICES").
- Zone bands inside network: public band `band-a`, private band `band-b`, rx 6, label 9.5px UPPERCASE.
- Entry box (LB/gateway) full-band width ×52; service boxes 180–185×58 side-by-side; data stores full-width ×58–60 in the private band.
- Accent stroke+fill for the subject's own services; slate+white for managed/data services.
- Every arrow states its constraint ("SG: ingress from ALB only", ":5432 · task SG only", "task role · no static keys").

## Skeleton
```svg
<svg viewBox="0 0 740 530" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, 'Helvetica Neue', Arial, sans-serif">
  <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9 z" fill="#475569"/></marker></defs>
  <rect x="75" y="16" width="130" height="36" rx="18" fill="#f1f5f9" stroke="#94a3b8"/>
  <text x="140" y="39" text-anchor="middle" font-size="12" font-weight="600" fill="#0f172a">Internet</text>
  <rect x="20" y="90" width="700" height="420" rx="10" fill="none" stroke="#94a3b8" stroke-width="1.2"/>
  <text x="36" y="112" font-size="10.5" font-weight="600" fill="#64748b">ACCOUNT_LABEL</text>
  <rect x="40" y="122" width="450" height="368" rx="8" fill="none" stroke="#0d9488" stroke-dasharray="5 4" stroke-width="1.2"/>
  <text x="54" y="141" font-size="10" font-weight="600" fill="#0d9488">NETWORK_LABEL</text>
  <!-- public band + entry box + service boxes; private band + data box; right column x=515 w=185 -->
  <line x1="140" y1="52" x2="140" y2="174" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)"/>
</svg>
```

## Pitfalls
- Right-column elbow arrows: route via x≈485–495 between the network frame edge and the column; stagger elbow x when two arrows share the edge.
- Keep ≥12px padding between a frame and its children; bands need 26px headroom for their label.
