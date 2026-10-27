"""Step 1 check: can Python log in to your Salesforce Developer Edition org?"""
import os
import sys

from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

missing = [k for k in ("SF_CONSUMER_KEY", "SF_CONSUMER_SECRET", "SF_DOMAIN") if not os.getenv(k)]
if missing:
    sys.exit(f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill it in.")

domain = os.environ["SF_DOMAIN"].strip()
if domain.endswith(".salesforce.com"):
    domain = domain[: -len(".salesforce.com")]
domain = domain.replace("https://", "").rstrip("/")

try:
    sf = Salesforce(
        consumer_key=os.environ["SF_CONSUMER_KEY"].strip(),
        consumer_secret=os.environ["SF_CONSUMER_SECRET"].strip(),
        domain=domain,
    )
except Exception as e:
    print("Login failed:\n", e)
    print("\nCommon causes: Run As user not set on the app's Policies tab, "
          "Client Credentials flow not enabled, or SF_DOMAIN wrong (must be your My Domain).")
    sys.exit(1)

print(f"Connected to {sf.sf_instance}\n")
records = sf.query("SELECT Id, Name FROM Account ORDER BY Name LIMIT 10")["records"]
print(f"Found {len(records)} accounts:")
for r in records:
    print(" -", r["Name"])
