# leaddawg_pro_backend/app/payment_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import stripe # Ensure stripe is available (initialized in __init__.py)
import os

from app.models import User # To update user tier
from app import db # To commit database changes

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')

# --- Configuration for Stripe Price IDs ---
# These are loaded when the module is imported
PRICE_ID_PRO_MONTHLY = os.getenv('STRIPE_PRICE_ID_PRO_MONTHLY')
PRICE_ID_AGENCY_MONTHLY = os.getenv('STRIPE_PRICE_ID_AGENCY_MONTHLY')

# Debug print to verify loading from .env at startup (will print when Flask loads this file)
print(f"--- PAYMENT_ROUTES.PY LOADED: PRO ID = '{PRICE_ID_PRO_MONTHLY}', AGENCY ID = '{PRICE_ID_AGENCY_MONTHLY}' ---")


# --- Helper to map Price ID to your internal tier name ---
def get_tier_from_price_id(price_id):
    # This function uses the module-level variables defined above
    if price_id == PRICE_ID_PRO_MONTHLY:
        return 'pro'
    elif price_id == PRICE_ID_AGENCY_MONTHLY:
        return 'agency'
    return None


@payments_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    current_app.logger.info("--- In create_checkout_session ---")
    # Logging the module-level variables correctly
    current_app.logger.info(f"Value of PRICE_ID_PRO_MONTHLY (module-level) in route: '{PRICE_ID_PRO_MONTHLY}'")
    current_app.logger.info(f"Value of PRICE_ID_AGENCY_MONTHLY (module-level) in route: '{PRICE_ID_AGENCY_MONTHLY}'")

    if not PRICE_ID_PRO_MONTHLY or not PRICE_ID_AGENCY_MONTHLY: # Check the module-level variables
        current_app.logger.error("Server-side Stripe Price ID configuration is missing (env vars not loaded at module level).")
        return jsonify(error={'message': 'Payment system not configured correctly. Please contact support.'}), 500

    data = request.get_json()
    current_app.logger.debug(f"Received data: {data}")
    if not data:
        return jsonify(error={'message': 'No input data provided'}), 400
    
    price_id_from_frontend = data.get('priceId')
    current_app.logger.info(f"Price ID received from frontend: '{price_id_from_frontend}'")

    if not price_id_from_frontend:
        return jsonify(error={'message': 'Price ID is required from frontend'}), 400

    valid_price_ids_map = {
        PRICE_ID_PRO_MONTHLY: "Pro Monthly Plan", # Uses module-level variable
        PRICE_ID_AGENCY_MONTHLY: "Agency Monthly Plan"  # Uses module-level variable
    }
    current_app.logger.debug(f"Valid server Price IDs map keys: {list(valid_price_ids_map.keys())}")

    if price_id_from_frontend not in valid_price_ids_map:
         current_app.logger.warning(f"VALIDATION FAIL: Frontend Price ID '{price_id_from_frontend}' not in server's valid map (which contains: {list(valid_price_ids_map.keys())}).")
         return jsonify(error={'message': 'Invalid or unsupported subscription plan selected.'}), 400
    
    selected_stripe_price_id = price_id_from_frontend 

    FRONTEND_URL = os.getenv('FRONTEND_URL') or current_app.config.get('FRONTEND_URL') or 'http://localhost:5174' 
    # Prioritize os.getenv for FRONTEND_URL if it might be set differently than app.config for some reason

    try:
          # --- NEW DEBUG STEP: TRY TO RETRIEVE THE PRICE DIRECTLY ---
        try:
            current_app.logger.info(f"Attempting to retrieve Price object from Stripe with ID: '{selected_stripe_price_id}'")
            retrieved_price = stripe.Price.retrieve(selected_stripe_price_id)
            current_app.logger.info(f"Successfully retrieved Price object: {retrieved_price.id}, Active: {retrieved_price.active}, Type: {retrieved_price.type}, Recurring: {retrieved_price.recurring}")
            if retrieved_price.type != 'recurring':
                current_app.logger.error(f"Price ID '{selected_stripe_price_id}' is NOT a recurring price. It's type: {retrieved_price.type}")
                # return jsonify(error={'message': 'Selected plan is not a subscription.'}), 400 # Optionally stop here
            if not retrieved_price.active:
                current_app.logger.error(f"Price ID '{selected_stripe_price_id}' is NOT active.")
                # return jsonify(error={'message': 'Selected plan is not active.'}), 400 # Optionally stop here

        except stripe.error.StripeError as e_retrieve:
            current_app.logger.error(f"Failed to retrieve Price object '{selected_stripe_price_id}' from Stripe directly: {e_retrieve}")
            # This error might be the same "No such price" error, confirming the ID is the issue with Stripe
        
        checkout_session_params = {
            'line_items': [{'price': selected_stripe_price_id, 'quantity': 1}],
            'mode': 'subscription',
            'success_url': f"{FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url': f"{FRONTEND_URL}/pricing?canceled=true",
            'client_reference_id': str(current_user.id),
            'metadata': {
                'user_id': str(current_user.id),
                'username': current_user.username,
                'selected_price_id': selected_stripe_price_id
            }
        }
        
        if current_user.stripe_customer_id:
            checkout_session_params['customer'] = current_user.stripe_customer_id
        else:
            checkout_session_params['customer_email'] = current_user.email

        current_app.logger.info(f"STRIPE API CALL PARAMS: Attempting to use Price ID: '{selected_stripe_price_id}' for line_items.")
        checkout_session = stripe.checkout.Session.create(**checkout_session_params)
        
        current_app.logger.info(f"Created Stripe Checkout Session ID: {checkout_session.id} for User ID: {current_user.id}")
        return jsonify({'id': checkout_session.id})

    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe API error during Checkout Session creation: {e}")
        error_message = str(e)
        if hasattr(e, 'user_message') and e.user_message:
            error_message = e.user_message
        elif hasattr(e, 'json_body') and e.json_body and 'error' in e.json_body and 'message' in e.json_body['error']:
            error_message = e.json_body['error']['message']
        return jsonify(error={'message': f'Stripe error: {error_message}'}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in create_checkout_session: {e}", exc_info=True)
        return jsonify(error={'message': 'An unexpected server error occurred.'}), 500

# ... (Keep the stripe_webhook function exactly as it was in the last version you provided,
#      as its internal logic for get_tier_from_price_id using the module-level PRICE_ID_PRO_MONTHLY
#      and PRICE_ID_AGENCY_MONTHLY was correct.) ...
@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload_str = request.data.decode('utf-8') 
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if not endpoint_secret:
        current_app.logger.error("Stripe webhook secret (STRIPE_WEBHOOK_SECRET) is not configured.")
        return jsonify(error="Webhook secret misconfiguration"), 500
    
    event = None
    try:
        event = stripe.Webhook.construct_event(payload_str, sig_header, endpoint_secret)
        current_app.logger.info(f"Received Stripe event: {event['id']} of type: {event['type']}")
    except ValueError as e: 
        current_app.logger.error(f"Webhook ValueError (invalid payload): {e}")
        return jsonify(error=str(e)), 400
    except stripe.error.SignatureVerificationError as e: 
        current_app.logger.error(f"Webhook SignatureVerificationError (invalid signature): {e}")
        return jsonify(error=str(e)), 400
    except Exception as e:
        current_app.logger.error(f"Webhook general construction error: {e}")
        return jsonify(error=str(e)), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        current_app.logger.info(f"Processing checkout.session.completed for session: {session.id}")
        user_id_str = session.get('client_reference_id')
        if not user_id_str and 'metadata' in session and session['metadata']:
            user_id_str = session['metadata'].get('user_id')
        if user_id_str:
            try:
                user_id = int(user_id_str)
                user = User.query.get(user_id)
                if user:
                    stripe_customer_id = session.get('customer')
                    stripe_subscription_id = session.get('subscription')
                    selected_price_id = session.get('metadata', {}).get('selected_price_id')
                    tier_name = get_tier_from_price_id(selected_price_id) if selected_price_id else 'pro' 
                    user.tier = tier_name 
                    if stripe_customer_id: user.stripe_customer_id = stripe_customer_id
                    if stripe_subscription_id: user.stripe_subscription_id = stripe_subscription_id
                    db.session.commit()
                    current_app.logger.info(f"User ID {user.id} ({user.username}) subscription activated/updated to tier: {tier_name}.")
                else:
                    current_app.logger.error(f"Webhook: User not found for ID {user_id_str} from session {session.id}.")
            except ValueError:
                current_app.logger.error(f"Webhook: Invalid user_id format '{user_id_str}' from session {session.id}.")
            except Exception as e:
                current_app.logger.error(f"Webhook: DB error updating user after checkout.session.completed: {e}")
                db.session.rollback()
        else:
            current_app.logger.warning(f"Webhook: client_reference_id or metadata.user_id missing in checkout.session.completed: {session.id}")
    elif event['type'] == 'invoice.payment_succeeded': # ... (as before)
        pass 
    elif event['type'] == 'invoice.payment_failed': # ... (as before)
        pass
    elif event['type'] == 'customer.subscription.deleted': # ... (as before)
        pass
    return jsonify(received=True), 200