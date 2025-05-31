# config.py
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env')) 

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Stripe Keys
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # --- ADD THESE FOR STRIPE PRICE IDs ---
    STRIPE_PRICE_ID_PRO_MONTHLY = os.environ.get('STRIPE_PRICE_ID_PRO_MONTHLY')
    STRIPE_PRICE_ID_AGENCY_MONTHLY = os.environ.get('STRIPE_PRICE_ID_AGENCY_MONTHLY')
    
    # --- ADD FRONTEND URL CONFIG ---
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:5174' 