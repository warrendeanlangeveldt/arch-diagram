# deploy-path — CI/CD and trust chain

## Recipe
- Canvas 740 × 160. Left→right: source (slate box) → auth arrow → role/mechanism (accent box) → fan-out to target boxes (stacked right, slate).
- Constraints ON the arrows and in box sub-lines ("main branch only", "2 repos only", "one cluster"). The diagram IS the least-privilege argument.
- Fan-out elbows: from role right edge at ±12px offsets, via x≈520, into each target's left centre.

## Skeleton
See the WP7 brief's deploy diagram — boxes 160–180×56–64, arrow labels split into two 8.5px lines when >16 chars so they clear the next box.

## Pitfalls
- The auth label between two boxes must fit the gap: measure (0.52 × px × chars) or stack two lines.
