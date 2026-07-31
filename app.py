from flask import Flask, request, jsonify
from telemetry_ingest import reduce_telemetry_to_pole_states
from fault_engine import find_faults, load_topology_from_csv

app = Flask(__name__)

# Load topology ONCE at startup, from the CSV registry (not hardcoded anymore)
topology, topo_confidence = load_topology_from_csv("pole_registry.csv")

# Server memory
telemetry = []
latest_pole_state = {}
latest_faults = []


@app.route("/")
def home():
    return "Power Fault Detector API Running"


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


if __name__ == "__main__":
    app.run(debug=True)
