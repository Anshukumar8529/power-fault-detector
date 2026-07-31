# simulator.py
#
# Step 4: The fault simulator.
#
# We have no real hardware. This is how WE (and the evaluator) will actually
# drive the system: pick a pole where a fault "happens", and this module
# generates the telemetry that such a fault would realistically cause -
# for every pole downstream of it, not just the one pole.
#
# Repairing does the reverse: generates power_restored telemetry for the
# same set of poles.

from topology_loader import load_pole_registry, infer_missing_topology


class Simulator:
    def __init__(self, csv_path="pole_registry.csv"):
        self.poles = load_pole_registry(csv_path)
        self.topology, self.confidence = infer_missing_topology(self.poles)
        self.pole_by_id = {p["pole_id"]: p for p in self.poles}

        # Track sequence numbers per device so simulated messages keep
        # incrementing realistically (never reuse/duplicate a seq).
        self.seq_counter = {p["pole_id"]: 0 for p in self.poles}

        self.children_of = {p["pole_id"]: [] for p in self.poles}
        for pid, parent_id in self.topology.items():
            if parent_id:
                self.children_of.setdefault(parent_id, []).append(pid)

    def _next_seq(self, pole_id):
        self.seq_counter[pole_id] += 1
        return self.seq_counter[pole_id]

    def _affected_subtree(self, pole_id):
        """Every pole downstream of pole_id, INCLUDING pole_id itself."""
        affected = [pole_id]
        stack = list(self.children_of.get(pole_id, []))
        while stack:
            current = stack.pop()
            affected.append(current)
            stack.extend(self.children_of.get(current, []))
        return affected

    def inject_fault(self, pole_id, ts="2026-07-31T10:00:00Z"):
        """
        Simulate a span fault AT pole_id: pole_id and everything downstream
        of it goes dark. Returns the list of telemetry messages generated -
        feed these into reduce_telemetry_to_pole_states() same as real data.
        """
        if pole_id not in self.pole_by_id:
            raise ValueError(f"Unknown pole_id: {pole_id}")

        affected = self._affected_subtree(pole_id)
        messages = []

        for pid in affected:
            device_id = self.pole_by_id[pid]["device_id"]
            if not device_id:
                continue  # this pole has no device fitted - can't report anything
            messages.append({
                "device_id": device_id,
                "pole_id": pid,
                "event": "power_lost",
                "energized": False,
                "ts": ts,
                "seq": self._next_seq(pid),
            })

        return messages

    def repair_fault(self, pole_id, ts="2026-07-31T10:30:00Z"):
        """
        Simulate the crew fixing the span: pole_id and everything downstream
        comes back live. Returns power_restored telemetry messages.
        """
        if pole_id not in self.pole_by_id:
            raise ValueError(f"Unknown pole_id: {pole_id}")

        affected = self._affected_subtree(pole_id)
        messages = []

        for pid in affected:
            device_id = self.pole_by_id[pid]["device_id"]
            if not device_id:
                continue
            messages.append({
                "device_id": device_id,
                "pole_id": pid,
                "event": "power_restored",
                "energized": True,
                "ts": ts,
                "seq": self._next_seq(pid),
            })

        return messages


if __name__ == "__main__":
    sim = Simulator("pole_registry.csv")

    print("Injecting fault at P-3 ...")
    fault_messages = sim.inject_fault("P-3")
    for m in fault_messages:
        print(" ", m)

    print("\nRepairing fault at P-3 ...")
    repair_messages = sim.repair_fault("P-3")
    for m in repair_messages:
        print(" ", m)
