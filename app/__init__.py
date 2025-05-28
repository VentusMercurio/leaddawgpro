# app/__init__.py
from flask import Flask, current_app, jsonify # Ensure current_app is imported if used in routes
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.session_protection = "strong"
# login_manager.login_view = 'auth.login' # Not strictly needed for pure API if frontend handles 401s

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
    # Adjust origins as needed for your new commercial frontend
    CORS(app, supports_credentials=True, origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"]) # Example new port

    # Register Blueprints
    from app.routes import auth_bp 
    app.register_blueprint(auth_bp)

    from app.routes import leads_bp # IMPORT AND REGISTER THE LEADS BLUEPRINT
    app.register_blueprint(leads_bp) 

    @app.route('/test/')
    def test_page():
        return '<h1>Testing the Flask Application Factory!</h1>'
    
    @app.route('/')
    def index():
        return jsonify(status="LeadDawg Pro Backend is Alive and Kicking!", version="0.1.1-leads-setup")

    return app

from app import models