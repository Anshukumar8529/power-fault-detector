# telemetry_ingest.py
#
# Step 2: Real telemetry format.
#
# Devices don't hand us a clean "pole is dark" list. They send a STREAM of
# messages like the ones below, and messages can arrive duplicated or
# out of order. We have to reduce that stream down to "what is the CURRENT
# state of each pole" before we can even run fault detection.

# ---- Raw telemetry stream (this is what devices actually send) ----
# Notice: duplicates, out-of-order arrival, and a stale retry.

telemetry_stream = [
    {"device_id": "D-0001", "pole_id": "P-1", "event": "heartbeat",
     "energized": True, "ts": "2026-07-29T02:10:00Z", "seq": 100},

    {"device_id": "D-0004", "pole_id": "P-4", "event": "power_lost",
     "energized": False, "ts": "2026-07-29T02:14:07Z", "seq": 55},

    # duplicate of the same message (at-least-once delivery) - must be ignored
    {"device_id": "D-0004", "pole_id": "P-4", "event": "power_lost",
     "energized": False, "ts": "2026-07-29T02:14:07Z", "seq": 55},

    {"device_id": "D-0006", "pole_id": "P-6", "event": "power_lost",
     "energized": False, "ts": "2026-07-29T02:14:12Z", "seq": 30},

    # a STALE retry that arrives late, with a lower seq than what we already
    # have for this device - must NOT override the newer state
    {"device_id": "D-0004", "pole_id": "P-4", "event": "heartbeat",
     "energized": True, "ts": "2026-07-29T02:00:00Z", "seq": 40},

    {"device_id": "D-0002", "pole_id": "P-2", "event": "heartbeat",
     "energized": True, "ts": "2026-07-29T02:10:05Z", "seq": 101},

    {"device_id": "D-0003", "pole_id": "P-3", "event": "heartbeat",
     "energized": True, "ts": "2026-07-29T02:10:03Z", "seq": 102},

    {"device_id": "D-0005", "pole_id": "P-5", "event": "heartbeat",
     "energized": True, "ts": "2026-07-29T02:10:04Z", "seq": 60},
]

# ---- Topology (same as before - this normally comes from the pole registry CSV) ----

topology = {
    "P-1": None,
    "P-2": "P-1",
    "P-3": "P-2",
    "P-4": "P-3",
    "P-5": "P-3",
    "P-6": "P-5",
}


def reduce_telemetry_to_pole_states(stream):
    """
    Turn a raw, messy telemetry stream into a clean {pole_id: energized}
    snapshot. Rule: for each device, only the message with the HIGHEST seq
    number wins - seq is the one reliable ordering signal we have (ts is not,
    because of clock skew).
    """
    latest_seq_by_device = {}   # device_id -> highest seq seen so far
    pole_state = {}             # pole_id -> current energized state

    for msg in stream:
        device_id = msg["device_id"]
        pole_id = msg["pole_id"]
        seq = msg["seq"]

        best_seq_so_far = latest_seq_by_device.get(device_id, -1)

        if seq <= best_seq_so_far:
            # This message is a duplicate, or an old stale retry. Ignore it.
            print(f"Ignoring stale/duplicate message from {device_id} (seq {seq} <= {best_seq_so_far})")
            continue

        latest_seq_by_device[device_id] = seq
        pole_state[pole_id] = msg["energized"]

    return pole_state


# ---- Reuse the fault-finding logic from step 1, now fed by real pole_state ----

def build_lookups(topology):
    children_of = {pid: [] for pid in topology}
    for pid, parent_id in topology.items():
        if parent_id:
            children_of[parent_id].append(pid)
    return children_of


def collect_dark_descendants(pole_id, pole_state, children_of):
    count = 0
    stack = list(children_of[pole_id])
    while stack:
        current_id = stack.pop()
        if not pole_state.get(current_id, True):  # unknown state -> assume live
            count += 1
            stack.extend(children_of[current_id])
    return count


def find_faults(pole_state, topology):
    children_of = build_lookups(topology)
    faults = []

    for pole_id, energized in pole_state.items():
        if energized:
            continue

        parent_id = topology[pole_id]
        parent_is_live = pole_state.get(parent_id, True) if parent_id else True

        if not parent_is_live:
            continue

        children = children_of[pole_id]
        children_states = [pole_state.get(c, True) for c in children]
        all_children_live = len(children) > 0 and all(children_states)

        if all_children_live:
            print(f"Ignoring {pole_id}: looks like a bad sensor, not a fault")
            continue

        downstream_count = collect_dark_descendants(pole_id, pole_state, children_of)
        faults.append({
            "span": f"{parent_id if parent_id else 'TRANSFORMER'} -> {pole_id}",
            "downstream_affected": 1 + downstream_count,
        })

    return faults


# ---- Run the full pipeline: raw stream -> clean state -> faults ----

if __name__ == "__main__":
    pole_state = reduce_telemetry_to_pole_states(telemetry_stream)

    print("\nResolved pole states:")
    for pole_id, energized in sorted(pole_state.items()):
        print(f"  {pole_id}: {'live' if energized else 'dark'}")

    faults = find_faults(pole_state, topology)

    print("\nDetected faults:")
    for fault in faults:
        print(fault)
