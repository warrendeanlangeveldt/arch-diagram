# sequence — ordered messages over time

## Recipe
- Canvas 740 × (110 + 34·messages). Lifelines: 3–5 columns, evenly spaced; header = icon 20px + name 11px 600 in a 150×44 slate box; dashed line (`3 4`, line colour) from header bottom to canvas bottom.
- Messages: horizontal arrows top→bottom in time order, 34px vertical rhythm; label 9.5px above each arrow, number badge (accent circle r=8) at the arrow's start.
- Returns/responses: dashed arrow stroke.
- No activation bars — editorial, not UML-strict.

## Skeleton
```svg
<svg viewBox="0 0 740 340" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, 'Helvetica Neue', Arial, sans-serif">
  <defs><marker id="arr" .../></defs>
  <rect x="20" y="16" width="150" height="44" rx="6" fill="#f8fafc" stroke="#94a3b8"/>
  <text x="106" y="42" text-anchor="middle" font-size="11" font-weight="600" fill="#0f172a">ACTOR_NAME</text>
  <line x1="95" y1="60" x2="95" y2="330" stroke="#cbd5e1" stroke-width="1.1" stroke-dasharray="3 4"/>
  <line x1="95" y1="96" x2="368" y2="96" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)"/>
  <text x="231" y="88" text-anchor="middle" font-size="9.5" fill="#475569">1 · MESSAGE_LABEL</text>
</svg>
```

## Pitfalls
- >9 messages: cut. Merge request/ack pairs; a sequence diagram is an argument, not a log.
- Self-calls: small rectangular loop right of the lifeline, label beside.
