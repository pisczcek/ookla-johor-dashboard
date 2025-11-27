import streamlit as st

def check_login():
    auth = {}
    try:
        auth = st.secrets["auth"]
    except Exception:
        pass
    if auth.get("enabled"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if u == auth.get("username") and p == auth.get("password"):
                st.session_state["logged_in"] = True
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")
        return st.session_state.get("logged_in", False)
    return True
