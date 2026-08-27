import hashlib
import os
import time

ACCOUNTS_FILE = "accounts.csv"
MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 30

# Tracks failed logins per username while the server is running:
# { "username": {"count": int, "locked_until": timestamp or None} }
failed_attempts = {}


class User:
    def __init__(self, username, password_hash):
        self.username = username
        self.password_hash = password_hash

    @staticmethod
    def hash_password(password):
        # We NEVER store the actual password. Hashing turns it into a fixed-length
        # string that can't be reversed back into the original password.
        # SHA-256 is a standard library hash function — good enough for a school project.
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def check_password_strength(password):
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."

        has_upper = False
        has_digit = False
        has_symbol = False
        symbols = "!@#$%^&*(),.?\":{}|<>"

        # Walk through each character once and flip flags as we spot each type.
        for char in password:
            if char.isupper():
                has_upper = True
            elif char.isdigit():
                has_digit = True
            elif char in symbols:
                has_symbol = True

        if not has_upper:
            return False, "Password must contain at least one uppercase letter."
        if not has_digit:
            return False, "Password must contain at least one digit."
        if not has_symbol:
            return False, "Password must contain at least one special character."

        return True, "Password is strong."


def load_accounts():
    # Returns a dict of {username: User} so we can quickly check "does this username exist?"
    accounts = {}

    if not os.path.exists(ACCOUNTS_FILE):
        return accounts

    with open(ACCOUNTS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            username, password_hash = line.split(",")
            accounts[username] = User(username, password_hash)

    return accounts


def save_account(user):
    # "a" = append mode, so we add this user without erasing existing accounts.
    with open(ACCOUNTS_FILE, "a") as f:
        f.write(f"{user.username},{user.password_hash}\n")


def register_user(username, password):
    accounts = load_accounts()

    if username in accounts:
        return False, "That username is already taken."

    is_strong, message = User.check_password_strength(password)
    if not is_strong:
        return False, message

    password_hash = User.hash_password(password)
    new_user = User(username, password_hash)
    save_account(new_user)

    return True, "Registration successful. You can now log in."


def login_user(username, password):
    accounts = load_accounts()

    # Get this user's attempt record, or a fresh one if we haven't seen them yet.
    record = failed_attempts.get(username, {"count": 0, "locked_until": None})

    # If they're currently locked out, refuse before even checking the password.
    if record["locked_until"] is not None and time.time() < record["locked_until"]:
        remaining = int(record["locked_until"] - time.time())
        return False, f"Account locked. Try again in {remaining} seconds."

    # Deliberately vague message here — we don't want to reveal to an attacker
    # whether the USERNAME or the PASSWORD was the wrong part.
    if username not in accounts:
        return False, "Invalid username or password."

    password_hash = User.hash_password(password)

    if password_hash == accounts[username].password_hash:
        # Successful login clears any past failed attempts.
        failed_attempts[username] = {"count": 0, "locked_until": None}
        return True, "Login successful."

    # Wrong password — increment the counter and lock out if we've hit the limit.
    record["count"] += 1
    if record["count"] >= MAX_ATTEMPTS:
        record["locked_until"] = time.time() + LOCKOUT_SECONDS
        record["count"] = 0
        failed_attempts[username] = record
        return False, f"Too many failed attempts. Account locked for {LOCKOUT_SECONDS} seconds."

    failed_attempts[username] = record
    return False, "Invalid username or password."