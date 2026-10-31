"""
bank_backend.py
---------------
Pure-Python, in-memory banking backend with a security layer.

* No web frameworks, no databases: everything lives in dicts and lists.
* Money uses `decimal.Decimal` (never float).
* Passwords: PBKDF2-HMAC-SHA256, unique 16-byte salt per user, 200,000 iterations,
  verified with constant-time comparison (hmac.compare_digest).
* Sessions: secrets.token_urlsafe(32) tokens with a TTL. Only SHA-256 hashes of
  tokens are stored, so a memory dump cannot be replayed as valid logins.
* Every banking operation requires a valid token, and users can only operate
  on accounts they own.

Classes: Transaction, Account, User, SessionManager, Bank (+ custom exceptions).
"""

import hashlib
import hmac
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import count
from typing import Callable, Dict, List, Union

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
PBKDF2_ITERATIONS = 200_000      # slows down brute-force attacks
SALT_BYTES = 16                  # unique random salt per user
TOKEN_BYTES = 32                 # input to secrets.token_urlsafe
DEFAULT_TOKEN_TTL = 15 * 60      # tokens live for 15 minutes (seconds)
MIN_PASSWORD_LENGTH = 8
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,32}$")

# Accepted input types for money. Floats are rejected (they are inexact).
Money = Union[int, str, Decimal]
TWO_PLACES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class BankError(Exception):
    """Base class for every error raised by this module."""


# -- money / account errors
class InvalidAmountError(BankError):
    """Amount is not a valid positive money value."""


class InsufficientFundsError(BankError):
    """Balance is lower than the amount requested."""


class AccountNotFoundError(BankError):
    """No account exists with the given ID."""


class InvalidTransferError(BankError):
    """Transfer is not allowed (e.g. sender and receiver are the same)."""


# -- security errors
class UserAlreadyExistsError(BankError):
    """Username is already taken."""


class InvalidUsernameError(BankError):
    """Username does not meet the format rules."""


class WeakPasswordError(BankError):
    """Password does not meet the minimum requirements."""


class AuthenticationError(BankError):
    """Wrong username or password."""


class InvalidTokenError(BankError):
    """Token is missing, malformed, unknown or revoked."""


class TokenExpiredError(InvalidTokenError):
    """Token was valid but its time-to-live has passed."""


class AuthorizationError(BankError):
    """Authenticated user is not allowed to use this account."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def to_money(value: Money, allow_zero: bool = False) -> Decimal:
    """
    Convert input to a validated Decimal with exactly 2 decimal places.

    Rules: number (not float/bool), finite, > 0 (or >= 0 if allow_zero),
    and at most 2 decimal places.
    """
    if isinstance(value, (float, bool)):
        raise InvalidAmountError("Use int, str or Decimal for amounts (not float/bool).")
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise InvalidAmountError(f"'{value}' is not a valid number.")

    if not amount.is_finite():
        raise InvalidAmountError("Amount must be a finite number.")
    if amount < 0 or (amount == 0 and not allow_zero):
        raise InvalidAmountError("Amount must be greater than 0.")
    if amount != amount.quantize(TWO_PLACES):
        raise InvalidAmountError("Amount cannot have more than 2 decimal places.")
    return amount.quantize(TWO_PLACES)


def hash_password(password: str, salt: bytes) -> bytes:
    """Derive a password hash with PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )


