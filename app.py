from flask import Flask, request, jsonify
import os
import re
import requests

app = Flask(__name__)

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
if not ACCESS_TOKEN:
    raise RuntimeError("⚠️ ACCESS_TOKEN environment variable not set!")

HUBSPOT_URL = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# -------------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------------
def normalize_phone(phone):
    """Clean messy phone numbers and format as +1XXXXXXXXXX for US numbers."""
    if not phone:
        return None
    phone = re.sub(r"(ext\.?|x|extension)\s*\d*", "", phone, flags=re.IGNORECASE)
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    if len(digits) == 10:
        digits = "1" + digits
    elif len(digits) > 11 and digits.startswith("00"):
        digits = digits[2:]
    return f"+{digits}"


def normalize_name(name):
    """Clean up extra spaces and standardize capitalization for names."""
    if not name:
        return None
    name = re.sub(r"\s+", " ", name.strip())
    parts = []
    for word in name.split(" "):
        sub = re.split(r"([-'])", word)
        parts.append("".join(s.capitalize() if s.isalpha() else s for s in sub))
    return " ".join(parts)


def split_name(full_name):
    """Split a full name into first + last (everything after first space = last)."""
    if not full_name:
        return None, None
    full_name = full_name.strip()
    first_space = full_name.find(" ")
    if first_space == -1:
        return full_name, None
    first = full_name[:first_space]
    last = full_name[first_space + 1:].strip()
    return first, last


# -------------------------------------------------------------------
# WEBHOOK ENDPOINT
# -------------------------------------------------------------------
@app.route("/hubspot-cleaner", methods=["POST"])
def hubspot_cleaner():
    """Receive Google Form data (via Apps Script), clean it, and send to HubSpot."""
    data = request.get_json(force=True)
    print("📬 Received submission:", data)

    # Extract raw fields
    name_raw = data.get("name")
    email = data.get("email")
    phone = data.get("phone")

    # Clean and process
    firstname_raw, lastname_raw = split_name(name_raw)
    firstname = normalize_name(firstname_raw)
    lastname = normalize_name(lastname_raw)
    phone = normalize_phone(phone)

    if not email:
        print("⚠️ No email found in submission; skipping.")
        return jsonify({"error": "Missing email"}), 400

    payload = {
        "properties": {
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "phone": phone
        }
    }

    # Send to HubSpot
    resp = requests.post(f"{HUBSPOT_URL}/crm/v3/objects/contacts",
                         headers=HEADERS, json=payload)

    if resp.status_code in (200, 201):
        print(f"✅ Contact created/updated successfully for {email}")
        return jsonify({"message": "OK"}), 200
    else:
        print(f"❌ HubSpot error {resp.status_code}: {resp.text}")
        return jsonify({"error": "HubSpot error", "details": resp.text}), 500


# -------------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
