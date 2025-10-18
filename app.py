#!/usr/bin/env python3
"""
Zoho Mail API Relay Service for Railway
Uses Zoho Mail API instead of SMTP to avoid Railway's SMTP blocking
"""

from flask import Flask, request, jsonify
import requests
import os
import logging
import json

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Zoho Mail API Configuration
ZOHO_CLIENT_ID = os.getenv('ZOHO_CLIENT_ID')
ZOHO_CLIENT_SECRET = os.getenv('ZOHO_CLIENT_SECRET')
ZOHO_REFRESH_TOKEN = os.getenv('ZOHO_REFRESH_TOKEN')
ZOHO_USER_EMAIL = os.getenv('ZOHO_USER_EMAIL', 'reservations@allarcoapartment.com')

# Zoho API endpoints (European)
ZOHO_TOKEN_URL = 'https://accounts.zoho.eu/oauth/v2/token'
ZOHO_MAIL_API_URL = 'https://mail.zoho.eu/api/messages'

def get_access_token():
    """Get access token using refresh token"""
    try:
        data = {
            'refresh_token': ZOHO_REFRESH_TOKEN,
            'client_id': ZOHO_CLIENT_ID,
            'client_secret': ZOHO_CLIENT_SECRET,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(ZOHO_TOKEN_URL, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get('access_token')
        else:
            logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting access token: {e}")
        return None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'zoho-mail-api-relay'})

@app.route('/send-email', methods=['POST'])
def send_email():
    """Send email via Zoho Mail API"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['to', 'subject', 'body']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get access token
        access_token = get_access_token()
        if not access_token:
            return jsonify({'error': 'Failed to get access token'}), 500
        
        # Prepare email data for Zoho API
        email_data = {
            'fromAddress': data.get('from', ZOHO_USER_EMAIL),
            'toAddress': data['to'],
            'subject': data['subject'],
            'content': data['body'],
            'mailFormat': 'html' if data.get('html', False) else 'text'
        }
        
        # Send email via Zoho API
        headers = {
            'Authorization': f'Zoho-oauthtoken {access_token}',
            'Content-Type': 'application/json'
        }
        
        logger.info(f"Sending email from {email_data['fromAddress']} to {email_data['toAddress']}")
        
        response = requests.post(
            ZOHO_MAIL_API_URL,
            headers=headers,
            json=email_data
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"Email sent successfully to {email_data['toAddress']}")
            return jsonify({'status': 'success', 'message': 'Email sent successfully'})
        else:
            logger.error(f"Failed to send email: {response.status_code} - {response.text}")
            return jsonify({'error': f'Zoho API error: {response.text}'}), 500
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/auth/start', methods=['GET'])
def start_oauth():
    """Start OAuth flow to get refresh token"""
    if not ZOHO_CLIENT_ID:
        return jsonify({"error": "ZOHO_CLIENT_ID not configured"}), 500
    
    # Get the current service URL
    service_url = request.url_root.rstrip('/')
    redirect_uri = f"{service_url}/auth/callback"
    
    auth_url = f"https://accounts.zoho.eu/oauth/v2/auth?scope=ZohoMail.messages.CREATE,ZohoMail.accounts.READ&client_id={ZOHO_CLIENT_ID}&response_type=code&access_type=offline&redirect_uri={redirect_uri}"
    
    return jsonify({
        "message": "Visit this URL to complete OAuth flow",
        "auth_url": auth_url,
        "redirect_uri": redirect_uri
    }), 200

@app.route('/auth/callback', methods=['GET'])
def oauth_callback():
    """Handle OAuth callback and get refresh token"""
    code = request.args.get('code')
    if not code:
        return jsonify({"error": "No authorization code received"}), 400
    
    # Exchange code for tokens
    token_url = 'https://accounts.zoho.eu/oauth/v2/token'
    data = {
        'grant_type': 'authorization_code',
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'redirect_uri': request.url_root.rstrip('/') + '/auth/callback',
        'code': code
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        tokens = response.json()
        
        refresh_token = tokens.get('refresh_token')
        if refresh_token:
            return jsonify({
                "message": "OAuth successful! Add this to your environment variables:",
                "ZOHO_REFRESH_TOKEN": refresh_token,
                "access_token": tokens.get('access_token'),
                "expires_in": tokens.get('expires_in')
            }), 200
        else:
            return jsonify({"error": "No refresh token received"}), 400
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to exchange code for tokens: {str(e)}"}), 500

@app.route('/test', methods=['GET'])
def test_connection():
    """Test Zoho API connection"""
    try:
        access_token = get_access_token()
        if access_token:
            logger.info("Zoho API connection test successful")
            return jsonify({'status': 'success', 'message': 'Zoho API connection successful'})
        else:
            return jsonify({'error': 'Failed to get access token'}), 500
    except Exception as e:
        logger.error(f"Zoho API connection test failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    required_vars = ['ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set up Zoho Mail API credentials")
        exit(1)
    
    # Check for refresh token
    if not os.getenv('ZOHO_REFRESH_TOKEN'):
        logger.warning("ZOHO_REFRESH_TOKEN not set. Service will start but email sending will be disabled.")
        logger.warning("Complete OAuth flow to get refresh token: /auth/start")
    
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting Zoho API Relay Service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
