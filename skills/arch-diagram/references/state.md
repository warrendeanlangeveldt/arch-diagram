# state — lifecycles, status machines

## Recipe
- Canvas 740 × 200–260. States as pills: height 36, rx 18, width = text + 32; 11px 600 labels.
- Happy path on one horizontal axis, left→right, 48–64px gaps; start state accent fill+stroke, terminal state accent stroke double (stroke-width 2.2), intermediates slate.
- Transitions: labelled arrows 9px ("approve", "reject · returns to client"); exception/backward transitions curve BELOW the axis (`path` with a single smooth bow, arrowhead at target bottom).

## Skeleton
```svg
<rect x="20" y="60" width="108" height="36" rx="18" fill="#f0fdfa" stroke="#0d9488" stroke-width="1.5"/>
<text x="74" y="83" text-anchor="middle" font-size="11" font-weight="600" fill="#0f172a">submitted</text>
<line x1="130" y1="78" x2="174" y2="78" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)"/>
<text x="152" y="70" text-anchor="middle" font-size="9" fill="#64748b">review</text>
<path d="M 300 96 C 260 140 180 140 140 100" fill="none" stroke="#475569" stroke-width="1.3" stroke-dasharray="4 3" marker-end="url(#arr)"/>
```

## Pitfalls
- More than 7 states → split into two diagrams (e.g. pre-print and fulfilment).
- Backward curves must clear the pills by ≥16px at the bow's lowest point.
