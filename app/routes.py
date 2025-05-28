from flask import Blueprint, jsonify

bp = Blueprint('main', __name__, url_prefix='/api') # All routes here will be /api/...

@bp.route('/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello from LeadDawg Pro Backend!")

# We will add /register, /login, /search (from old app), /my-leads etc. here later