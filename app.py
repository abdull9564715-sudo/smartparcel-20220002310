from flask import Flask, request, jsonify
import boto3
import uuid
import datetime
import json
import socket

app = Flask(__name__)

# ==============================
# 🔐 SIMPLE API KEY SYSTEM
# ==============================
USER_KEYS = {
    "key-admin-001": "admin",
    "key-driver-001": "driver",
    "key-customer-001": "customer"
}

# ==============================
# ☁️ AWS CONFIGURATION
# ==============================
REGION = "ap-southeast-2"
TABLE_NAME = "smartparcel-parcels"
QUEUE_URL = "https://sqs.ap-southeast-2.amazonaws.com/230195035124/smartparcel-notifications-2023001234"

# ==============================
# 🔗 AWS CONNECTIONS
# ==============================
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

sqs = boto3.client("sqs", region_name=REGION)

# ==============================
# 🔍 AUTH CHECK FUNCTION
# ==============================
def check_auth(allowed_roles):
    api_key = request.headers.get("X-API-Key")

    if not api_key or api_key not in USER_KEYS:
        return None, (jsonify({"error": "API key missing"}), 401)

    role = USER_KEYS[api_key]

    if role not in allowed_roles:
        return None, (jsonify({"error": "Access denied"}), 403)

    return role, None

# ==============================
# ❤️ HEALTH CHECK
# ==============================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "hostname": socket.gethostname()
    })

# ==============================
# 📦 CREATE PARCEL
# ==============================
@app.route("/api/parcels", methods=["POST"])
def create_parcel():

    role, err = check_auth(["admin", "driver"])
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    parcel_id = "PKG-" + uuid.uuid4().hex[:8]

    item = {
        "parcel_id": parcel_id,
        "sender": data.get("sender"),
        "receiver": data.get("receiver"),
        "address": data.get("address"),
        "email": data.get("email"),
        "status": "created",
        "history": [
            {
                "status": "created",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
    }

    table.put_item(Item=item)

    print(f"{datetime.datetime.utcnow()} | POST -> {parcel_id}")

    return jsonify({"parcel_id": parcel_id}), 201

# ==============================
# 📄 GET PARCEL DETAILS
# ==============================
@app.route("/api/parcels/<pid>", methods=["GET"])
def get_parcel(pid):

    role, err = check_auth(["admin", "driver", "customer"])
    if err:
        return err

    response = table.get_item(Key={"parcel_id": pid})

    if "Item" not in response:
        return jsonify({"error": "Parcel not found"}), 404

    print(f"{datetime.datetime.utcnow()} | GET -> {pid}")

    return jsonify(response["Item"])

# ==============================
# 🔄 UPDATE PARCEL STATUS (PUT)
# ==============================
@app.route("/api/parcels/<pid>/status", methods=["PUT"])
def update_status(pid):

    role, err = check_auth(["driver"])
    if err:
        return err

    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    new_status = data["status"]

    response = table.get_item(Key={"parcel_id": pid})

    if "Item" not in response:
        return jsonify({"error": "Parcel not found"}), 404

    item = response["Item"]

    # update history
    history = item.get("history", [])
    history.append({
        "status": new_status,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

    # update database
    table.update_item(
        Key={"parcel_id": pid},
        UpdateExpression="SET #s = :s, history = :h",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": new_status,
            ":h": history
        }
    )

    # send message to SQS
    message = {
        "parcel_id": pid,
        "status": new_status,
        "email": item.get("email")
    }

    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message)
    )

    print(f"{datetime.datetime.utcnow()} | PUT -> {pid} -> {new_status}")

    return jsonify({"message": "Status updated"}), 200

# ==============================
# 🚀 RUN SERVER
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)