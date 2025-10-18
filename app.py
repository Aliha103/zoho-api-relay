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
    required_vars = ['ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET', 'ZOHO_REFRESH_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set up Zoho Mail API credentials")
        exit(1)
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
