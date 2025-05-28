# app/models.py
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime # Import datetime for timestamps

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    
    # Relationship to SavedLead (one-to-many: one User has many SavedLeads)
    saved_leads = db.relationship('SavedLead', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class SavedLead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    place_id_google = db.Column(db.String(255), nullable=False, index=True) # Google's Place ID
    name_at_save = db.Column(db.String(255), nullable=False)
    address_at_save = db.Column(db.String(500)) # Address can be long
    phone_at_save = db.Column(db.String(50))
    website_at_save = db.Column(db.String(500))
    
    user_status = db.Column(db.String(50), default='New', nullable=False) # e.g., New, Contacted, Booked
    user_notes = db.Column(db.Text) # For longer notes from the user
    
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign Key to link to the User who saved this lead
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<SavedLead {self.name_at_save} for User {self.user_id}>'

    def to_dict(self): # Helper method to convert object to dictionary for JSON response
        return {
            'id': self.id,
            'place_id_google': self.place_id_google,
            'name_at_save': self.name_at_save,
            'address_at_save': self.address_at_save,
            'phone_at_save': self.phone_at_save,
            'website_at_save': self.website_at_save,
            'user_status': self.user_status,
            'user_notes': self.user_notes,
            'saved_at': self.saved_at.isoformat() + 'Z' if self.saved_at else None, # ISO format with Z for UTC
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'user_id': self.user_id
        }