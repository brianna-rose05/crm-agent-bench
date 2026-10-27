"""Shared Salesforce login used by every script in this project."""
import os
import sys

from dotenv import load_dotenv
from simple_salesforce import Salesforce


def connect():
    load_dotenv()
    missing = [k for k in ("SF_CONSUMER_KEY", "SF_CONSUMER_SECRET", "SF_DOMAIN") if not os.getenv(k)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")
    domain = os.environ["SF_DOMAIN"].strip().replace("https://", "").rstrip("/")
    if domain.endswith(".salesforce.com"):
        domain = domain[: -len(".salesforce.com")]
    return Salesforce(
        consumer_key=os.environ["SF_CONSUMER_KEY"].strip(),
        consumer_secret=os.environ["SF_CONSUMER_SECRET"].strip(),
        domain=domain,
    )
