"""Cluster-first selection with separate page and prepared-history budgets."""
import math
import random
import statistics

DEFAULT_PAGE_BUDGET = 128
DEFAULT_RECORD_BUDGET = 100_000


def select_pages(clusters, page_types, budget, max_run_length=5,
                 max_runs_per_cluster=3, forced_pages=(), coverage_types=None,
                 rng=None, page_records=None, record_budget=None):
    """Cover clusters, missing types, history-count extremes, then page runs.

    Counts are prepared history records, not live objects. None disables the
    record cap and preserves the page-only policy. Mandatory perf pages remain
    the only exception to either cap; all excesses and omissions are reported.
    """
    for name, value in (('page', budget), ('record', record_budget)):
        if value is None and name == 'record':
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f'{name} budget must be a nonnegative integer')
    if max_run_length < 1 or max_runs_per_cluster < 1:
        raise ValueError('page-run limits must be positive')
    rng = random if rng is None else rng
    clusters = {c: sorted(set(pages)) for c, pages in clusters.items() if len(pages)}
    eligible = {page for pages in clusters.values() for page in pages}
    if record_budget is not None and page_records is None:
        raise ValueError('record budget requires per-page history counts')
    costs = {page: page_records[page] if page_records is not None else 0 for page in eligible}
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in costs.values()):
        raise ValueError('history counts must be nonnegative integers')
    selected = eligible.intersection(forced_pages)
    forced = set(selected)
    records = sum(costs[p] for p in selected)
    forced_records = records
    available_types = set().union(*(page_types.get(page, set()) for page in eligible))
    if coverage_types is not None:
        available_types.intersection_update(coverage_types)
    covered_types = set().union(*(page_types.get(page, set()) for page in selected))

    def fits(page, reserve=0):
        return (page not in selected and len(selected) < budget and
                (record_budget is None or records + costs[page] + reserve <= record_budget))

    def add(page):
        nonlocal records
        if not fits(page):
            return False
        selected.add(page)
        records += costs[page]
        covered_types.update(page_types.get(page, ()))
        return True

    def choose(pages, reserve=0):
        candidates = [p for p in pages if fits(p, reserve)]
        if not candidates:
            return
        if record_budget is not None:
            # Prefer an ordinary history size, not the cheapest page. Reserve
            # enough for other clusters when complete cluster coverage fits.
            target = math.log1p(statistics.median(costs[p] for p in pages))
            distances = {p: abs(math.log1p(costs[p]) - target) for p in candidates}
            closest = min(distances.values())
            candidates = [p for p in candidates if distances[p] == closest]
        add(rng.choice(candidates))

    order = list(clusters)
    rng.shuffle(order)
    uncovered = [c for c in order if not selected.intersection(clusters[c])]
    minima = {c: min(costs[p] for p in clusters[c]) for c in uncovered}
    remaining_min = sum(minima.values())
    can_cover = (len(selected) + len(uncovered) <= budget and
                 (record_budget is None or records + remaining_min <= record_budget))
    for cluster in uncovered:
        remaining_min -= minima[cluster]
        choose(clusters[cluster], remaining_min if can_cover and record_budget is not None else 0)
    after_clusters = len(selected)

    missing = sorted(available_types - covered_types)
    rng.shuffle(missing)
    if missing and len(selected) < budget:
        type_pages = {tp: [] for tp in missing}
        for page in sorted(eligible):
            for tp in page_types.get(page, ()):
                if tp in type_pages:
                    type_pages[tp].append(page)
        for tp in missing:
            if tp not in covered_types:
                choose(type_pages[tp])
    after_types = len(selected)

    # A >=4x within-cluster range is worth showing if coverage leaves capacity.
    # This does not claim to measure peak live density or identify churn.
    ranges = {}
    if record_budget is not None:
        for cluster in order:
            pages = clusters[cluster]
            low, high = min(costs[p] for p in pages), max(costs[p] for p in pages)
            if high >= 4 * max(1, low):
                ranges[cluster] = (low, high)
                for target in (low, high):
                    if not any(p in selected and costs[p] == target for p in pages):
                        choose([p for p in pages if costs[p] == target])
    after_ranges = len(selected)

    for cluster in order:
        if len(selected) >= budget:
            break
        pages = clusters[cluster]
        if len(pages) <= max_runs_per_cluster * max_run_length:
            for page in pages:
                add(page)
                if len(selected) >= budget:
                    break
        else:
            for _ in range(max_runs_per_cluster):
                start = rng.randrange(len(pages))
                for pos in range(start, min(start + max_run_length, len(pages))):
                    if pos > start and pages[pos] != pages[pos - 1] + 1:
                        break
                    add(pages[pos])
                    if len(selected) >= budget:
                        break
                if len(selected) >= budget:
                    break

    omitted = [int(c) for c, pages in clusters.items() if not selected.intersection(pages)]
    missing_ranges = [
        dict(cluster=int(c), end=end, records=n)
        for c, bounds in ranges.items() for end, n in zip(('low', 'high'), bounds)
        if not any(p in selected and costs[p] == n for p in clusters[c])]
    return selected, dict(
        policy='cluster-first-type-coverage' if record_budget is None else 'cluster-first-history-budget',
        page_budget=budget, record_budget=record_budget,
        selected_pages=len(selected), selected_records=records if page_records is not None else None,
        mandatory_perf_pages=len(forced), mandatory_perf_records=forced_records,
        perf_budget_excess=max(0, len(forced)-budget),
        perf_record_budget_excess=max(0, forced_records-record_budget) if record_budget is not None else 0,
        pages_after_cluster_pass=after_clusters, pages_after_type_pass=after_types,
        pages_after_history_range_pass=after_ranges,
        available_clusters=len(clusters), represented_clusters=len(clusters)-len(omitted),
        omitted_clusters=sorted(omitted), eligible_types=sorted(available_types),
        omitted_types=sorted(available_types-covered_types),
        history_range_clusters=len(ranges), omitted_history_extremes=missing_ranges,
        oversized_pages=sum(n > record_budget for n in costs.values()) if record_budget is not None else 0)
