import os
import time
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
ts = time.gmtime()
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    person = db.execute("SELECT Symbol, Name, Shares, Price, TOTAL FROM stocks WHERE id = :userid", userid=session["user_id"])
    length = len(person)
    money = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
    cash = money[0]["cash"]
    print(cash)
    return render_template("index.html", length=length, person=person, money=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("quote"):
            return apology("Missing Symbol", 403)

        quoter = lookup(request.form.get("quote"))
        if not quoter:
            return apology("Invalid Symbol", 403)
        amount = request.form.get("shares")
        if amount == '':
            return apology("Must contain at least 1 input")
        if amount.isdigit():
            amount = float(amount)
            if amount < 1:
                return apology("Invalid input")
        else:
            return apology("Invalid input")
        payment = round(amount * quoter["price"], 3)
        person = db.execute("SELECT * FROM users WHERE id = :username;", username=session["user_id"])
        asset = person[0]["cash"]
        if payment > asset:
            return apology("Insufficient funds", 403)
        remaining = asset - payment
        db.execute("UPDATE users SET Cash = :remaining WHERE id = :userid", remaining=remaining, userid=session["user_id"])
        person1 = db.execute("SELECT * FROM stocks WHERE id = :username;", username=session["user_id"])
        if len(person) != 1:
            db.execute("INSERT INTO stocks (id, Symbol, Name, Shares, Price, TOTAL) VALUES (:userid, :symbol, :name, :shares, :price, :total)",userid=session["user_id"], symbol=quoter["symbol"], name=quoter["name"], shares=amount, price=quoter["price"], total=payment)
        firsty = db.execute("SELECT * FROM stocks WHERE id = :userid AND Symbol = :symbol", userid=session["user_id"], symbol = quoter["symbol"])
        if len(firsty) != 1:
            db.execute("INSERT INTO stocks (id, Symbol, Name, Shares, Price, TOTAL) VALUES (:userid, :symbol, :name, :shares, :price, :total)",userid=session["user_id"], symbol=quoter["symbol"], name=quoter["name"], shares=amount, price=quoter["price"], total=payment)
        else:
            db.execute("UPDATE stocks  SET Shares = :shares, Price = :price, TOTAL = :total WHERE id = :userid AND symbol = :symbol", shares=amount+firsty[0]["Shares"], price=quoter["price"], total=payment+person1[0]["TOTAL"], userid=session["user_id"], symbol=quoter["symbol"])
        db.execute("INSERT INTO history (id, symbol, buy_sell, shares, price, transacted) VALUES (:userid, :symbol, :mode, :shares, :price, :time)",userid=session["user_id"], symbol=quoter["symbol"], mode="Buy", shares=amount, price=quoter["price"], time=time.strftime("%Y-%m-%d %H:%M:%S", ts))
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    person = db.execute("SELECT symbol, buy_sell, shares, price, transacted FROM history WHERE id = :userid", userid=session["user_id"])
    length = len(person)
    return render_template("history.html", length=length, person=person)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        money = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        cash = money[0]["cash"]
        amount = request.form.get("amount")
        if amount == '':
            return apology("Must contain at least 1 input")
        if amount.isdigit():
            amount = float(amount)
            if amount < 1:
                return apology("Invalid input")
        else:
            return apology("Invalid input")
        final = cash + amount
        db.execute("UPDATE users  SET cash = :total WHERE id = :userid", total=final, userid=session["user_id"])
        db.execute("INSERT INTO history (id, symbol, buy_sell, shares, price, transacted) VALUES (:userid, :symbol, :mode, :shares, :price, :time)",userid=session["user_id"], symbol="None", mode="Add Money", shares=0, price=amount, time=time.strftime("%Y-%m-%d %H:%M:%S", ts))
        return redirect("/")
    else:
        return render_template("add.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Show quotes"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("quote"):
            return apology("Missing Symbol", 403)

        quoter = lookup(request.form.get("quote"))
        if not quoter:
            return apology("Invalid Symbol", 403)
        # Redirect user to home page
        return render_template("quoted.html", name=quoter["name"], symbol=quoter["symbol"], price=quoter["price"])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        name = request.form.get("username")
        taken_name = db.execute("SELECT * FROM users WHERE username = :username;", username=request.form.get("username"))
        namae = taken_name[0]["username"]
        print(taken_name[0]["username"])
        if not name:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password same as confirm password
        elif request.form.get("password") != request.form.get("password_confirm"):
            return apology("password must be same", 403)

        elif namae == name:
            return apology("username must be unique", 403)
        else:
            hasher = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :password);", username=request.form.get("username"), password=hasher)
            session["user_id"] = request.form.get("username")
            return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # Ensure username was submitted
        person = db.execute("SELECT * FROM users WHERE id = :username;", username=session["user_id"])
        stocks = db.execute("SELECT * FROM stocks WHERE id = :userid", userid=session["user_id"])
        amount = int(request.form.get("shares"))
        availed = int(stocks[0]['Shares'])
        if amount == '':
            return apology("Must contain at least 1 input")
        elif amount < 1:
                return apology("Amount cannot be negative")
        elif amount > availed:
            return apology("You don't have too much in your possession")
        quoter = lookup(request.form.get("symbol"))
        payment = round(amount * quoter["price"], 3)
        asset = person[0]["cash"]
        remaining = asset + payment
        db.execute("UPDATE users SET Cash = :remaining WHERE id = :userid", remaining=remaining, userid=session["user_id"])
        firsty = db.execute("SELECT * FROM stocks WHERE id = :userid AND Symbol = :symbol", userid=session["user_id"], symbol = quoter["symbol"])
        db.execute("UPDATE stocks  SET Shares = :shares, Price = :price, TOTAL = :total WHERE id = :userid AND symbol = :symbol", shares=firsty[0]["Shares"]-amount, price=quoter["price"], total=firsty[0]["TOTAL"]-payment, userid=session["user_id"], symbol=quoter["symbol"])
        db.execute("INSERT INTO history (id, symbol, buy_sell, shares, price, transacted) VALUES (:userid, :symbol, :mode, :shares, :price, :time)",userid=session["user_id"], symbol=quoter["symbol"], mode="Sell", shares=amount, price=quoter["price"], time=time.strftime("%Y-%m-%d %H:%M:%S", ts))
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        person = db.execute("SELECT * FROM stocks WHERE id = :userid", userid=session["user_id"])
        length = len(person)
        return render_template("sell.html", length=length, person=person)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
