# app/__init__.py
from flask import Flask, current_app # Added current_app for logging example
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
import os # Ensure os is imported

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
# login_manager.login_view = 'auth.login' # Points to the login route in 'auth' blueprint
# We are building an API, so login_view might not be used in the same way as a traditional web app.
# For API, frontend handles redirects. If session cookie is not valid, API returns 401.
login_manager.session_protection = "strong" # Good for security
login_manager.login_message_category = 'info'


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    # Configure CORS to allow credentials (cookies) from your frontend domain
    # Replace 'http://localhost:3000' with your actual frontend dev URL or deployed URL
    CORS(app, supports_credentials=True, origins=["http://localhost:5173", "http://localhost:3000"]) # Add your frontend origins

    # Register Blueprints
    from app.routes import auth_bp # Import the auth blueprint
    app.register_blueprint(auth_bp)

    # If you have other general API routes, create another blueprint for them
    # e.g., from app.api_routes import api_bp
    # app.register_blueprint(api_bp, url_prefix='/api/v1')


    @app.route('/test/')
    def test_page():
        return '<h1>Testing the Flask Application Factory!</h1>'
    
    @app.route('/') # Optional root route for basic status
    def index():
        return jsonify(status="LeadDawg Pro Backend is Alive and Kicking!",
                       version="0.1.0-auth-setup")

    return app

from app import models # Important: Keep this at the bottom