# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A script to demonstrate a 3-legged OAuth flow with BTP XSUAA and
interact with a secured currency conversion API.

This script sets up a local web server to catch the OAuth redirect,
obtains an access token, and then uses it to call a secured API.
"""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import webbrowser
import requests
from tabulate import tabulate

#------------------------------------------------------------------------#
# Globals
#------------------------------------------------------------------------#
XSUAA_URL = os.getenv("XSUAA_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SALES_ORDER_API_URL = os.getenv("SALES_ORDER_API_URL")
REDIRECT_URI = "http://localhost:3000/callback"

# Global variable to store the code received by the web server
auth_code = None

#------------------------------------------------------------------------#
# Callback handler for a 3-legged OAuth flow
#------------------------------------------------------------------------#
class CallbackHandler(BaseHTTPRequestHandler):
    """A simple local web server to catch the redirect from BTP."""
    
    def do_GET(self):
        """Handles GET requests to the callback URI.

        It extracts the authorization code from the URL query parameters,
        stores it globally, and sends a success message to the browser.
        """
        global auth_code
        query_components = parse_qs(urlparse(self.path).query)
        
        if 'code' in query_components:
            auth_code = query_components['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            # Send a success message to the browser
            self.wfile.write(b"<html><body><h1>Authentication successful!</h1><p>You can close this tab and return to your terminal.</p></body></html>")
        else:
            self.send_response(400)
            self.end_headers()
            
    def log_message(self, format, *args):
        """Suppresses the default HTTP server logging.

        This is done to keep the terminal output clean during the OAuth flow.
        """
        # Suppress standard HTTP server logging to keep terminal clean
        pass


#------------------------------------------------------------------------#
# Get Access token from 3 legged flow
#------------------------------------------------------------------------#
def get_access_token_3_legged():
    """Authenticates using the 3-Legged Authorization Code Flow.

    This function performs the following steps:
    1. Starts a local HTTP server to listen for the OAuth callback.
    2. Constructs the authorization URL for BTP XSUAA.
    3. Opens the authorization URL in the user's default web browser.
    4. Waits for the authorization code from the callback.
    5. Exchanges the authorization code for an access token.

    Returns:
        The obtained access token as a string.

    Raises:
        Exception: If the authorization code cannot be retrieved.
        requests.exceptions.HTTPError: If the token exchange fails.
    """
    global auth_code
    
    # 1. Start a local server to listen for the BTP callback
    server_address = ('localhost', 3000)
    httpd = HTTPServer(server_address, CallbackHandler)
    
    # 2. Construct the authorization URL
    auth_url = XSUAA_URL + "/oauth/authorize"
    
    auth_request_url = (
        f"{auth_url}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    
    # 3. Open the user's default web browser
    print("Opening browser for BTP authentication...")
    webbrowser.open(auth_request_url)
    
    # 4. Wait for exactly one request (the callback)
    print("Waiting for authorization callback on port 3000...")
    httpd.handle_request() 
    
    if not auth_code:
        raise Exception("Failed to retrieve the authorization code.")
        
    print("Authorization code received! Exchanging for access token...")
    
    # 5. Exchange the authorization code for an Access Token
    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'code': auth_code
    }
    
    token_url = XSUAA_URL + "/oauth/token"
    response = requests.post(token_url, data=payload)
    response.raise_for_status() 
    
    token_data = response.json()
    return token_data['access_token']

#------------------------------------------------------------------------#
# Get top 5 Sales Orders
#------------------------------------------------------------------------#
def get_sales_orders(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    query_params = {"$top": 5, "$format": "json"}  
    response = requests.get(f"{SALES_ORDER_API_URL}/A_SalesOrder", headers=headers, params=query_params)
    response.raise_for_status() 
    return response.json()

#------------------------------------------------------------------------#
# Main method
#------------------------------------------------------------------------#
def main():
    """Main function to execute the authentication and currency conversion process.

    It obtains an access token and then calls the currency conversion API
    to convert a fixed amount from USD to EUR.
    """
    access_token = get_access_token_3_legged()
    response = get_sales_orders(access_token)
    
    # Get headers for tabulate
    headers = ["Order No.", "Net Amount", "Currency"]

    # Get data for tabulate
    data = []
    for order in response['d']['results']:
        data.append([order['SalesOrder'], order['TotalNetAmount'], order['TransactionCurrency']])
    
    # Print the table
    print(tabulate(data, headers=headers, tablefmt="pretty"))

#------------------------------------------------------------------------#
# Entry 
#------------------------------------------------------------------------#
if __name__ == "__main__":
    main()
