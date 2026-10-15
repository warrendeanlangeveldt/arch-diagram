# integration — two platforms and their contract

## Recipe
- Canvas 740 × 380–440. Two frames side by side (each ~330 wide), one per platform; subject platform gets the accent dashed frame, the partner solid slate.
- The ~80px gap between frames is the contract lane: all cross-platform arrows live there, each labelled protocol + auth ("REST · X-API-Key", "redirect · signed token").
- Inside each frame only the components that touch the contract (2–4 boxes); internal detail belongs in that platform's own deployment diagram.
- Shared artefacts (webhook endpoints, files, queues) sit ON the gap's vertical centre line as small slate boxes.

## Skeleton
```svg
<svg viewBox="0 0 740 400" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, 'Helvetica Neue', Arial, sans-serif">
  <defs><marker id="arr" .../></defs>
  <rect x="20" y="40" width="300" height="330" rx="8" fill="none" stroke="#0d9488" stroke-dasharray="5 4" stroke-width="1.2"/>
  <text x="34" y="60" font-size="10" font-weight="600" fill="#0d9488">OUR_PLATFORM</text>
  <rect x="420" y="40" width="300" height="330" rx="8" fill="none" stroke="#94a3b8" stroke-width="1.2"/>
  <text x="434" y="60" font-size="10.5" font-weight="600" fill="#64748b">PARTNER_PLATFORM</text>
  <!-- contract arrows across x 320..420, labels 9px above each -->
</svg>
```

## Pitfalls
- Number the contract arrows if order matters; otherwise group request/response pairs.
- Auth mechanism goes on the arrow, not in a footnote.
