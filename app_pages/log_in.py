from __future__ import annotations
from pathlib import Path
import re
import contextlib
import streamlit as st
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, func, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from email_validator import validate_email, EmailNotValidError


# ---------- Database ----------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "auth.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    future=True,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
Base = declarative_base()
ph = PasswordHasher()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(254), unique=True, nullable=False)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    password_hash = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

Base.metadata.create_all(engine)

# ---------- Helpers ----------
PASSWORD_POLICY = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)"
    r"(?=.*[!@#$%^&*()_\-+=\[\]{};:'\",.<>/?\\|`~]).{8,128}$"
)

def validate_signup(first, last, email, username, password):
    if not all([first.strip(), last.strip(), email.strip(), username.strip(), password.strip()]):
        return "Please fill in all fields."
    try:
        validate_email(email, allow_smtputf8=True)
    except EmailNotValidError as e:
        return f"❌ {e}"
    if not PASSWORD_POLICY.match(password):
        return ("Password must be 8–128 chars and include uppercase, lowercase, "
                "a digit, and a symbol.")
    return None

@contextlib.contextmanager
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_user(first, last, email, username, password):
    pwd_hash = ph.hash(password)
    with get_db() as db:
        u = User(first_name=first, last_name=last,
                 email=email.lower(), username=username, password_hash=pwd_hash)
        db.add(u)
        try:
            db.commit()
            return True, "✅ Account created!"
        except IntegrityError:
            db.rollback()
            return False, "❌ Username or email already in use."

def authenticate(username_or_email, password):
    with get_db() as db:
        user = db.query(User).filter(
            (User.username == username_or_email) | (User.email == username_or_email.lower())
        ).first()
        if user:
            try:
                if ph.verify(user.password_hash, password):
                    return {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "name": f"{user.first_name} {user.last_name}",
                    }
            except VerifyMismatchError:
                return None
    return None


# ---------- UI ----------
def render():
    # Green button style
    st.markdown("""
        <style>
        div.stButton > button:first-child,
        div.stFormSubmitButton > button:first-child {
            background-color:#228B22!important;color:white!important;
            border:none!important;border-radius:6px!important;padding:0.5rem 1rem!important;
        }
        div.stButton > button:hover,
        div.stFormSubmitButton > button:hover {
            background-color:#1e7a1e!important;color:white!important;
        }
        </style>
    """, unsafe_allow_html=True)

    user = st.session_state.get("user")

    if user:
        st.title("Account")
        st.success(f"Signed in as {user['name']}")
        st.write(f"**Username:** {user['username']}")
        st.write(f"**Email:** {user['email']}")
        if st.button("Log out"):
            st.session_state.pop("user")
            st.session_state.pop("trips", None)  
            st.rerun()
        return

    st.title("Log In")
    if "create_mode" not in st.session_state:
        st.session_state["create_mode"] = False

    # --- Log In Form ---
    if not st.session_state["create_mode"]:
        with st.form("login_form", border=True):
            u = st.text_input("Username or Email")
            p = st.text_input("Password", type="password")
            c1, c2 = st.columns(2)
            with c1:
                login_clicked = st.form_submit_button("Log In", use_container_width=True)
            with c2:
                create_clicked = st.form_submit_button("Create Account", use_container_width=True)

            if login_clicked:
                if not u or not p:
                    st.error("Please enter both fields.")
                else:
                    authed = authenticate(u, p)
                    if authed:
                        st.session_state["user"] = authed
                        st.session_state.pop("trips", None)  
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")

            if create_clicked:
                st.session_state["create_mode"] = True
                st.rerun()

    # --- Create Account Form ---
    else:
        with st.form("signup_form", border=True):
            st.subheader("Create Account")
            c1, c2 = st.columns(2)
            with c1:
                first = st.text_input("First Name")
            with c2:
                last = st.text_input("Last Name")
            email = st.text_input("Email")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            cta1, cta2 = st.columns(2)
            with cta1:
                submit = st.form_submit_button("Create Account", use_container_width=True)
            with cta2:
                back = st.form_submit_button("Back to Log In", use_container_width=True)

            if submit:
                err = validate_signup(first, last, email, username, password)
                if err:
                    st.error(err)
                else:
                    ok, msg = create_user(first, last, email, username, password)
                    if ok:
                        st.success(msg)
                        st.session_state["create_mode"] = False
                        st.rerun()
                    else:
                        st.error(msg)
            if back:
                st.session_state["create_mode"] = False
                st.rerun()


if __name__ == "__main__":
    render()
