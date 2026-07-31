# fault_engine.py
#
# Combines topology_loader.py (CSV + missing-data inference) with the
# fault-finding logic, and adds a "confidence" field to each fault:
# if the span touches ANY inferred edge, the whole fault is reported
# as lower confidence - because we're not sure that span is real.

from topology_loader import load_pole_registry, infer_missing_topology


def build_children_map(topology):
    children_of = {pid: [] for pid in topology}
    for pid, parent_id in topology.items():
        if parent_id:
            children_of.setdefault(parent_id, []).append(pid)
    return children_of


def collect_dark_descendants(pole_id, pole_state, children_of):
    count = 0
    stack = list(children_of.get(pole_id, []))
    while stack:
        current_id = stack.pop()
        if not pole_state.get(current_id, True):
            count += 1
            stack.extend(children_of.get(current_id, []))
    return count


def find_faults(pole_state, topology, confidence, pole_meta=None, outage_registry=None):
    """
    pole_meta: optional {pole_id: {"dt_id": ..., "feeder_id": ...}} - required
    only if outage_registry is passed, to check scheduled-outage suppression.
    """
    children_of = build_children_map(topology)
    faults = []

    for pole_id, energized in pole_state.items():
        if energized:
            continue

        parent_id = topology.get(pole_id)
        parent_is_live = pole_state.get(parent_id, True) if parent_id else True

        if not parent_is_live:
            continue

        children = children_of.get(pole_id, [])
        children_states = [pole_state.get(c, True) for c in children]
        all_children_live = len(children) > 0 and all(children_states)

        if all_children_live:
            continue  # likely a bad sensor, not a real fault

        # Scheduled outage check: if this pole's DT or feeder is under a
        # published maintenance/load-shedding window right now, this is
        # expected darkness, not a fault - suppress the ticket.
        if outage_registry and pole_meta and pole_id in pole_meta:
            meta = pole_meta[pole_id]
            if outage_registry.is_covered(meta["dt_id"], "dt") or \
               outage_registry.is_covered(meta["feeder_id"], "feeder"):
                continue

        downstream_count = collect_dark_descendants(pole_id, pole_state, children_of)

        # This fault is only as trustworthy as the shakiest edge involved.
        span_confidence = "high" if confidence.get(pole_id) == "known" else "low - inferred topology"

        faults.append({
            "span": f"{parent_id if parent_id else 'TRANSFORMER'} -> {pole_id}",
            "downstream_affected": 1 + downstream_count,
            "confidence": span_confidence,
        })

    return faults


def load_topology_from_csv(csv_path="pole_registry.csv"):
    poles = load_pole_registry(csv_path)
    topology, confidence = infer_missing_topology(poles)
    return topology, confidence
