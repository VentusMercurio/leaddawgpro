# leaddawg_pro_backend/app/payment_routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import stripe # Ensure stripe is available (initialized in __init__.py)
import os

from app.models import User # To update user tier
from app import db # To commit database changes

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')

# --- Configuration for Stripe Price IDs ---
# It's better to get these from environment variables or a config file in a real app,
# but hardcoding for this example to match previous setup.
# !! REPLACE THESE WITH YOUR ACTUAL STRIPE PRICE IDs !!
PRICE_ID_PRO_MONTHLY = os.getenv('STRIPE_PRICE_ID_PRO_MONTHLY')
PRICE_ID_AGENCY_MONTHLY = os.getenv('STRIPE_PRICE_ID_AGENCY_MONTHLY')
# You would add more Price IDs if you have yearly plans, etc.

# --- Helper to map Price ID to your internal tier name ---
def get_tier_from_price_id(price_id):
    if price_id == PRICE_ID_PRO_MONTHLY:
        return 'pro'
    elif price_id == PRICE_ID_AGENCY_MONTHLY:
        return 'agency'
    # Add more mappings as needed
    return None # Or a default/error case


@payments_bp.route('/create-checkout-session', methods=['POST'])
@login_required # User must be logged in to initiate a subscription
def create_checkout_session():
    data = request.get_json()
    price_id = data.get('priceId') # Frontend will send which Stripe Price ID to use

    if not price_id:
        return jsonify(error={'message': 'Price ID is required'}), 400

    # Validate if price_id is one of your known ones
    if price_id not in [PRICE_ID_PRO_MONTHLY, PRICE_ID_AGENCY_MONTHLY]: # Add other valid Price IDs here
         current_app.logger.warning(f"Invalid Price ID received: {price_id}")
         return jsonify(error={'message': 'Invalid or unsupported Price ID'}), 400

    # Get frontend URL from environment variable or default for local dev
    # This should be the root of your frontend application
    FRONTEND_URL = os.getenv('FRONTEND_URL') or 'http://localhost:5174' 

    try:
        checkout_session_params = {
            'line_items': [
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            'mode': 'subscription',
            'success_url': f"{FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url': f"{FRONTEND_URL}/pricing?canceled=true",
            'client_reference_id': str(current_user.id), # Your app's user ID
            'metadata': { # Additional info you might want in Stripe and webhooks
                'user_id': str(current_user.id),
                'username': current_user.username,
                'selected_price_id': price_id # Store which price they selected
            }
        }
        
        # If you manage customer objects in Stripe and have a stripe_customer_id on your User model:
        if current_user.stripe_customer_id:
            checkout_session_params['customer'] = current_user.stripe_customer_id
        else:
            # If you want Stripe to create a new customer or you want to pass email for guest checkout
            checkout_session_params['customer_email'] = current_user.email
            # Alternatively, create a Stripe Customer first if one doesn't exist for the user:
            # customer = stripe.Customer.create(email=current_user.email, name=current_user.username, metadata={'app_user_id': current_user.id})
            # current_user.stripe_customer_id = customer.id
            # db.session.commit()
            # checkout_session_params['customer'] = customer.id


        checkout_session = stripe.checkout.Session.create(**checkout_session_params)
        
        current_app.logger.info(f"Created Stripe Checkout Session ID: {checkout_session.id} for User ID: {current_user.id}")
        return jsonify({'id': checkout_session.id}) # Return session ID to frontend

    except Exception as e:
        current_app.logger.error(f"Stripe Checkout Session creation error: {e}")
        return jsonify(error={'message': f'Stripe error: {str(e)}'}), 500


@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload_str = request.data.decode('utf-8') # Get raw body as string
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if not endpoint_secret:
        current_app.logger.error("Stripe webhook secret (STRIPE_WEBHOOK_SECRET) is not configured.")
        return jsonify(error="Webhook secret misconfiguration"), 500
    
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload_str, sig_header, endpoint_secret
        )
        current_app.logger.info(f"Received Stripe event: {event['id']} of type: {event['type']}")
    except ValueError as e: # Invalid payload
        current_app.logger.error(f"Webhook ValueError (invalid payload): {e}")
        return jsonify(error=str(e)), 400
    except stripe.error.SignatureVerificationError as e: # Invalid signature
        current_app.logger.error(f"Webhook SignatureVerificationError (invalid signature): {e}")
        return jsonify(error=str(e)), 400
    except Exception as e:
        current_app.logger.error(f"Webhook general construction error: {e}")
        return jsonify(error=str(e)), 400


    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        current_app.logger.info(f"Processing checkout.session.completed for session: {session.id}")
        
        # Retrieve user_id from client_reference_id or metadata
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
                    
                    # Determine tier from metadata if stored, or assume based on the event
                    # For a robust solution, you'd inspect line_items in the session
                    # or listen to 'customer.subscription.created' or 'invoice.paid'
                    # and get the price_id from the subscription data.
                    selected_price_id = session.get('metadata', {}).get('selected_price_id')
                    tier_name = get_tier_from_price_id(selected_price_id) if selected_price_id else 'pro' # Fallback to 'pro'

                    user.tier = tier_name 
                    if stripe_customer_id: user.stripe_customer_id = stripe_customer_id
                    if stripe_subscription_id: user.stripe_subscription_id = stripe_subscription_id
                    # TODO: Set subscription_active_until based on Stripe subscription data
                    # This usually comes from the 'customer.subscription.created' or 'invoice.paid' events
                    # which contain 'current_period_end'.

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

    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        current_app.logger.info(f"Invoice payment succeeded for customer {customer_id}, subscription {subscription_id}")
        # TODO: Find user by stripe_customer_id or stripe_subscription_id
        # Update their subscription_active_until using invoice.period_end (converted from timestamp)
        # Ensure their tier is still correct.

    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        current_app.logger.warning(f"Invoice payment failed for customer {customer_id}, subscription {subscription_id}")
        # TODO: Find user. Notify them. Potentially downgrade tier after grace period or multiple failures.
        
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        current_app.logger.info(f"Subscription {subscription.id} for customer {customer_id} was canceled/deleted.")
        # TODO: Find user by stripe_customer_id. Update their tier to 'free' or 'canceled'.
        # Set subscription_active_until to subscription.ended_at or canceled_at.

    # Add more event handlers as needed:
    # customer.subscription.updated (e.g., plan changes, trial end)
    # checkout.session.async_payment_succeeded
    # checkout.session.async_payment_failed

    return jsonify(received=True), 200