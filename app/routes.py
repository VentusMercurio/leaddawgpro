# app/routes.py
from flask import Blueprint, request, jsonify, current_app # Added current_app
from app import db
from app.models import User, SavedLead # Ensure SavedLead is imported
from werkzeug.security import generate_password_hash, check_password_hash # Not used directly here but good to have for auth context
from flask_login import login_user, logout_user, login_required, current_user

# --- Authentication Blueprint ---
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data: return jsonify(message="No input data provided"), 400
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not username or not email or not password: return jsonify(message="Username, email, and password are required"), 400
    if User.query.filter_by(username=username).first(): return jsonify(message="Username already exists"), 409
    if User.query.filter_by(email=email).first(): return jsonify(message="Email already registered"), 409
    if len(password) < 8: return jsonify(message="Password must be at least 8 characters long"), 400
    new_user = User(username=username, email=email)
    new_user.set_password(password)
    try:
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user) 
        return jsonify(message="User registered successfully", user={'id': new_user.id, 'username': new_user.username}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during registration: {e}")
        return jsonify(message="Registration failed due to an internal error"), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data: return jsonify(message="No input data provided"), 400
    identifier = data.get('identifier')
    password = data.get('password')
    if not identifier or not password: return jsonify(message="Username/email and password are required"), 400
    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
    if user and user.check_password(password):
        login_user(user, remember=data.get('remember', False))
        return jsonify(message="Login successful", user={'id': current_user.id, 'username': current_user.username}), 200
    else:
        return jsonify(message="Invalid username/email or password"), 401

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify(message="Logout successful"), 200

@auth_bp.route('/status', methods=['GET'])
@login_required
def status():
    return jsonify(logged_in=True, user={'id': current_user.id, 'username': current_user.username, 'email': current_user.email}), 200

# --- Leads Blueprint ---
leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')

@leads_bp.route('', methods=['POST']) # Endpoint will be POST /api/leads
@login_required 
def save_new_lead():
    data = request.get_json()
    if not data:
        return jsonify(message="No input data provided"), 400

    google_place_id = data.get('google_place_id')
    name = data.get('name')
    
    if not google_place_id or not name:
        return jsonify(message="Google Place ID and Name are required"), 400

    existing_saved_lead = SavedLead.query.filter_by(user_id=current_user.id, place_id_google=google_place_id).first()
    if existing_saved_lead:
        return jsonify(message="Lead already saved by this user", lead=existing_saved_lead.to_dict()), 409

    new_lead = SavedLead(
        place_id_google=google_place_id,
        name_at_save=name,
        address_at_save=data.get('address'),
        phone_at_save=data.get('phone'),
        website_at_save=data.get('website'),
        user_id=current_user.id,
        user_status=data.get('status', 'New')
    )
    try:
        db.session.add(new_lead)
        db.session.commit()
        return jsonify(message="Lead saved successfully", lead=new_lead.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving lead: {e}") # Log the actual error
        return jsonify(message="Failed to save lead due to an internal error"), 500
    
    # --- NEW ROUTE TO GET SAVED LEADS ---
@leads_bp.route('', methods=['GET']) # Endpoint will be GET /api/leads
@login_required # Only logged-in users can get their leads
def get_saved_leads():
    # Fetch all leads saved by the currently logged-in user
    # The 'saved_leads' relationship on the User model can be used,
    # or query SavedLead directly filtering by user_id.
    # Querying SavedLead directly is often more explicit for APIs.
    
    user_leads = SavedLead.query.filter_by(user_id=current_user.id).order_by(SavedLead.saved_at.desc()).all()
    
    # Convert the list of SavedLead objects to a list of dictionaries
    leads_list = [lead.to_dict() for lead in user_leads]
    
    return jsonify(leads=leads_list), 200

# We will add PUT /api/leads/<id> and DELETE /api/leads/<id> later