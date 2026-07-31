from flask import Flask, request, jsonify, render_template
from telemetry_ingest import reduce_telemetry_to_pole_states
from fault_engine import find_faults, load_topology_from_csv
from simulator import Simulator

app = Flask(__name__)

# Load topology ONCE at startup, from the CSV registry (not hardcoded anymore)
topology, topo_confidence = load_topology_from_csv("pole_registry.csv")
sim = Simulator("pole_registry.csv")

# Server memory
telemetry = []
latest_pole_state = {}
latest_faults = []


def _process_new_messages(messages):
    """Feed a batch of telemetry messages through the same pipeline
    real device data goes through, and refresh latest state/faults."""
    global latest_pole_state, latest_faults
    telemetry.extend(messages)
    latest_pole_state = reduce_telemetry_to_pole_states(telemetry)
    latest_faults = find_faults(latest_pole_state, topology, topo_confidence)


@app.route("/")
def home():
    return "Power Fault Detector API Running"


@app.route("/dashboard")
def console():
    return render_template("console.html")


@app.route("/telemetry", methods=["POST"])
def receive_telemetry():
    global latest_pole_state, latest_faults

    message = request.get_json()
    telemetry.append(message)

    latest_pole_state = reduce_telemetry_to_pole_states(telemetry)
    latest_faults = find_faults(latest_pole_state, topology, topo_confidence)

    return jsonify({
        "status": "success",
        "message": "Telemetry received successfully",
        "current_pole_state": latest_pole_state,
        "faults": latest_faults
    })


@app.route("/faults", methods=["GET"])
def get_faults():
    return jsonify({
        "current_pole_state": latest_pole_state,
        "faults": latest_faults
    })


# Helpful for debugging: see the resolved topology and which edges were guessed
@app.route("/topology", methods=["GET"])
def get_topology():
    return jsonify({
        "topology": topology,
        "confidence": topo_confidence
    })


# All known poles with their current state - used by the operator console
@app.route("/poles", methods=["GET"])
def get_poles():
    pole_list = []
    for pole in sim.poles:
        pid = pole["pole_id"]
        pole_list.append({
            "pole_id": pid,
            "lat": pole["lat"],
            "lon": pole["lon"],
            "pincode": pole["pincode"],
            "energized": latest_pole_state.get(pid, True),  # assume live if never reported
        })
    return jsonify({"poles": pole_list})


# ---- Simulator endpoints: this is how we (and the evaluator) test the system ----

@app.route("/simulator/inject-fault", methods=["POST"])
def inject_fault():
    body = request.get_json()
    pole_id = body.get("pole_id")

    try:
        messages = sim.inject_fault(pole_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    _process_new_messages(messages)

    return jsonify({
        "status": "success",
        "message": f"Fault injected at {pole_id}",
        "generated_telemetry": messages,
        "current_pole_state": latest_pole_state,
        "faults": latest_faults
    })


@app.route("/simulator/repair-fault", methods=["POST"])
def repair_fault():
    body = request.get_json()
    pole_id = body.get("pole_id")

    try:
        messages = sim.repair_fault(pole_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    _process_new_messages(messages)

    return jsonify({
        "status": "success",
        "message": f"Fault repaired at {pole_id}",
        "generated_telemetry": messages,
        "current_pole_state": latest_pole_state,
        "faults": latest_faults
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
