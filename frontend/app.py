"""Streamlit UI for policy questions and authenticated claim workflows."""
import os
import re

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
CHAT_ENDPOINT = f"{BACKEND_URL}/api/v1/chat"
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/login"

st.set_page_config(page_title="OmniCare Assistant", page_icon="🏠")

DEMO_ACCOUNTS = {
    "usr_123": {"label": "Demo Customer 123", "pin": "1234"},
    "usr_456": {"label": "Demo Customer 456", "pin": "4567"},
}

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "profile" not in st.session_state:
    st.session_state.profile = None
if "messages" not in st.session_state:
    st.session_state.messages = []


def login(user_id: str, pin: str) -> dict:
    response = requests.post(LOGIN_ENDPOINT, json={"user_id": user_id, "pin": pin}, timeout=10)
    response.raise_for_status()
    return response.json()


def send_message(message: str) -> dict:
    response = requests.post(
        CHAT_ENDPOINT,
        headers={"Authorization": f"Bearer {st.session_state.access_token}"},
        json={"user_id": st.session_state.user_id, "message": message},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


with st.sidebar:
    st.subheader("Account")
    if st.session_state.access_token and st.session_state.profile:
        profile = st.session_state.profile
        st.success(f"Signed in as {profile['display_name']}")
        st.caption(f"User ID: {profile['user_id']}")
        st.markdown("**Your authorized policies**")
        for policy in profile["policies"]:
            st.write(f"✓ `{policy}` — claim submission allowed")
        if st.button("Sign out"):
            for key in ("access_token", "user_id", "profile", "messages"):
                st.session_state[key] = None if key != "messages" else []
            st.rerun()
    else:
        st.info("Sign in with a demo account to use the assistant.")
        account = st.selectbox(
            "Demo account",
            options=list(DEMO_ACCOUNTS),
            format_func=lambda value: DEMO_ACCOUNTS[value]["label"],
        )
        pin = st.text_input("Demo PIN", value=DEMO_ACCOUNTS[account]["pin"], type="password")
        if st.button("Sign in", type="primary"):
            try:
                profile = login(account, pin)
                st.session_state.access_token = profile["access_token"]
                st.session_state.user_id = profile["user_id"]
                st.session_state.profile = profile
                st.session_state.messages = []
                st.rerun()
            except requests.RequestException:
                st.error("Unable to sign in. Check that the backend is running.")

st.title("🏠 OmniCare Customer Assistant")
st.caption("Ask about policy coverage, check a claim, or submit a new claim.")

if not st.session_state.access_token:
    st.warning("Please sign in from the Account panel before starting a chat.")
    st.stop()


for index, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"].replace("$", r"\$"))
        if msg.get("sources"):
            labels = [s.get("section", "") if isinstance(s, dict) else s for s in msg["sources"]]
            st.caption("📄 Sources: " + "; ".join(labels))
        if msg.get("pending_token"):
            st.info("Review the claim details above. The claim will not be submitted until you confirm it.")
            if st.button("Confirm claim submission", key=f"confirm_{index}"):
                with st.spinner("Submitting claim..."):
                    try:
                        data = send_message(f"confirm {msg['pending_token']}")
                        st.session_state.messages.append(
                            {"role": "assistant", "content": data["response"], "sources": data.get("sources", [])}
                        )
                        st.rerun()
                    except requests.RequestException:
                        st.error("The backend could not process the confirmation. Please try again.")

user_input = st.chat_input("Type your message...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                data = send_message(user_input)
                st.markdown(data["response"].replace("$", r"\$"))
                if data.get("sources"):
                    labels = [s.get("section", "") if isinstance(s, dict) else s for s in data["sources"]]
                    st.caption("📄 Sources: " + "; ".join(labels))
                token_match = re.search(
                    r"Reply ['\"]confirm ([A-Za-z0-9_-]+)['\"]", data.get("response", "")
                )
                assistant_msg = {
                    "role": "assistant",
                    "content": data["response"],
                    "sources": data.get("sources", []),
                }
                if token_match:
                    assistant_msg["pending_token"] = token_match.group(1)
                st.session_state.messages.append(assistant_msg)
            except requests.exceptions.ConnectionError:
                error_msg = "Can't reach the backend. Is it running?"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except requests.exceptions.Timeout:
                error_msg = "The request took too long. Please try again."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else "unknown"
                error_msg = f"The backend rejected the request ({status_code}). Please sign in again if your session expired."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
