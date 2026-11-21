import base64
import html
import io
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, abort, flash, g, make_response, redirect, render_template,
    request, session, url_for,
)
from flask_wtf import CSRFProtect
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv()

MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
LAYOUTS = {"row", "staggered", "two-rows"}
PAPER_SIZES = {"letter-landscape", "letter-portrait", "square"}
MAX_SPROUTS = 7
MAX_NAME_LENGTH = 18

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
if os.environ.get("FLASK_ENV") == "production" and not os.environ.get("FLASK_SECRET_KEY"):
    raise RuntimeError("FLASK_SECRET_KEY must be set in production")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    DATABASE=os.environ.get("NAMESPROUTS_DATABASE", os.path.join(app.instance_path, "namesprouts.db")),
    STRIPE_SECRET_KEY=os.environ.get("STRIPE_SECRET_KEY"),
    STRIPE_WEBHOOK_SECRET=os.environ.get("STRIPE_WEBHOOK_SECRET"),
    DESIGN_PRICE_CENTS=int(os.environ.get("DESIGN_PRICE_CENTS", "500")),
)
csrf = CSRFProtect(app)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    if "_database" not in g:
        g._database = sqlite3.connect(app.config["DATABASE"])
        g._database.row_factory = sqlite3.Row
        g._database.execute("PRAGMA foreign_keys = ON")
    return g._database


@app.teardown_appcontext
def close_db(_exception):
    db = g.pop("_database", None)
    if db:
        db.close()


def init_db():
    database_directory = os.path.dirname(app.config["DATABASE"])
    if database_directory:
        os.makedirs(database_directory, exist_ok=True)
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS designs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            layout TEXT NOT NULL,
            paper_size TEXT NOT NULL,
            sprouts_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            approved_at TEXT,
            paid_at TEXT,
            checkout_session_id TEXT UNIQUE,
            amount_paid INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    db.commit()


@app.before_request
def prepare_database():
    if not app.extensions.get("namesprouts_schema_ready"):
        init_db()
        app.extensions["namesprouts_schema_ready"] = True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            session["next_url"] = request.full_path
            flash("Create a free account or sign in to save your proof.", "info")
            return redirect(url_for("register"))
        return view(*args, **kwargs)
    return wrapped


def owner_design(design_id):
    design = get_db().execute(
        "SELECT * FROM designs WHERE id = ? AND user_id = ?",
        (design_id, session.get("user_id")),
    ).fetchone()
    if design is None:
        abort(404)
    return design


