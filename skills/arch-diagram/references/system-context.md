# system-context — actors, the system, externals

C4-level-1 flavour: one accent box, no internals.

## Recipe
- Canvas 740 × 300–360. The system: one large accent box (260–300 × 100–120) centred, title 13px + 2 sub-lines.
- Actors left column (user-browser/mobile/identity icons above 11px labels, no boxes — icon + text only).
- External systems right column: slate boxes 185×58 with icons.
- Edges: labelled with verb + protocol ("orders boards · HTTPS", "reads jobs · API key"). Max 6–7 edges; merge minor ones.

## Skeleton
```svg
<svg viewBox="0 0 740 320" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, 'Helvetica Neue', Arial, sans-serif">
  <defs><marker id="arr" .../></defs>
  <!-- actor: icon 28px at (60,90), label below -->
  <rect x="230" y="100" width="280" height="110" rx="8" fill="#f0fdfa" stroke="#0d9488" stroke-width="1.6"/>
  <text x="370" y="140" text-anchor="middle" font-size="13" font-weight="700" fill="#0f172a">SYSTEM_NAME</text>
  <text x="370" y="158" text-anchor="middle" font-size="9.5" fill="#475569">ONE_LINE_PURPOSE</text>
  <!-- externals: slate boxes at x=555 -->
</svg>
```

## Pitfalls
- Resist internals — if you're drawing the system's parts, you want `deployment` or `data-flow` instead.
- Edge labels sit above their line, never crossing the system box.
