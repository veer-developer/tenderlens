from google import genai
import json, re

GEMINI_API_KEY = ""
client = genai.Client(api_key=GEMINI_API_KEY)

bidder_text = """COMPANY PROFILE DOCUMENT
Company: ABC Construction Pvt Ltd
PAN: ABCDE1234F
GST Number: 29ABCDE1234F1Z5 Active Valid
FINANCIAL DETAILS
Annual Turnover FY 2023-24 Rs 8.5 Crore
ISO 9001 2015 Certificate Valid Until March 2027
Project 1 Road Construction NHAI 2022 Rs 3.2 Crore
Project 2 Government Building PWD Karnataka 2021 Rs 2.8 Crore
Project 3 Bridge Repair BBMP Bangalore 2023 Rs 1.9 Crore"""

criteria = [
    {"id":1,"criterion":"Minimum annual turnover of Rs. 5 crore","type":"Financial","mandatory":True,"threshold":"Rs. 5 crore"},
    {"id":2,"criterion":"At least 3 similar projects in last 5 years","type":"Technical","mandatory":True,"threshold":"3 projects"},
    {"id":3,"criterion":"Valid GST registration certificate","type":"Document","mandatory":True,"threshold":None},
    {"id":4,"criterion":"ISO 9001 certification","type":"Compliance","mandatory":False,"threshold":None},
]

prompt = f"""Evaluate this bidder against each criterion.
Return ONLY a valid JSON array. No markdown. No explanation.

Each object: {{"criterion_id": <int>, "criterion_name": "<text>", "verdict": "Eligible|Not Eligible|Needs Review", "confidence": <0.0-1.0>, "evidence": "<found text>", "reason": "<explanation>"}}

CRITERIA: {json.dumps(criteria)}
BIDDER: ABC Construction Pvt Ltd
DOCUMENTS: {bidder_text}

JSON array only:"""

r = client.models.generate_content(model="gemini-2.0-flash-lite", contents=prompt)
print("RAW RESPONSE:")
print(r.text)
print("\n--- PARSING ---")
raw = re.sub(r"```json|```", "", r.text).strip()
start = raw.find("[")
if start != -1:
    raw = raw[start:]
try:
    parsed = json.loads(raw)
    print("SUCCESS! Items:", len(parsed))
    print(json.dumps(parsed[0], indent=2))
except Exception as e:
    print("FAILED:", e)
    print("Cleaned text was:", repr(raw[:200]))
