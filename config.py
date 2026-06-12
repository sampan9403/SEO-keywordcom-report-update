import streamlit as st
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/presentations"]

def get_credentials():
    try:
        info = dict(st.secrets["gcp_service_account"])
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        return service_account.Credentials.from_service_account_file(
            "Google-Slides-Keys.json", scopes=SCOPES
        )

def get_service_account_email():
    try:
        return st.secrets["gcp_service_account"]["client_email"]
    except Exception:
        try:
            import json
            with open("Google-Slides-Keys.json") as f:
                return json.load(f).get("client_email", "")
        except Exception:
            return ""
