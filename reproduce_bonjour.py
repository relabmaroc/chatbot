import requests
import json
import sys
import uuid

BASE_URL = "http://localhost:8000"
USER_ID = "jihgi"

def send_message(message):
    print(f"\nSending: {message}")
    payload = {
        "message": message,
        "channel": "web",
        "identifier": USER_ID
    }
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"Response: {data['message']}")
        if "souci technique" in data['message']:
            print("❌ ERROR REPRODUCED!")
            print(f"Metadata: {data.get('metadata')}")
        else:
            print("✅ Response seems OK")
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    send_message("Bonjour")