# Fixed salt used only to burn the same CPU time when a username doesn't exist,
# so response time doesn't reveal which usernames are registered.
_DUMMY_SALT = b"\x00" * SALT_BYTES


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------
@dataclass(frozen=True)  # immutable: history entries can't be edited later
class Transaction:
    """One entry in an account's history."""
    id: int
    timestamp: datetime
    amount: Decimal
    type: str                  # DEPOSIT, WITHDRAWAL, TRANSFER_OUT, TRANSFER_IN
    resulting_balance: Decimal

    def __str__(self) -> str:
        return (f"#{self.id:<3} {self.timestamp:%Y-%m-%d %H:%M:%S} | "
                f"{self.type:<12} | {self.amount:>10} | balance: {self.resulting_balance:>10}")


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
class Account:
    """Manages the funds and transaction history of one account."""

    def __init__(self, account_id: str, owner_username: str, initial_balance: Money = 0):
        self.account_id = account_id
        self.owner_username = owner_username
        self._balance = Decimal("0.00")
        self._transactions: List[Transaction] = []
        self._tx_counter = count(1)

        opening = to_money(initial_balance, allow_zero=True)
        if opening > 0:
            self.deposit(opening)

    @property
    def balance(self) -> Decimal:
        """Read-only: outside code cannot assign a balance directly."""
        return self._balance

    def _record(self, amount: Decimal, tx_type: str) -> Transaction:
        tx = Transaction(next(self._tx_counter), datetime.now(), amount, tx_type, self._balance)
        self._transactions.append(tx)
        return tx

    def deposit(self, amount: Money, tx_type: str = "DEPOSIT") -> Transaction:
        """Add money. Amount must be > 0."""
        amount = to_money(amount)
        self._balance += amount
        return self._record(amount, tx_type)

    def withdraw(self, amount: Money, tx_type: str = "WITHDRAWAL") -> Transaction:
        """Remove money. Amount must be > 0 and balance must be >= amount."""
        amount = to_money(amount)
        if self._balance < amount:
            raise InsufficientFundsError(
                f"Account {self.account_id}: balance {self._balance} is less than {amount}."
            )
        self._balance -= amount
        return self._record(amount, tx_type)

    def get_statement(self) -> List[Transaction]:
        """Return a copy of the history so callers can't modify the original."""
        return list(self._transactions)

    # -- internal: used ONLY by Bank to undo a failed transfer ---------------
    def _snapshot(self):
        return self._balance, len(self._transactions)

    def _restore(self, snapshot) -> None:
        balance, history_len = snapshot
        self._balance = balance
        del self._transactions[history_len:]
        self._tx_counter = count(history_len + 1)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User:
    """A bank customer. Stores only a salted password hash, never the password."""

    def __init__(self, username: str, salt: bytes, password_hash: bytes):
        self.username = username
        self._salt = salt
        self._password_hash = password_hash
        self._account_ids: List[str] = []   # accounts linked to this user

    @classmethod
    def create(cls, username: str, password: str) -> "User":
        """Build a user with a fresh random salt and a hashed password."""
        salt = secrets.token_bytes(SALT_BYTES)
        return cls(username, salt, hash_password(password, salt))

    def verify_password(self, password: str) -> bool:
        """Constant-time password check (prevents timing attacks)."""
        if not isinstance(password, str):
            return False
        candidate = hash_password(password, self._salt)
        return hmac.compare_digest(candidate, self._password_hash)

    @property
    def account_ids(self) -> List[str]:
        return list(self._account_ids)

    def _link_account(self, account_id: str) -> None:
        self._account_ids.append(account_id)

    def owns(self, account_id: str) -> bool:
        return account_id in self._account_ids


# ---------------------------------------------------------------------------
# Session / token management
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Session:
    """What we remember about a token (we never store the token itself)."""
    username: str
    expires_at: float


