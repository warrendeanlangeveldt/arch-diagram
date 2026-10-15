# phases — roadmaps, work packages, rollouts

## Recipe
- Canvas 740 × (rows · 56 + 80). Axis: 1.3px line at bottom, tick labels 9px muted (weeks/months/WPs).
- Phase bars: rounded spans (height 32, rx 6, accent-fill + accent stroke 1.2), label 10.5px 600 inside-left (x+12); bar x/width proportional to the axis scale.
- Parallel workstreams: one bar row each, row labels in a 110px left gutter.
- Milestones: accent diamonds (12×12 rotated rect) ON the axis, label 9px below.

## Skeleton
```svg
<line x1="130" y1="200" x2="720" y2="200" stroke="#94a3b8" stroke-width="1.3"/>
<rect x="130" y="60" width="180" height="32" rx="6" fill="#f0fdfa" stroke="#0d9488" stroke-width="1.2"/>
<text x="142" y="80" font-size="10.5" font-weight="600" fill="#0f172a">PHASE_NAME</text>
<rect x="306" y="194" width="12" height="12" transform="rotate(45 312 200)" fill="#0d9488"/>
<text x="312" y="222" text-anchor="middle" font-size="9" fill="#64748b">MILESTONE</text>
```

## Pitfalls
- Don't fake precision: if dates are soft, label ticks by phase number, not calendar weeks.
