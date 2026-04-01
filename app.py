# -------------------------------------------------------
# SmartParcel — NET_214 Project, Spring 2026
# Author  : ABDUL LATIF
# ID      : 20220002310
# Email   : your-email@cud.ac.ae
# AWS Acc : 230195035124
# -------------------------------------------------------

from flask import Flask, request, jsonify
import uuid
import datetime
import boto3
import json
import socket

app = Flask(__name__)

# ---------------- API KEYS ----------------
API_KEYS = {
    "key-admin-001": "admin",
    "key-driver-001": "driver",
    "key-customer-001": "customer"
}

# ---------------- AWS CONFIG ----------------
REGION = "ap-southeast-2"
TABLE_NAME = "smartparcel-parcels"
BUCKET_NAME = "smartparcel-photos-20220002310"
QUEUE_URL = "https://sqs.ap-southeast-2.amazonaws.com/230195035124/smartparcel-notifications-20220002310"

# ---------------- AWS CLIENTS ----------------
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

s3 = boto3.client('s3', region_name=REGION)
sqs = boto3.client('sqs', region_name=REGION)

# ---------------- AUTH FUNCTION ----------------
def authenticate(required_roles):
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key not in API_KEYS:
        return None, (jsonify({"error": "Unauthorized"}), 401)

    role = API_KEYS[api_key]

    if role not in required_roles:
        return None, (jsonify({"error": "Forbidden"}), 403)

    return role, None

# ---------------- HEALTH CHECK ----------------
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "hostname": socket.gethostname()
    }), 200

# ---------------- CREATE PARCEL ----------------
@app.route('/api/parcels', methods=['POST'])
def create_parcel():
    role, error = authenticate(["admin", "driver"])
    if error:
        return error

    data = request.get_json()

    required_fields = ["sender", "receiver", "address", "email"]
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    parcel_id = "PKG-" + str(uuid.uuid4())[:8]

    item = {
        "parcel_id": parcel_id,
        "sender": data["sender"],
        "receiver": data["receiver"],
        "address": data["address"],
        "email": data["email"],
        "status": "created",
        "history": [{
            "status": "created",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }]
    }

    table.put_item(Item=item)

    return jsonify({"parcel_id": parcel_id}), 201

# ---------------- GET PARCEL ----------------
@app.route('/api/parcels/<parcel_id>', methods=['GET'])
def get_parcel(parcel_id):
    role, error = authenticate(["admin", "driver", "customer"])
    if error:
        return error

    response = table.get_item(Key={"parcel_id": parcel_id})

    if "Item" not in response:
        return jsonify({"error": "Parcel not found"}), 404

    return jsonify(response["Item"]), 200

# ---------------- UPDATE STATUS ----------------
@app.route('/api/parcels/<parcel_id>/status', methods=['PUT'])
def update_status(parcel_id):
    role, error = authenticate(["driver"])
    if error:
        return error

    data = request.get_json()
    new_status = data.get("status")

    valid_status = ["picked_up", "in_transit", "delivered"]
    if new_status not in valid_status:
        return jsonify({"error": "Invalid status"}), 400

    response = table.get_item(Key={"parcel_id": parcel_id})
    if "Item" not in response:
        return jsonify({"error": "Parcel not found"}), 404

    item = response["Item"]

    item["status"] = new_status
    item["history"].append({
        "status": new_status,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

    table.put_item(Item=item)

    # ---------------- SEND TO SQS ----------------
    message = {
        "parcel_id": parcel_id,
        "new_status": new_status,
        "customer_email": item["email"],
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message)
    )

    return jsonify({"message": "Status updated"}), 200

# ---------------- LIST PARCELS ----------------
@app.route('/api/parcels', methods=['GET'])
def list_parcels():
    role, error = authenticate(["admin"])
    if error:
        return error

    response = table.scan()
    return jsonify(response.get("Items", [])), 200

# ---------------- DELETE PARCEL ----------------
@app.route('/api/parcels/<parcel_id>', methods=['DELETE'])
def delete_parcel(parcel_id):
    role, error = authenticate(["admin"])
    if error:
        return error

    response = table.get_item(Key={"parcel_id": parcel_id})
    if "Item" not in response:
        return jsonify({"error": "Parcel not found"}), 404

    item = response["Item"]

    if item["status"] != "created":
        return jsonify({"error": "Cannot cancel parcel"}), 409

    item["status"] = "cancelled"
    table.put_item(Item=item)

    return jsonify({"message": "Parcel cancelled"}), 200

# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
