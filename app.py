from flask import Flask, render_template, request, redirect, url_for, flash
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
import json, uuid, os

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "library_state.json"

# ---------------- Data Classes ----------------
@dataclass
class Book:
    isbn: str
    title: str
    authors: List[str]
    total_copies: int = 1
    available_copies: int = 1
    pub_year: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    def to_dict(self): return asdict(self)

@dataclass
class Member:
    member_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    joined_on: str = field(default_factory=lambda: date.today().isoformat())
    def to_dict(self): return asdict(self)

@dataclass
class Transaction:
    txn_id: str
    member_id: str
    isbn: str
    issued_on: str
    due_on: str
    returned_on: Optional[str] = None
    fine_paid: float = 0.0
    def to_dict(self): return asdict(self)

# ---------------- Core Library ----------------
class Library:
    def __init__(self, fine_per_day: float = 1.0):
        self.books: Dict[str, Book] = {}
        self.members: Dict[str, Member] = {}
        self.transactions: Dict[str, Transaction] = {}
        self.fine_per_day = fine_per_day

    def add_book(self, isbn, title, authors, copies=1, pub_year=None, tags=None):
        tags = tags or []
        if isbn in self.books:
            b = self.books[isbn]
            b.total_copies += copies
            b.available_copies += copies
        else:
            self.books[isbn] = Book(isbn, title, authors, copies, copies, pub_year, tags)

    def add_member(self, name, email=None, phone=None):
        m = Member(member_id=str(uuid.uuid4()), name=name, email=email, phone=phone)
        self.members[m.member_id] = m
        return m

    def issue_book(self, member_id, isbn, days=14):
        if isbn not in self.books or member_id not in self.members:
            raise Exception("Invalid member or book.")
        b = self.books[isbn]
        if b.available_copies <= 0:
            raise Exception("Book not available.")
        txn = Transaction(
            txn_id=str(uuid.uuid4()),
            member_id=member_id,
            isbn=isbn,
            issued_on=date.today().isoformat(),
            due_on=(date.today() + timedelta(days=days)).isoformat()
        )
        b.available_copies -= 1
        self.transactions[txn.txn_id] = txn
        return txn

    def return_book(self, txn_id):
        t = self.transactions[txn_id]
        if t.returned_on:
            raise Exception("Already returned.")
        today = date.today()
        due = datetime.fromisoformat(t.due_on).date()
        fine = max(0, (today - due).days) * self.fine_per_day if today > due else 0
        t.returned_on = today.isoformat()
        t.fine_paid = fine
        self.books[t.isbn].available_copies += 1
        return fine

    def to_dict(self):
        return {
            "books": {i: b.to_dict() for i, b in self.books.items()},
            "members": {m: x.to_dict() for m, x in self.members.items()},
            "transactions": {t: x.to_dict() for t, x in self.transactions.items()}
        }

    def save(self, path=DATA_FILE):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path=DATA_FILE):
        lib = cls()
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            for i, b in data.get("books", {}).items():
                lib.books[i] = Book(**b)
            for m, x in data.get("members", {}).items():
                lib.members[m] = Member(**x)
            for t, x in data.get("transactions", {}).items():
                lib.transactions[t] = Transaction(**x)
        return lib

# ---------------- Routes ----------------
lib = Library.load()

@app.route("/")
def index():
    return render_template("index.html", books=len(lib.books), members=len(lib.members), txns=len(lib.transactions))

@app.route("/books")
def books():
    return render_template("books.html", books=lib.books.values())

@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        isbn = request.form["isbn"]
        title = request.form["title"]
        authors = request.form["authors"].split(",")
        copies = int(request.form.get("copies", 1))
        lib.add_book(isbn, title, authors, copies)
        lib.save()
        flash("Book added successfully!")
        return redirect(url_for("books"))
    return render_template("add_book.html")

@app.route("/members")
def members():
    return render_template("members.html", members=lib.members.values())

@app.route("/add_member", methods=["GET", "POST"])
def add_member():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form.get("email")
        phone = request.form.get("phone")
        lib.add_member(name, email, phone)
        lib.save()
        flash("Member added!")
        return redirect(url_for("members"))
    return render_template("add_member.html")

@app.route("/issue", methods=["GET", "POST"])
def issue():
    if request.method == "POST":
        mid = request.form["member_id"]
        isbn = request.form["isbn"]
        try:
            txn = lib.issue_book(mid, isbn)
            lib.save()
            flash(f"Issued successfully. Txn ID: {txn.txn_id}")
        except Exception as e:
            flash(str(e))
        return redirect(url_for("transactions"))
    return render_template("issue.html", books=lib.books.values(), members=lib.members.values())

@app.route("/return", methods=["GET", "POST"])
def return_book():
    if request.method == "POST":
        txn_id = request.form["txn_id"]
        try:
            fine = lib.return_book(txn_id)
            lib.save()
            flash(f"Book returned. Fine: ₹{fine}")
        except Exception as e:
            flash(str(e))
        return redirect(url_for("transactions"))
    return render_template("return.html", txns=lib.transactions.values())

@app.route("/transactions")
def transactions():
    return render_template("transactions.html", txns=lib.transactions.values(), lib=lib)

if __name__ == "__main__":
    app.run(debug=True)
