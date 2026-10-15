# data-flow — pipelines, ETL, request paths

## Recipe
- Canvas 740 × 160–220. Single left→right lane of icon boxes (150–170 × 58), gap 40–56px.
- Numbered badges: accent circle r=10 at each hop's top-left corner (box x+0, y-10), number 10px white 700.
- Arrows between boxes carry the payload name 9px ("IDML file", "zone signals").
- A branch gets ONE diamond (52×52 rotated square) with yes/no labels; more than one branch → this is a flowchart, simplify or split.

## Skeleton
```svg
<svg viewBox="0 0 740 180" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, 'Helvetica Neue', Arial, sans-serif">
  <defs><marker id="arr" .../></defs>
  <rect x="20" y="60" width="160" height="58" rx="6" fill="#f0fdfa" stroke="#0d9488" stroke-width="1.4"/>
  <circle cx="20" cy="60" r="10" fill="#0d9488"/><text x="20" y="63.5" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">1</text>
  <!-- icon at (34, 79); title centre x = 20+34+(160-34)/2 -->
  <line x1="182" y1="89" x2="218" y2="89" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)"/>
  <text x="200" y="81" text-anchor="middle" font-size="9" fill="#64748b">PAYLOAD</text>
</svg>
```

## Pitfalls
- 4 boxes fit at 170w; 5+ → shrink to 150w or wrap to a second row (connector elbows down at the break).
