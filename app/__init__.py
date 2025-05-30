# app/__init__.py
from flask import Flask, current_app, jsonify
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
import stripe
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.session_protection = "strong"

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
     # Initialize Stripe API key
    if app.config['STRIPE_SECRET_KEY']:
        stripe.api_key = app.config['STRIPE_SECRET_KEY']
    else:
        app.logger.warning("STRIPE_SECRET_KEY not set. Stripe functionality will not work.")


    # Ensure the instance folder exists for SQLite
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists or cannot create

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Configure CORS: Add your frontend development and production URLs
    # Example: "http://localhost:5174" could be your new commercial frontend dev port
    CORS(app, supports_credentials=True, origins=[
        "http://localhost:3000", # Common React dev port
        "http://localhost:5173", # Vite default React dev port
        "http://localhost:5174", # Another possible Vite port
        # Add your deployed frontend URL here later, e.g., "https://your-app.vercel.app"
    ])

    # --- Register Blueprints ---
    from app.routes import auth_bp 
    app.register_blueprint(auth_bp)

    from app.routes import leads_bp
    app.register_blueprint(leads_bp) 

    from app.routes import search_bp  # <--- IMPORT search_bp
    app.register_blueprint(search_bp) # <--- REGISTER search_bp

    # --- Test and Index Routes (defined directly on app) ---
    @app.route('/test/')
    def test_page():
        return '<h1>Testing the Flask Application Factory!</h1>'
    
    @app.route('/')
    def index():
        return jsonify(status="LeadDawg Pro Backend is Alive and Kicking!", 
                       version="0.1.2-search-added", # Updated version for clarity
                       available_blueprints=["/api/auth", "/api/leads", "/api/search"])

    return app

# Import models at the bottom to avoid circular imports,
# especially important for Flask-Migrate and SQLAlchemy.
from app import models