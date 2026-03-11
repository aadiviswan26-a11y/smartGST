import os
import sys
import time
from werkzeug.utils import secure_filename

try:
    from flask import ( # pyright: ignore[reportMissingImports]
        Flask,
        request,
        jsonify,
        render_template,
        send_file,           # ← use send_file instead of send_from_directory
        redirect,
        url_for,
        flash,
        session
    )
    from flask_login import (
        LoginManager,
        login_user,
        login_required,
        logout_user,
        current_user
    )
    from flask_wtf import FlaskForm
    from wtforms import StringField, PasswordField, SubmitField, validators
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError as e:
    print(f"Error: Flask import failed. Please install Flask: pip install flask")
    raise

# ensure the package root is on sys.path when running `python app.py`
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.gst_engine import gst_calculation
from backend.history_manager import read_history
from backend.fraud_detector import check_fraud
from backend.pdfgenerator import generate_invoice
from models import User, init_db, get_user_by_email, create_user, verify_password, update_user

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for simplicity

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Initialize database
init_db()

class LoginForm(FlaskForm):
    email = StringField('Email', [validators.DataRequired(), validators.Email()])
    password = PasswordField('Password', [validators.DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    name = StringField('Full Name', [validators.DataRequired(), validators.Length(min=2, max=100)])
    email = StringField('Email', [validators.DataRequired(), validators.Email()])
    phone = StringField('Phone Number', [validators.DataRequired(), validators.Length(min=10, max=15)])
    password = PasswordField('Password', [validators.DataRequired(), validators.Length(min=6)])
    confirm_password = PasswordField('Confirm Password', [validators.DataRequired(), validators.EqualTo('password')])
    submit = SubmitField('Sign Up')

class ProfileForm(FlaskForm):
    name = StringField('Full Name', [validators.DataRequired(), validators.Length(min=2, max=100)])
    email = StringField('Email', [validators.DataRequired(), validators.Email()])
    phone = StringField('Phone Number', [validators.DataRequired(), validators.Length(min=10, max=15)])
    shop_name = StringField('Shop Name')
    shop_address = StringField('Shop Address')
    submit = SubmitField('Update Profile')

@app.route("/")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm()
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        print(f"\n[DEBUG LOGIN ROUTE] Email from form: '{email}'")
        print(f"[DEBUG LOGIN ROUTE] Password from form: '{password}'")
        
        if email and password:
            user = verify_password(email, password)
            if user:
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('home'))
            else:
                flash('Invalid email or password', 'error')
        else:
            flash('Please enter email and password', 'error')

    return render_template("login.html", form=form)

@app.route("/signup", methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = SignupForm()
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        print(f"\n[DEBUG SIGNUP] Email: {email}")
        print(f"[DEBUG SIGNUP] Name: {name}")
        print(f"[DEBUG SIGNUP] Phone: {phone}")
        
        if not email or not name or not phone or not password:
            flash('Please fill all fields', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            user = create_user(
                email=email,
                name=name,
                phone=phone,
                password=password
            )
            if user:
                print(f"[DEBUG SIGNUP] User created successfully: {user.email}")
                login_user(user)
                flash('Account created successfully!', 'success')
                return redirect(url_for('home'))
            else:
                print(f"[DEBUG SIGNUP] Failed to create user - email already exists")
                flash('Email already exists', 'error')

    return render_template("signup.html", form=form)

@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if request.method == 'GET':
        form.name.data = current_user.name
        form.email.data = current_user.email
        form.phone.data = current_user.phone
        form.shop_name.data = getattr(current_user, 'shop_name', '')
        form.shop_address.data = getattr(current_user, 'shop_address', '')

    if form.validate_on_submit():
        # Check if email is already taken by another user
        existing_user = get_user_by_email(form.email.data)
        if existing_user and existing_user.id != current_user.id:
            flash('Email already taken', 'error')
        else:
            update_user(
                current_user.id,
                name=form.name.data,
                email=form.email.data,
                phone=form.phone.data,
                shop_name=form.shop_name.data,
                shop_address=form.shop_address.data
            )
            # mirror changes on the current_user object so the page reload shows them
            current_user.name = form.name.data
            current_user.email = form.email.data
            current_user.phone = form.phone.data
            current_user.shop_name = form.shop_name.data
            current_user.shop_address = form.shop_address.data

            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))

    return render_template("profile.html", form=form)

@app.route("/upload_profile_pic", methods=['POST'])
@login_required
def upload_profile_pic():
    if 'profile_pic' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('profile'))

    file = request.files['profile_pic']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('profile'))

    if file and allowed_file(file.filename):
        # Create profile_pics directory if it doesn't exist
        profile_pics_dir = os.path.join(app.static_folder, 'profile_pics')
        os.makedirs(profile_pics_dir, exist_ok=True)

        # Generate unique filename
        filename = f"user_{current_user.id}_{int(time.time())}_{secure_filename(file.filename)}"
        file_path = os.path.join(profile_pics_dir, filename)

        # Save the file
        file.save(file_path)

        # Update user profile picture in database
        update_user(current_user.id, profile_pic=filename)

        # Update current user object
        current_user.profile_pic = filename

        flash('Profile picture updated successfully!', 'success')
    else:
        flash('Invalid file type. Please upload an image.', 'error')

    return redirect(url_for('profile'))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route("/calculate", methods=["POST"])
