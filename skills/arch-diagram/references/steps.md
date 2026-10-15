# steps — numbered procedures, onboarding, "step graph"

## Recipe
- Canvas 740 × 150 (one row). Badges: accent circles r=14 at y=48, evenly spaced (5 steps → x = 72 + 140·i); number 12px 700 white, y+4.5.
- Connectors: 1.3px `#cbd5e1` lines between badge edges (start/end 14px clear of centres).
- Under each badge: title 11px 600 ink at y=86; ONE sub-line 9px body at y=101.
- 4–7 steps per row; more → second row at y+=110, connector elbows down at the row end.

## Skeleton
```svg
<circle cx="72" cy="48" r="14" fill="#0d9488"/>
<text x="72" y="52.5" text-anchor="middle" font-size="12" font-weight="700" fill="#ffffff">1</text>
<text x="72" y="86" text-anchor="middle" font-size="11" font-weight="600" fill="#0f172a">STEP_TITLE</text>
<text x="72" y="101" text-anchor="middle" font-size="9" fill="#475569">STEP_SUB</text>
<line x1="86" y1="48" x2="198" y2="48" stroke="#cbd5e1" stroke-width="1.3"/>
```

## Pitfalls
- Sub-lines longer than ~26 chars collide with neighbours at 140px spacing — trim the copy, don't shrink the font.
