import json
import base64

# Read the token from localStorage (we'll get it from the browser)
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyYjI1NzFkYy1iOTExLTQwZmQtOThjNy0xYjAyYTMyYjE1MGMiLCJlbWFpbCI6ImNob29udmFpQGdtYWlsLmNvbSIsImZ1bGxfbmFtZSI6bnVsbCwiaXNfYWN0aXZlIjp0cnVlLCJpc192ZXJpZmllZCI6ZmFsc2UsImF2YXRhcl91cmwiOm51bGwsIn0.abc123"

# Decode the payload
parts = token.split('.')
payload = json.loads(base64.b64decode(parts[1] + '==').decode('utf-8'))
print("Payload:", json.dumps(payload, indent=2))

import time
now = int(time.time())
print(f"Current time: {now}")
print(f"Token expiry: {payload.get('exp', 'N/A')}")
if 'exp' in payload:
    print(f"Time until expiry: {payload['exp'] - now} seconds")
    print(f"Is expired: {payload['exp'] < now}")