@login_required
def calculate():
    data = request.get_json(force=True, silent=True) or {}

    # Check if it's the new multi-item format or old single item format
    if "items" in data:
        # New multi-item format
        items = data.get("items", [])
        gst_type = data.get("gst_type", "exclusive")
        gst_category = data.get("gst_category", "cgst_sgst")

        if not items or len(items) == 0:
            return jsonify({"error": "No items provided"}), 400

        total_subtotal = 0
        processed_items = []
        overall_rate = None
        overall_category = None

        for item in items:
            product = item.get("product", "").strip()
            quantity = item.get("quantity", 1)
            unit_price = item.get("unit_price", 0)

            try:
                unit_price = float(unit_price)
                quantity = int(quantity)
            except Exception:
                return jsonify({"error": "Invalid price or quantity"}), 400

            if not product or unit_price <= 0 or quantity <= 0:
                return jsonify({"error": "Invalid item data"}), 400

            # Calculate for this item
            try:
                result = gst_calculation(
                    product, unit_price, gst_type=gst_type, gst_category=gst_category
                )

                if isinstance(result, dict):
                    rate = result.get("rate")
                    gst_amount = result.get("gst")
                    item_total = result.get("total")
                    category = result.get("category", gst_category)
                else:
                    if len(result) == 4:
                        rate, gst_amount, item_total, category = result
                    elif len(result) == 3:
                        rate, gst_amount, item_total = result
                        category = gst_category
                    else:
                        raise ValueError("unexpected result from gst_calculation")

                # Use the first item's rate and category for overall calculation
                if overall_rate is None:
                    overall_rate = rate
                    overall_category = category

                item_subtotal = unit_price * quantity
                item_gst_total = gst_amount * quantity
                item_final_total = item_total * quantity

                processed_items.append({
                    "product": product,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total": item_subtotal,
                    "gst": item_gst_total,
                    "final_total": item_final_total
                })

                total_subtotal += item_subtotal

            except Exception as e:
                return jsonify({"error": f"Calculation failed for {product}", "detail": str(e)}), 500

        # Calculate overall GST based on total subtotal
        if gst_type == "exclusive":
            overall_gst = total_subtotal * (overall_rate / 100)
            overall_total = total_subtotal + overall_gst
        else:  # inclusive
            overall_total = total_subtotal
            overall_gst = total_subtotal - (total_subtotal / (1 + overall_rate / 100))

        return jsonify({
            "items": processed_items,
            "subtotal": total_subtotal,
            "rate": overall_rate,
            "gst": overall_gst,
            "total": overall_total,
            "category": overall_category
        })

    else:
        # Legacy single item format for backward compatibility
        product = data.get("product", "").strip()
        price_raw = data.get("price", "")
        gst_type = data.get("gst_type", "exclusive")
        gst_category = data.get("gst_category", "cgst_sgst")

        try:
            price = float(price_raw)
        except Exception:
            return jsonify({"error": "Invalid price"}), 400

        if not product or price <= 0:
            return jsonify({"error": "Invalid input"}), 400

        try:
            result = gst_calculation(
                product, price, gst_type=gst_type, gst_category=gst_category
            )

            if isinstance(result, dict):
                rate = result.get("rate")
                gst_amount = result.get("gst")
                total = result.get("total")
                category = result.get("category", gst_category)
            else:
                if len(result) == 4:
                    rate, gst_amount, total, category = result
                elif len(result) == 3:
                    rate, gst_amount, total = result
                    category = gst_category
                else:
                    raise ValueError("unexpected result from gst_calculation")
        except Exception as e:
            return jsonify({"error": "Calculation failed", "detail": str(e)}), 500

        return jsonify({
            "rate": rate,
            "gst": gst_amount,
            "total": total,
            "category": category
        })


@app.route("/history", methods=["GET"])
@login_required
def history():
    rows = read_history()
    return jsonify(rows)


@app.route("/api/check_fraud", methods=["POST"])
@login_required
def api_check_fraud():
    data = request.get_json(force=True, silent=True) or {}
    try:
        final = float(data.get("final", 0))
        billed = float(data.get("billed", 0))
    except Exception:
        return jsonify({"error": "Invalid numbers"}), 400

    result = check_fraud(final, billed)
    return jsonify({"result": result})


@app.route("/api/generate_invoice", methods=["POST"])
@login_required
def api_generate_invoice():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "").strip()
    items = data.get("items", None)
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        shop_info = {
            'name': getattr(current_user, 'shop_name', None),
            'address': getattr(current_user, 'shop_address', None),
            'phone': current_user.phone,
            'email': current_user.email
        }
        filename = generate_invoice(text, items, shop_info)
    except Exception as e:
        return jsonify({"error": "Failed to generate PDF", "detail": str(e)}), 500

    if not filename or not os.path.isfile(filename):
        return jsonify({"error": "PDF not found"}), 500

    # send_file happily accepts an absolute path and avoids the
    # “outside directory” checks
    return send_file(filename, as_attachment=True, mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")