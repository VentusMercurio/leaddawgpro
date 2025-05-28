# app/routes.py
from flask import Blueprint, request, jsonify
from app import db # Import the db instance
from app.models import User # Import the User model
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

# If you decide to make a separate auth blueprint:
# auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
# For now, let's add to the existing bp, assuming it will be /api/auth/...
# Or, better, let's make this a dedicated auth blueprint.

# Create a new blueprint for authentication routes
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify(message="No input data provided"), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify(message="Username, email, and password are required"), 400

    if User.query.filter_by(username=username).first():
        return jsonify(message="Username already exists"), 409 # 409 Conflict
    
    if User.query.filter_by(email=email).first():
        return jsonify(message="Email already registered"), 409

    # Basic validation (can be enhanced with WTForms or Marshmallow later)
    if len(password) < 8:
        return jsonify(message="Password must be at least 8 characters long"), 400
    # You can add more validation for username and email format if needed

    new_user = User(username=username, email=email)
    new_user.set_password(password) # Hashes the password
    
    try:
        db.session.add(new_user)
        db.session.commit()
        # Optionally log the user in immediately after registration
        login_user(new_user) 
        return jsonify(message="User registered successfully", user={'id': new_user.id, 'username': new_user.username}), 201 # 201 Created
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during registration: {e}") # Requires from flask import current_app
        return jsonify(message="Registration failed due to an internal error"), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify(message="No input data provided"), 400

    identifier = data.get('identifier') # Can be username or email
    password = data.get('password')

    if not identifier or not password:
        return jsonify(message="Username/email and password are required"), 400

    # Try to find user by username or email
    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

    if user and user.check_password(password):
        login_user(user, remember=data.get('remember', False)) # 'remember' can be a checkbox on frontend
        # current_user will now be set
        return jsonify(message="Login successful", user={'id': current_user.id, 'username': current_user.username}), 200
    else:
        return jsonify(message="Invalid username/email or password"), 401 # 401 Unauthorized


@auth_bp.route('/logout', methods=['POST'])
@login_required # Ensures only logged-in users can logout
def logout():
    logout_user()
    return jsonify(message="Logout successful"), 200


@auth_bp.route('/status', methods=['GET'])
@login_required # Example of a protected route
def status():
    # current_user is provided by Flask-Login
    return jsonify(
        logged_in=True, 
        user={'id': current_user.id, 'username': current_user.username, 'email': current_user.email}
    ), 200

# This is your old hello route, can be kept or removed
# If you keep it, it needs to be on a different blueprint or have a different name
# Let's assume you want to keep your general API blueprint separate.
# We'll need to adjust app/__init__.py

# Remove or comment out the old 'bp' definition if creating 'auth_bp'
# from flask import Blueprint, jsonify
# bp = Blueprint('main', __name__, url_prefix='/api')
# @bp.route('/hello', methods=['GET'])
# def hello():
#     return jsonify(message="Hello from LeadDawg Pro Backend!")