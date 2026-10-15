# swimlane — who does what across parties

## Recipe
- Canvas 740 × (lanes · 90 + 40). One horizontal lane per actor (max 4): left gutter cell 110px wide with actor name 10.5px 600 UPPERCASE + optional icon; lane bands alternate band-a/band-b full width.
- Action boxes 150–170×48 sit in their actor's lane, time flowing left→right on a shared x-grid so simultaneous things align.
- Handoffs: vertical (or elbowed) arrows crossing lane boundaries at the handoff moment, labelled with the artefact ("portal URL", "print order").

## Skeleton
```svg
<rect x="0" y="40" width="740" height="90" fill="#f8fafc"/>
<rect x="0" y="130" width="740" height="90" fill="#eef2f7"/>
<text x="16" y="90" font-size="10.5" font-weight="600" fill="#64748b">PARTNER</text>
<rect x="130" y="60" width="160" height="48" rx="6" fill="#ffffff" stroke="#94a3b8" stroke-width="1.3"/>
<line x1="210" y1="108" x2="210" y2="148" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)"/>
```

## Pitfalls
- Keep one row of boxes per lane; stacked boxes in a lane mean the lane should split.
- The x-grid is the timeline — don't place a later action left of an earlier one.
