# app/routes.py
from flask import Blueprint, request, jsonify, current_app, Response, send_file # Added Response, send_file
from app import db
from app.models import User, SavedLead 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

# --- Imports for Search Blueprint & Image Proxy ---
import requests 
import time     
import os       
import io # For image proxy stream

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
        return jsonify(message="User registered successfully", user={'id': new_user.id, 'username': new_user.username, 'email': new_user.email, 'tier': new_user.tier }), 201
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
        return jsonify(message="Login successful", user={'id': current_user.id, 'username': current_user.username, 'email': current_user.email, 'tier': current_user.tier }), 200
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
    return jsonify(logged_in=True, user={'id': current_user.id, 'username': current_user.username, 'email': current_user.email, 'tier': current_user.tier }), 200


# --- Leads Blueprint ---
leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')

@leads_bp.route('', methods=['POST'])
@login_required 
def save_new_lead():
    data = request.get_json()
    if not data: return jsonify(message="No input data provided"), 400
    google_place_id = data.get('google_place_id')
    name = data.get('name')
    if not google_place_id or not name: return jsonify(message="Google Place ID and Name are required"), 400
    existing_saved_lead = SavedLead.query.filter_by(user_id=current_user.id, place_id_google=google_place_id).first()
    if existing_saved_lead: return jsonify(message="Lead already saved by this user", lead=existing_saved_lead.to_dict()), 409
    new_lead = SavedLead(
        place_id_google=google_place_id, name_at_save=name,
        address_at_save=data.get('address'), phone_at_save=data.get('phone'),
        website_at_save=data.get('website'), user_id=current_user.id,
        user_status=data.get('status', 'New')
    )
    try:
        db.session.add(new_lead)
        db.session.commit()
        return jsonify(message="Lead saved successfully", lead=new_lead.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving lead: {e}")
        return jsonify(message="Failed to save lead due to an internal error"), 500
    
@leads_bp.route('', methods=['GET'])
@login_required
def get_saved_leads():
    user_leads = SavedLead.query.filter_by(user_id=current_user.id).order_by(SavedLead.saved_at.desc()).all()
    leads_list = [lead.to_dict() for lead in user_leads]
    return jsonify(leads=leads_list), 200

@leads_bp.route('/<int:lead_id>', methods=['PUT'])
@login_required
def update_saved_lead(lead_id):
    lead_to_update = SavedLead.query.get_or_404(lead_id)
    if lead_to_update.owner != current_user: return jsonify(message="Unauthorized to update this lead"), 403
    data = request.get_json()
    if not data: return jsonify(message="No update data provided"), 400
    if 'user_status' in data:
        VALID_STATUSES = ["New", "Contacted", "Followed Up", "Interested", "Booked", "Not Interested", "Pending"] 
        if data['user_status'] not in VALID_STATUSES:
            return jsonify(message=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"), 400
        lead_to_update.user_status = data['user_status']
    if 'user_notes' in data: lead_to_update.user_notes = data['user_notes']
    try:
        db.session.commit()
        return jsonify(message="Lead updated successfully", lead=lead_to_update.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating lead {lead_id}: {e}")
        return jsonify(message="Failed to update lead due to an internal error"), 500

@leads_bp.route('/<int:lead_id>', methods=['DELETE'])
@login_required
def delete_saved_lead(lead_id):
    lead_to_delete = SavedLead.query.get_or_404(lead_id)
    if lead_to_delete.owner != current_user: return jsonify(message="Unauthorized to delete this lead"), 403
    try:
        db.session.delete(lead_to_delete)
        db.session.commit()
        return jsonify(message="Lead deleted successfully"), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting lead {lead_id}: {e}")
        return jsonify(message="Failed to delete lead due to an internal error"), 500


# --- SEARCH BLUEPRINT (Including Image Proxy) ---
search_bp = Blueprint('search', __name__, url_prefix='/api/search')

GOOGLE_PLACES_API_KEY_FOR_PRO = os.getenv("GOOGLE_PLACES_API_KEY_PRO") 
PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACE_DETAILS_API_URL = "https://maps.googleapis.com/maps/api/place/details/json"

@search_bp.route('/places', methods=['GET'])
def search_places_route():
    # ... (Your existing search_places_route logic for fetching from Google, 
    #      including photo_url generation, is already here and correct from your provided block) ...
    # ... (No changes needed inside this function from your provided block) ...
    query = request.args.get('query')
    if not query: return jsonify(message="Missing 'query' parameter"), 400
    if not GOOGLE_PLACES_API_KEY_FOR_PRO:
        current_app.logger.error("GOOGLE_PLACES_API_KEY_PRO not configured.")
        return jsonify(message="API key for places search not configured"), 500
    all_raw_places_from_textsearch = []
    max_pages = 3; current_page_count = 0; next_page_token = None
    try:
        while current_page_count < max_pages:
            current_page_count += 1; api_params = { "query": query, "key": GOOGLE_PLACES_API_KEY_FOR_PRO }
            if next_page_token: api_params["pagetoken"] = next_page_token; time.sleep(2)
            response = requests.get(PLACES_API_URL, params=api_params); response.raise_for_status()
            results_json = response.json()
            if results_json.get("status") == "OK":
                all_raw_places_from_textsearch.extend(results_json.get("results", [])); next_page_token = results_json.get("next_page_token")
                if not next_page_token: break
            elif results_json.get("status") == "ZERO_RESULTS" and current_page_count == 1: return jsonify(status="ZERO_RESULTS", places=[]), 200
            elif results_json.get("status") != "OK":
                error_msg = results_json.get('error_message', 'Unknown Google API error')
                if not all_raw_places_from_textsearch: return jsonify(message=f"Google API error: {error_msg}"), 500
                else: break
            else: break
        if not all_raw_places_from_textsearch: return jsonify(status="ZERO_RESULTS", places=[]), 200
        detailed_places_list = []
        for basic_place_info in all_raw_places_from_textsearch:
            place_id = basic_place_info.get("place_id")
            place_name_for_log = basic_place_info.get("name", "Unknown")
            if not place_id: detailed_places_list.append({ "name": place_name_for_log, "error_message": "Missing Place ID" }); continue
            details_params = {"place_id": place_id, "fields": "name,formatted_address,website,formatted_phone_number,types,rating,user_ratings_total,business_status,opening_hours,url,place_id,photos", "key": GOOGLE_PLACES_API_KEY_FOR_PRO}
            details_response = requests.get(PLACE_DETAILS_API_URL, params=details_params); details_result = details_response.json()
            photo_url = None
            if details_result.get("status") == "OK" and "result" in details_result:
                place_data = details_result["result"]
                if place_data.get("photos") and len(place_data["photos"]) > 0:
                    photo_ref = place_data["photos"][0].get("photo_reference")
                    if photo_ref: photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_ref}&key={GOOGLE_PLACES_API_KEY_FOR_PRO}"
                detailed_places_list.append({"google_place_id": place_id, "name": place_data.get("name"), "address": place_data.get("formatted_address"), "website": place_data.get("website"), "phone_number": place_data.get("formatted_phone_number"), "photo_url": photo_url, "email": None, "types": place_data.get("types", []), "rating": place_data.get("rating"), "user_ratings_total": place_data.get("user_ratings_total"), "business_status": place_data.get("business_status"), "opening_hours": place_data.get("opening_hours", {}).get("weekday_text"), "google_maps_url": place_data.get("url")})
            else: detailed_places_list.append({"google_place_id": place_id, "name": place_name_for_log, "address": basic_place_info.get("formatted_address"), "website": None, "phone_number": None, "email": None, "photo_url": None, "types": basic_place_info.get("types", []), "rating": basic_place_info.get("rating"), "user_ratings_total": basic_place_info.get("user_ratings_total"), "business_status": basic_place_info.get("business_status"), "opening_hours": None, "google_maps_url": None, "error_details_fetch": details_result.get('status')})
        return jsonify(status="OK", places=detailed_places_list), 200
    except requests.exceptions.RequestException as e: return jsonify(message=f"Error calling Google Places API: {str(e)}"), 503
    except Exception as e: current_app.logger.error(f"Unexpected error in search: {e}", exc_info=True); return jsonify(message=f"Server error: {str(e)}"), 500


# --- NEW IMAGE PROXY ROUTE (added to search_bp) ---
@search_bp.route('/image-proxy', methods=['GET'])
def image_proxy():
    photo_url_to_fetch = request.args.get('url') 

    if not photo_url_to_fetch:
        return jsonify(error="Missing image URL parameter ('url')"), 400

    # Basic validation (optional but good)
    if not photo_url_to_fetch.startswith("https://maps.googleapis.com/maps/api/place/photo"):
        current_app.logger.warning(f"Image proxy received potentially invalid URL: {photo_url_to_fetch}")
        # Allow it to proceed for now, Google will error out if it's truly invalid
        # return jsonify(error="Invalid image URL for proxy, must be a Google Places Photo API URL"), 400

    try:
        current_app.logger.info(f"Proxying image from: {photo_url_to_fetch}")
        
        # It's critical that your GOOGLE_PLACES_API_KEY_FOR_PRO is part of photo_url_to_fetch
        # (which it is, because your search_places_route constructed it that way)
        # So, no need to add the key again here.
        image_response = requests.get(photo_url_to_fetch, stream=True)
        image_response.raise_for_status() 

        content_type = image_response.headers.get('Content-Type', 'image/jpeg')
        
        # Use iter_content to stream. Important for larger images.
        def generate():
            for chunk in image_response.iter_content(chunk_size=8192): # Read in 8KB chunks
                yield chunk
        
        return Response(generate(), content_type=content_type)

    except requests.exceptions.HTTPError as http_err:
        current_app.logger.error(f"HTTP error proxying image {photo_url_to_fetch}: {http_err} - Status: {http_err.response.status_code}")
        return jsonify(error=f"Failed to fetch image from source: {http_err.response.status_code}"), http_err.response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Network error proxying image {photo_url_to_fetch}: {e}")
        return jsonify(error=f"Failed to fetch image due to network issue: {str(e)}"), 502
    except Exception as e:
        current_app.logger.error(f"Unexpected error in image_proxy for {photo_url_to_fetch}: {e}", exc_info=True)
        return jsonify(error="Server error during image proxying"), 500