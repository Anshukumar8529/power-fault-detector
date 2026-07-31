# topology_loader.py
#
# Step 3: Load topology from a CSV registry (like the real assignment gives),
# and handle the CENTRAL design problem: some poles have no parent_pole_id.
#
# Approach used here (one of several valid ones - document this choice in
# DECISIONS.md): for poles with a KNOWN parent, trust it completely. For
# poles with NO parent recorded, infer the most likely parent as the
# nearest OTHER pole on the same distribution transformer, using GPS
# distance. Mark these inferred edges with lower confidence, and say so
# honestly in the ticket output.

import csv
import math


def load_pole_registry(csv_path):
    poles = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poles.append({
                "pole_id": row["pole_id"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "dt_id": row["dt_id"],
                "parent_pole_id": row["parent_pole_id"] or None,
                "seq_on_line": row["seq_on_line"] or None,
                "pincode": row["pincode"] or None,
            })
    return poles


def haversine_meters(lat1, lon1, lat2, lon2):
    """Straight-line distance between two GPS points, in metres."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def infer_missing_topology(poles):
    """
    Returns:
      topology: {pole_id: parent_pole_id}
      confidence: {pole_id: "known" | "inferred"}
    """
    topology = {}
    confidence = {}

    # Group poles by transformer, since a pole can only connect within its own DT.
    by_dt = {}
    for pole in poles:
        by_dt.setdefault(pole["dt_id"], []).append(pole)

    for dt_id, dt_poles in by_dt.items():
        # A pole is a KNOWN root (directly off the transformer) if it HAS a
        # seq_on_line but no parent - that's deliberate, not missing data.
        # A pole is truly UNKNOWN only if seq_on_line is also missing.
        known_root = [p for p in dt_poles if p["seq_on_line"] and not p["parent_pole_id"]]
        known_child = [p for p in dt_poles if p["parent_pole_id"]]
        known = known_root + known_child
        unknown = [p for p in dt_poles if not p["seq_on_line"] and not p["parent_pole_id"]]

        for p in known_root:
            topology[p["pole_id"]] = None  # connects straight to the transformer
            confidence[p["pole_id"]] = "known"

        for p in known_child:
            topology[p["pole_id"]] = p["parent_pole_id"]
            confidence[p["pole_id"]] = "known"

        # Anchors = poles whose position we can already trust as "placed" in
        # the tree: every pole with a known parent, plus poles already
        # resolved in this loop.
        anchors = list(known)

        for p in unknown:
            if not anchors:
                # No reference point at all for this DT - fall back to no parent.
                topology[p["pole_id"]] = None
                confidence[p["pole_id"]] = "inferred"
                continue

            nearest = min(
                anchors,
                key=lambda a: haversine_meters(p["lat"], p["lon"], a["lat"], a["lon"])
            )
            topology[p["pole_id"]] = nearest["pole_id"]
            confidence[p["pole_id"]] = "inferred"
            anchors.append(p)  # this pole can now anchor further unknowns too

    return topology, confidence


if __name__ == "__main__":
    poles = load_pole_registry("pole_registry.csv")
    topology, confidence = infer_missing_topology(poles)

    print("Resolved topology (pole -> parent):")
    for pole_id, parent_id in topology.items():
        tag = confidence[pole_id]
        print(f"  {pole_id} -> {parent_id}  [{tag}]")
