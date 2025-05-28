from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login' # Will define 'auth.login' route later
login_manager.login_message_category = 'info' # For flashing messages

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    CORS(app, supports_credentials=True) # supports_credentials=True if you use cookies for session

    # Import and register Blueprints here
    from app.routes import bp as main_bp # Example, will create routes.py
    app.register_blueprint(main_bp)

    # You might have an 'auth' blueprint for auth routes
    # from app.auth_routes import auth_bp # Example
    # app.register_blueprint(auth_bp, url_prefix='/auth')


    @app.route('/test/') # A simple test route
    def test_page():
        return '<h1>Testing the Flask Application Factory!</h1>'

    return app

# Import models here to make them known to Flask-Migrate
# but do it at the bottom to avoid circular imports
from app import models 
import os # Add this if not already imported at the top