class SessionManager:
    """Issues, validates and revokes expiring login tokens."""

    def __init__(self, ttl_seconds: int = DEFAULT_TOKEN_TTL,
                 clock: Callable[[], float] = time.time):
        self._ttl = ttl_seconds
        self._clock = clock                       # injectable, so expiry is testable
        self._sessions: Dict[str, Session] = {}   # sha256(token) -> Session

    @staticmethod
    def _digest(token: str) -> str:
        """Tokens are random and high-entropy, so a fast SHA-256 is enough here."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, username: str) -> str:
        """Create a token. The plain token is returned once and never stored."""
        self.purge_expired()
        token = secrets.token_urlsafe(TOKEN_BYTES)
        self._sessions[self._digest(token)] = Session(username, self._clock() + self._ttl)
        return token

    def validate(self, token: str) -> str:
        """Return the username for a valid token, or raise."""
        if not isinstance(token, str) or not token:
            raise InvalidTokenError("Missing or malformed token.")
        key = self._digest(token)
        session = self._sessions.get(key)
        if session is None:
            raise InvalidTokenError("Invalid token.")
        if self._clock() >= session.expires_at:
            del self._sessions[key]               # clean up expired session
            raise TokenExpiredError("Token has expired. Please log in again.")
        return session.username

    def revoke(self, token: str) -> None:
        """Log out: forget the token (no error if it is already gone)."""
        if isinstance(token, str):
            self._sessions.pop(self._digest(token), None)

    def purge_expired(self) -> None:
        """Drop all expired sessions to keep memory tidy."""
        now = self._clock()
        expired = [k for k, s in self._sessions.items() if now >= s.expires_at]
        for k in expired:
            del self._sessions[k]


# ---------------------------------------------------------------------------
# Bank
# ---------------------------------------------------------------------------
class Bank:
    """Manages users, accounts and token-protected banking operations."""

    _GENERIC_LOGIN_ERROR = "Invalid username or password."

    def __init__(self, name: str = "PyBank", token_ttl: int = DEFAULT_TOKEN_TTL,
                 clock: Callable[[], float] = time.time):
        self.name = name
        self._users: Dict[str, User] = {}
        self._accounts: Dict[str, Account] = {}
        self._sessions = SessionManager(token_ttl, clock)
        self._id_counter = count(1001)
        self._lock = threading.RLock()   # keeps multi-step operations consistent

    # ---- registration & authentication ------------------------------------
    @staticmethod
    def _normalize(username: str) -> str:
        return username.strip().lower() if isinstance(username, str) else ""

    def register(self, username: str, password: str, initial_balance: Money = 0) -> Account:
        """
        Register a new user AND open their first account in one step.
        Everything is validated before anything is stored.
        """
        key = self._normalize(username)
        if not USERNAME_PATTERN.match(key):
            raise InvalidUsernameError(
                "Username must be 3-32 characters: letters, digits or underscore."
            )
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise WeakPasswordError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
        to_money(initial_balance, allow_zero=True)   # validate before creating anything

        with self._lock:
            if key in self._users:
                raise UserAlreadyExistsError(f"Username '{key}' is already taken.")
            user = User.create(key, password)
            self._users[key] = user
            return self._create_account(user, initial_balance)

    def login(self, username: str, password: str) -> str:
        """Verify credentials and return a new session token."""
        user = self._users.get(self._normalize(username))
        if user is None:
            # Do equal work so timing doesn't reveal whether the username exists.
            hash_password(password if isinstance(password, str) else "", _DUMMY_SALT)
            raise AuthenticationError(self._GENERIC_LOGIN_ERROR)
        if not user.verify_password(password):
            raise AuthenticationError(self._GENERIC_LOGIN_ERROR)
        return self._sessions.issue(user.username)

    def logout(self, token: str) -> None:
        """Invalidate a token immediately."""
        self._sessions.revoke(token)

    # ---- internal helpers --------------------------------------------------
    def _create_account(self, user: User, initial_balance: Money = 0) -> Account:
        account_id = f"ACC-{next(self._id_counter)}"
        account = Account(account_id, user.username, initial_balance)
        self._accounts[account_id] = account
        user._link_account(account_id)
        return account

    def _authenticate(self, token: str) -> User:
        """Token -> User, or raise InvalidTokenError / TokenExpiredError."""
        username = self._sessions.validate(token)
        return self._users[username]

    def _owned_account(self, user: User, account_id: str) -> Account:
        """
        Return the account only if this user owns it. The same error is used for
        'not yours' and 'does not exist', so IDs can't be probed.
        """
        if not user.owns(account_id):
            raise AuthorizationError(f"You do not have access to account '{account_id}'.")
        return self._accounts[account_id]

    def _get_account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError:
            raise AccountNotFoundError(f"Account '{account_id}' does not exist.")

    # ---- token-protected banking operations ------------------------------
    def open_account(self, token: str, initial_balance: Money = 0) -> Account:
        """Open an additional account for the logged-in user."""
        with self._lock:
            user = self._authenticate(token)
            return self._create_account(user, initial_balance)

    def get_balance(self, token: str, account_id: str) -> Decimal:
        user = self._authenticate(token)
        return self._owned_account(user, account_id).balance

    def deposit(self, token: str, account_id: str, amount: Money) -> Transaction:
        with self._lock:
            user = self._authenticate(token)
            return self._owned_account(user, account_id).deposit(amount)

    def withdraw(self, token: str, account_id: str, amount: Money) -> Transaction:
        with self._lock:
            user = self._authenticate(token)
            return self._owned_account(user, account_id).withdraw(amount)

    def get_statement(self, token: str, account_id: str) -> List[Transaction]:
        user = self._authenticate(token)
        return self._owned_account(user, account_id).get_statement()

    def transfer(self, token: str, sender_id: str, receiver_id: str, amount: Money) -> None:
        """Transfer from one of YOUR accounts to any existing account."""
        with self._lock:
            user = self._authenticate(token)
            self._owned_account(user, sender_id)     # authorization check
            self._process_transfer(sender_id, receiver_id, amount)

    def _process_transfer(self, sender_id: str, receiver_id: str, amount: Money) -> None:
        """
        All-or-nothing transfer:
          1. Validate the amount and sender.
          2. Deduct from sender (raises if funds are insufficient).
          3. In try/except: find receiver and deposit.
          4. On ANY failure in step 3, roll the sender back and re-raise.
        """
        amount = to_money(amount)
        if sender_id == receiver_id:
            raise InvalidTransferError("Sender and receiver must be different accounts.")

        sender = self._get_account(sender_id)
        snapshot = sender._snapshot()
        sender.withdraw(amount, tx_type="TRANSFER_OUT")

        try:
            receiver = self._get_account(receiver_id)   # may raise AccountNotFoundError
            receiver.deposit(amount, tx_type="TRANSFER_IN")
        except Exception:
            sender._restore(snapshot)                   # ROLLBACK
            raise


# ---------------------------------------------------------------------------
# Demo / tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    class FakeClock:
        """Controllable clock so we can 'fast-forward' to test token expiry."""
        def __init__(self):
            self.now = 1_000_000.0
        def __call__(self):
            return self.now
        def advance(self, seconds):
            self.now += seconds

    def attempt(label, func, *args):
        """Run an operation; print OK or the error it raised. Returns the result."""
        try:
            result = func(*args)
            print(f"[OK]   {label}")
            return result
        except BankError as e:
            print(f"[FAIL] {label} -> {type(e).__name__}: {e}")

    clock = FakeClock()
    bank = Bank("DemoBank", token_ttl=900, clock=clock)   # 15-minute tokens

    print("=== Registration ===")
    ali_acc = attempt("Register 'Ali' with 1000.00", bank.register, "Ali", "S3cure-Pass!", "1000.00")
    sara_acc = attempt("Register 'Sara' with 250.50", bank.register, "Sara", "An0ther-Pass!", "250.50")
    attempt("Register duplicate username", bank.register, "ali", "Whatever123")
    attempt("Register weak password", bank.register, "bob", "123")
    attempt("Register bad username", bank.register, "x!", "LongEnough123")
    attempt("Register invalid opening balance", bank.register, "bob", "LongEnough123", "-5")
    print(f"Ali -> {ali_acc.account_id} | Sara -> {sara_acc.account_id}\n")

    print("=== Login ===")
    attempt("Login with wrong password", bank.login, "ali", "wrong-password")
    attempt("Login with unknown user", bank.login, "ghost", "whatever-pass")
    ali_token = attempt("Login Ali", bank.login, "ali", "S3cure-Pass!")
    sara_token = attempt("Login Sara", bank.login, "sara", "An0ther-Pass!")
    print(f"Ali's token (shown once): {ali_token[:12]}...")
    print(f"Plain token stored in memory? {ali_token in bank._sessions._sessions} "
          f"(only its SHA-256 hash is kept)\n")

    print("=== Token-protected operations ===")
    attempt("Ali deposits 500.25", bank.deposit, ali_token, ali_acc.account_id, "500.25")
    attempt("Ali withdraws 200", bank.withdraw, ali_token, ali_acc.account_id, 200)
    attempt("Ali withdraws 99999 (too much)", bank.withdraw, ali_token, ali_acc.account_id, 99999)
    attempt("Ali deposits -50", bank.deposit, ali_token, ali_acc.account_id, -50)
    attempt("Ali transfers 300 -> Sara", bank.transfer, ali_token, ali_acc.account_id, sara_acc.account_id, 300)
    print(f"Ali: {bank.get_balance(ali_token, ali_acc.account_id)} | "
          f"Sara: {bank.get_balance(sara_token, sara_acc.account_id)}\n")

    print("=== Security failures ===")
    attempt("Operation with fake token", bank.deposit, "not-a-real-token", ali_acc.account_id, 10)
    attempt("Operation with no token", bank.deposit, None, ali_acc.account_id, 10)
    attempt("Ali withdraws from SARA's account", bank.withdraw, ali_token, sara_acc.account_id, 10)
    attempt("Ali views SARA's statement", bank.get_statement, ali_token, sara_acc.account_id)
    attempt("Ali transfers FROM Sara's account", bank.transfer, ali_token, sara_acc.account_id, ali_acc.account_id, 10)

    print("\n=== Atomic rollback ===")
    before = bank.get_balance(ali_token, ali_acc.account_id)
    attempt("Transfer to NON-EXISTENT receiver", bank.transfer, ali_token, ali_acc.account_id, "ACC-9999", 100)
    after = bank.get_balance(ali_token, ali_acc.account_id)
    print(f"Ali before: {before} | after: {after} -> rolled back: {before == after}")
    attempt("Transfer to self", bank.transfer, ali_token, ali_acc.account_id, ali_acc.account_id, 10)

    print("\n=== Extra account ===")
    second = attempt("Ali opens a second account with 50", bank.open_account, ali_token, 50)
    print(f"Ali's accounts: {bank._users['ali'].account_ids}")

    print("\n=== Logout & expiry ===")
    attempt("Sara logs out", bank.logout, sara_token)
    attempt("Sara uses token after logout", bank.get_balance, sara_token, sara_acc.account_id)
    clock.advance(901)   # jump past the 15-minute TTL
    attempt("Ali uses token after 901s (expired)", bank.get_balance, ali_token, ali_acc.account_id)
    ali_token = attempt("Ali logs in again", bank.login, "ali", "S3cure-Pass!")

    print("\n=== Statement ===")
    for tx in bank.get_statement(ali_token, ali_acc.account_id):
        print(tx)
