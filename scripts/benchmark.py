"""Run from the repository root: py -3.12 scripts/benchmark.py."""
from time import perf_counter

from draft_assistant.heroes import parse_draft
from draft_assistant.scoring import recommend

draft = parse_draft("sf bara ogre silencer | underlord jakiro wd | carry")
started = perf_counter()
for _ in range(1000):
    recommend(draft)
elapsed = perf_counter() - started
print(f"1000 recommendations: {elapsed:.4f}s")
print(f"Average: {elapsed / 1000 * 1000:.3f}ms")