def validate_sprouts(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SPROUTS:
        raise ValueError("Add between 1 and 7 flowers to your proof.")
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("One of the flower details is invalid.")
        name = str(item.get("name", "")).strip()
        month = str(item.get("month", "")).lower()
        if not name or len(name) > MAX_NAME_LENGTH or not any(character.isalpha() for character in name):
            raise ValueError("Each name must be 1 to 18 characters and include a letter.")
        if month not in MONTHS:
            raise ValueError("Choose a valid birth month for every flower.")
        cleaned.append({"name": name, "month": month})
    return cleaned


def load_sprouts(design):
    return json.loads(design["sprouts_json"])


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not username or len(username) > 40 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            flash("Enter a username and a valid email address.", "error")
            return render_template("register.html"), 400
        if len(password) < 8 or len(password) > 200:
            flash("Choose a password between 8 and 200 characters.", "error")
            return render_template("register.html"), 400
        try:
            db = get_db()
            db.execute(
                "INSERT INTO users (username, email, hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("That username or email is already in use. Try signing in.", "error")
            return render_template("register.html"), 409
        user = get_db().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = username
        session.permanent = True
        flash("Your free NameSprouts account is ready.", "success")
        return redirect(url_for("design"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not user or not check_password_hash(user["hash"], password):
            flash("Username or password was not recognized.", "error")
            return render_template("login.html"), 401
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session.permanent = True
        return redirect(url_for("projects"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/design")
def design():
    initial_design = None
    design_id = request.args.get("design_id", "")
    if design_id.isdigit():
        if "user_id" not in session:
            session["next_url"] = request.full_path
            return redirect(url_for("login"))
        saved_design = owner_design(int(design_id))
        initial_design = {
            "id": saved_design["id"],
            "title": saved_design["title"],
            "layout": saved_design["layout"],
            "paper_size": saved_design["paper_size"],
            "sprouts": load_sprouts(saved_design),
        }
    return render_template(
        "design.html",
        months=MONTHS,
        max_sprouts=MAX_SPROUTS,
        design_price=app.config["DESIGN_PRICE_CENTS"] / 100,
        initial_design=initial_design,
    )


@app.route("/design/save", methods=["POST"])
@login_required
def save_design():
    try:
        sprouts = validate_sprouts(json.loads(request.form.get("sprouts_json", "[]")))
    except (ValueError, json.JSONDecodeError) as error:
        flash(str(error), "error")
        return redirect(url_for("design"))

    layout = request.form.get("layout", "row")
    paper_size = request.form.get("paper_size", "letter-landscape")
    if layout not in LAYOUTS or paper_size not in PAPER_SIZES:
        flash("Choose a valid layout and paper size.", "error")
        return redirect(url_for("design"))
    title = request.form.get("title", "").strip()[:80] or "My NameSprouts"
    design_id = request.form.get("design_id", "").strip()
    now = utc_now()
    db = get_db()
    if design_id.isdigit():
        existing = db.execute(
            "SELECT id, status FROM designs WHERE id = ? AND user_id = ?",
            (int(design_id), session["user_id"]),
        ).fetchone()
        if existing and existing["status"] != "paid":
            db.execute(
                """UPDATE designs SET title = ?, layout = ?, paper_size = ?,
                   sprouts_json = ?, status = 'draft', approved_at = NULL,
                   paid_at = NULL, amount_paid = NULL, checkout_session_id = NULL,
                   updated_at = ? WHERE id = ? AND user_id = ?""",
                (title, layout, paper_size, json.dumps(sprouts), now, int(design_id), session["user_id"]),
            )
            saved_id = int(design_id)
        else:
            saved_id = None
    else:
        saved_id = None
    if saved_id is None:
        cursor = db.execute(
            """INSERT INTO designs
               (user_id, title, layout, paper_size, sprouts_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session["user_id"], title, layout, paper_size, json.dumps(sprouts), now, now),
        )
        saved_id = cursor.lastrowid
    db.commit()
    return redirect(url_for("proof", design_id=saved_id))


@app.route("/proof/<int:design_id>")
@login_required
def proof(design_id):
    design = owner_design(design_id)
    return render_template(
        "proof.html",
        design=design,
        sprouts=load_sprouts(design),
        price=app.config["DESIGN_PRICE_CENTS"] / 100,
        stripe_ready=bool(app.config["STRIPE_SECRET_KEY"]),
    )


@app.route("/proof/<int:design_id>/approve", methods=["POST"])
@login_required
def approve_proof(design_id):
    design = owner_design(design_id)
    if design["status"] == "paid":
        return redirect(url_for("proof", design_id=design_id))
    get_db().execute(
        """UPDATE designs SET status = 'approved', approved_at = ?, updated_at = ?
           WHERE id = ? AND user_id = ?""",
        (utc_now(), utc_now(), design_id, session["user_id"]),
    )
    get_db().commit()
    flash("Proof approved. Pay once to unlock your print-ready download.", "success")
    return redirect(url_for("proof", design_id=design_id))


@app.route("/proof/<int:design_id>/checkout", methods=["POST"])
@login_required
def checkout(design_id):
    design = owner_design(design_id)
    if design["status"] not in {"approved", "paid"}:
        flash("Review and approve your proof before checkout.", "error")
        return redirect(url_for("proof", design_id=design_id))
    if design["status"] == "paid":
        return redirect(url_for("download_pdf", design_id=design_id))
    if not app.config["STRIPE_SECRET_KEY"]:
        flash("Online checkout is not configured yet. Your proof is saved and ready.", "info")
        return redirect(url_for("proof", design_id=design_id))
    try:
        import stripe
        stripe.api_key = app.config["STRIPE_SECRET_KEY"]
        if design["checkout_session_id"]:
            previous_session = stripe.checkout.Session.retrieve(design["checkout_session_id"])
            if previous_session.get("status") == "open":
                return redirect(previous_session.url, code=303)
            mark_design_paid(previous_session)
            latest = get_db().execute(
                "SELECT status FROM designs WHERE id = ? AND user_id = ?",
                (design_id, session["user_id"]),
            ).fetchone()
            if latest and latest["status"] == "paid":
                return redirect(url_for("download_pdf", design_id=design_id))
            if previous_session.get("status") == "complete":
                flash("Your payment is processing. We will unlock the download as soon as Stripe confirms it.", "info")
                return redirect(url_for("proof", design_id=design_id))
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"NameSprouts printable — {design['title']}"},
                    "unit_amount": app.config["DESIGN_PRICE_CENTS"],
                },
                "quantity": 1,
            }],
            customer_email=get_db().execute(
                "SELECT email FROM users WHERE id = ?", (session["user_id"],)
            ).fetchone()["email"],
            client_reference_id=str(design_id),
            metadata={"design_id": str(design_id), "user_id": str(session["user_id"])},
            success_url=url_for("payment_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("proof", design_id=design_id, _external=True),
        )
    except Exception as error:
        app.logger.exception("Unable to create Stripe Checkout session: %s", error)
        flash("Checkout could not be started. Please try again later.", "error")
        return redirect(url_for("proof", design_id=design_id))
    get_db().execute(
        "UPDATE designs SET checkout_session_id = ?, updated_at = ? WHERE id = ?",
        (checkout_session.id, utc_now(), design_id),
    )
    get_db().commit()
    return redirect(checkout_session.url, code=303)


def mark_design_paid(checkout_session):
    metadata = checkout_session.get("metadata") or {}
    design_id = metadata.get("design_id")
    user_id = metadata.get("user_id")
    if (
        checkout_session.get("payment_status") != "paid"
        or checkout_session.get("mode") != "payment"
        or checkout_session.get("currency") != "usd"
        or checkout_session.get("amount_total") != app.config["DESIGN_PRICE_CENTS"]
        or not design_id
        or not user_id
    ):
        return
    get_db().execute(
        """UPDATE designs SET status = 'paid', paid_at = ?, amount_paid = ?, updated_at = ?
           WHERE id = ? AND user_id = ? AND checkout_session_id = ?""",
        (
            utc_now(), checkout_session.get("amount_total"), utc_now(),
            design_id, user_id, checkout_session.get("id"),
        ),
    )
    get_db().commit()


@app.route("/payment/success")
@login_required
def payment_success():
    session_id = request.args.get("session_id", "")
    if not session_id or not app.config["STRIPE_SECRET_KEY"]:
        flash("We could not confirm that payment. Your proof is still saved.", "error")
        return redirect(url_for("projects"))
    try:
        import stripe
        stripe.api_key = app.config["STRIPE_SECRET_KEY"]
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        metadata = checkout_session.get("metadata") or {}
        if metadata.get("user_id") != str(session["user_id"]):
            abort(404)
        mark_design_paid(checkout_session)
        design_id = int(metadata["design_id"])
    except Exception:
        app.logger.exception("Unable to verify Stripe Checkout session")
        flash("Payment confirmation is still processing. Your download will appear in My Designs.", "info")
        return redirect(url_for("projects"))
    design = get_db().execute(
        "SELECT status FROM designs WHERE id = ? AND user_id = ?",
        (design_id, session["user_id"]),
    ).fetchone()
    if design and design["status"] == "paid":
        flash("Payment confirmed. Your printable is ready to download.", "success")
    else:
        flash("Payment confirmation is still processing. Refresh this page shortly.", "info")
    return redirect(url_for("proof", design_id=design_id))


@app.route("/webhooks/stripe", methods=["POST"])
@csrf.exempt
def stripe_webhook():
    if not app.config["STRIPE_SECRET_KEY"] or not app.config["STRIPE_WEBHOOK_SECRET"]:
        abort(503)
    try:
        import stripe
        event = stripe.Webhook.construct_event(
            request.get_data(),
            request.headers.get("Stripe-Signature", ""),
            app.config["STRIPE_WEBHOOK_SECRET"],
        )
    except Exception as error:
        app.logger.warning("Rejected Stripe webhook: %s", error)
        abort(400)
    if event["type"] in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        mark_design_paid(event["data"]["object"])
    return "", 200


def page_dimensions(paper_size):
    return {
        "letter-landscape": (1100, 850),
        "letter-portrait": (850, 1100),
        "square": (1000, 1000),
    }[paper_size]


def page_inches(paper_size):
    return {
        "letter-landscape": (11, 8.5),
        "letter-portrait": (8.5, 11),
        "square": (10, 10),
    }[paper_size]


def image_data(relative_path):
    path = os.path.join(app.static_folder, relative_path)
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("ascii")


def transparent_flower_bytes(month):
    if month not in MONTHS:
        abort(404)
    cache = app.extensions.setdefault("flower_cutouts", {})
    if month in cache:
        return cache[month]
    source_path = os.path.join(app.static_folder, "flowers", f"{month}.png")
    with Image.open(source_path) as source:
        image = source.convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, _old_alpha = pixels[x, y]
            high, low = max(red, green, blue), min(red, green, blue)
            chroma = high - low
            light = (red + green + blue) / 3
            color_alpha = max(0, min(255, round((chroma - 18) * 10)))
            ink_alpha = max(0, min(255, round((170 - light) * 5)))
            petal_alpha = max(0, min(255, round((light - 208) * 6)))
            pixels[x, y] = (red, green, blue, max(color_alpha, ink_alpha, petal_alpha))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    cache[month] = output.getvalue()
    image.close()
    return cache[month]


@app.route("/flower.png")
def flower_image():
    month = request.args.get("month", "").lower()
    response = make_response(transparent_flower_bytes(month))
    response.headers["Content-Type"] = "image/png"
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


def register_print_font():
    try:
        from fontTools.ttLib import TTFont as OpenTypeFont
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont as ReportLabFont

        if "Allura" in pdfmetrics.getRegisteredFontNames():
            return
        font_directory = os.path.join(app.instance_path, "print-fonts")
        os.makedirs(font_directory, exist_ok=True)
        output_path = os.path.join(font_directory, "Allura-Regular.ttf")
        if not os.path.exists(output_path):
            source_path = os.path.join(app.static_folder, "fonts", "Allura-Regular.woff2")
            font = OpenTypeFont(source_path)
            font.flavor = None
            font.save(output_path)
        pdfmetrics.registerFont(ReportLabFont("Allura", output_path))
        pdfmetrics.registerFontFamily("Allura", normal="Allura", bold="Allura", italic="Allura", boldItalic="Allura")
    except Exception:
        app.logger.exception("Could not prepare the script font for PDF output")


def build_design_svg(design, watermark=False, embed_font=True):
    sprouts = load_sprouts(design)
    width, height = page_dimensions(design["paper_size"])
    page_data = image_data("images/watercolor-paper-bg.png")
    row_groups = []
    if design["layout"] == "two-rows" and len(sprouts) > 1:
        split = (len(sprouts) + 1) // 2
        row_groups = [(sprouts[:split], 0.28), (sprouts[split:], 0.70)]
        row_groups = [group for group in row_groups if group[0]]
    else:
        row_groups = [(sprouts, 0.49)]
    page_width, page_height = page_inches(design["paper_size"])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{page_width}in" height="{page_height}in" viewBox="0 0 {width} {height}">',
        f'<title>{html.escape(design["title"])}</title>',
        f'<image width="{width}" height="{height}" href="data:image/png;base64,{page_data}" preserveAspectRatio="xMidYMid slice"/>',
    ]
    if embed_font:
        font_data = image_data("fonts/Allura-Regular.woff2")
        parts.insert(
            2,
            f'<style>@font-face{{font-family:Allura;src:url(data:font/woff2;base64,{font_data}) format("woff2")}}</style>',
        )
    for group_items, center_y_ratio in row_groups:
        count = len(group_items)
        center_y = height * center_y_ratio
        slot_width = (width - 80) / count
        tile_width = min(235, slot_width + 26)
        tile_height = tile_width * 1.38
        top = center_y - tile_height * 0.49
        for index, sprout in enumerate(group_items):
            center_x = width * (index + 0.5) / count
            offset = 24 if design["layout"] == "staggered" and index % 2 else 0
            image_top = top + offset
            month_data = base64.b64encode(transparent_flower_bytes(sprout["month"])).decode("ascii")
            name = html.escape(sprout["name"])
            name_size = min(28, max(10, tile_height * 0.37 / max(len(sprout["name"]) * 0.56, 1)))
            name_y = image_top + tile_height * 0.82
            font_family = "Allura,cursive" if embed_font else "Allura"
            parts.append(
                f'<image x="{center_x - tile_width / 2:.1f}" y="{image_top:.1f}" '
                f'width="{tile_width:.1f}" height="{tile_height:.1f}" '
                f'href="data:image/png;base64,{month_data}" preserveAspectRatio="xMidYMax meet" '
                f'style="mix-blend-mode:multiply"/>'
            )
            parts.append(
                f'<text x="{center_x:.1f}" y="{name_y:.1f}" text-anchor="middle" dominant-baseline="middle" '
                f'font-family="{font_family}" font-size="{name_size:.1f}" '
                f'fill="#24231f" transform="rotate(-90 {center_x:.1f} {name_y:.1f})">{name}</text>'
            )
    if watermark:
        parts.append(
            f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" '
            f'font-family="Arial,sans-serif" font-size="44" letter-spacing="8" '
            f'fill="#35543c" fill-opacity=".24" transform="rotate(-24 {width / 2} {height / 2})">'
            'PROOF - NOT FOR PRINT</text>'
        )
    parts.append('</svg>')
    return ''.join(parts)


@app.route("/proof/<int:design_id>/artwork.svg")
@login_required
def proof_svg(design_id):
    design = owner_design(design_id)
    response = make_response(build_design_svg(design, watermark=design["status"] != "paid"))
    response.headers["Content-Type"] = "image/svg+xml; charset=utf-8"
    response.headers["Content-Disposition"] = "inline"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/proof/<int:design_id>/download")
@login_required
def download_pdf(design_id):
    design = owner_design(design_id)
    if design["status"] != "paid":
        flash("The print-ready download unlocks after payment.", "info")
        return redirect(url_for("proof", design_id=design_id))
    try:
        from reportlab.graphics import renderPDF
        from reportlab.pdfgen import canvas as pdf_canvas
        from svglib.svglib import svg2rlg
        register_print_font()
        svg_bytes = build_design_svg(design, embed_font=False).encode("utf-8")
        drawing = svg2rlg(io.BytesIO(svg_bytes))
        if drawing is None:
            raise ValueError("The printable could not be rendered.")
        pdf_buffer = io.BytesIO()
        paper_width, paper_height = page_inches(design["paper_size"])
        output = pdf_canvas.Canvas(pdf_buffer, pagesize=(paper_width * 72, paper_height * 72))
        renderPDF.draw(drawing, output, 0, 0)
        output.showPage()
        output.save()
    except Exception:
        app.logger.exception("Could not create print-ready PDF for design %s", design_id)
        flash("The PDF could not be generated right now. Please try again.", "error")
        return redirect(url_for("proof", design_id=design_id))
    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="namesprouts-{design_id}.pdf"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/projects")
@login_required
def projects():
    designs = get_db().execute(
        "SELECT * FROM designs WHERE user_id = ? ORDER BY updated_at DESC",
        (session["user_id"],),
    ).fetchall()
    return render_template("my_projects.html", designs=designs)


@app.route("/projects/<int:design_id>/delete", methods=["POST"])
@login_required
def delete_design(design_id):
    owner_design(design_id)
    get_db().execute("DELETE FROM designs WHERE id = ? AND user_id = ?", (design_id, session["user_id"]))
    get_db().commit()
    flash("Design deleted.", "success")
    return redirect(url_for("projects"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    return render_template("505.html"), 500

