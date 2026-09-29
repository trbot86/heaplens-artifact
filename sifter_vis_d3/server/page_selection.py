"""Bounded cluster-first representative selection for the camera-ready branch."""
import random


def select_pages(clusters, page_types, budget, max_run_length=5,
                 max_runs_per_cluster=3, forced_pages=(), coverage_types=None,
                 rng=None):
    """Cover clusters, then missing types, then add consecutive page runs.

    Types refer to the prepared page histories, not a single selected time.
    Perf-directed pages remain mandatory for compatibility. They count toward
    the budget, but are retained when they alone exceed it; metadata reports
    that exception. No ordinary sampling pass can exceed the budget.
    """
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ValueError('page budget must be a nonnegative integer')
    if max_run_length < 1 or max_runs_per_cluster < 1:
        raise ValueError('page-run limits must be positive')
    rng = random if rng is None else rng
    clusters = {c: sorted(set(pages)) for c, pages in clusters.items() if len(pages)}
    eligible = {page for pages in clusters.values() for page in pages}
    selected = eligible.intersection(forced_pages)
    forced = set(selected)
    available_types = set().union(*(page_types.get(page, set()) for page in eligible))
    if coverage_types is not None:
        available_types.intersection_update(coverage_types)
    covered_types = set().union(*(page_types.get(page, set()) for page in selected))

    def add(page):
        if page in selected or len(selected) >= budget:
            return False
        selected.add(page)
        covered_types.update(page_types.get(page, ()))
        return True

    order = list(clusters)
    rng.shuffle(order)
    for cluster in order:
        if len(selected) >= budget:
            break
        if not selected.intersection(clusters[cluster]):
            add(rng.choice(clusters[cluster]))
    after_clusters = len(selected)

    # A page picked for one missing type can also cover other missing types.
    missing = sorted(available_types - covered_types)
    rng.shuffle(missing)
    if missing and len(selected) < budget:
        type_pages = {tp: [] for tp in missing}
        for page in sorted(eligible):
            for tp in page_types.get(page, ()):
                if tp in type_pages:
                    type_pages[tp].append(page)
        for tp in missing:
            if len(selected) >= budget:
                break
            if tp not in covered_types:
                add(rng.choice(type_pages[tp]))
    after_types = len(selected)

    # Retain the existing run policy as a best-effort use of spare slots.
    # Check after each distinct addition, rather than only between clusters.
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
    return selected, dict(policy='cluster-first-type-coverage', page_budget=budget,
        selected_pages=len(selected), mandatory_perf_pages=len(forced),
        perf_budget_excess=max(0, len(forced)-budget),
        pages_after_cluster_pass=after_clusters, pages_after_type_pass=after_types,
        available_clusters=len(clusters), represented_clusters=len(clusters)-len(omitted),
        omitted_clusters=sorted(omitted), eligible_types=sorted(available_types),
        omitted_types=sorted(available_types-covered_types))
