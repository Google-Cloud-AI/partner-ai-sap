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


import os
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import webbrowser
import requests
import asyncio
import httpx
from a2a.client import ClientConfig, create_client, A2ACardResolver
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from a2a.client.errors import A2AClientError


#------------------------------------------------------------------------#
# Globals
#------------------------------------------------------------------------#
load_dotenv(override=True)

XSUAA_URL = os.getenv("XSUAA_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AGENT_URL = os.getenv("AGENT_URL")
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
# Get agent card
#------------------------------------------------------------------------#
async def get_agent_card():
    print('Initializes the A2ACardResolver instance with an HTTP client')
    
    import httpx 
    from a2a.client import A2ACardResolver 

    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=AGENT_URL,
        )
        public_agent_card = await resolver.get_agent_card()
        print('\nSuccessfully fetched the public agent card:')
    return public_agent_card


#------------------------------------------------------------------------#
# Send message to agent 
#------------------------------------------------------------------------#
async def send_message(text_query: str, access_token: str):
    public_agent_card = await get_agent_card()
    print('\n--- Public Agent Card - Non-Streaming Call ---')
    
    headers = {"Authorization": f"Bearer {access_token}"}
    print('\nInitializing a non-streaming client.')
    
    try:
        async with httpx.AsyncClient(headers=headers) as httpx_client:
            # Pass the pre-configured httpx_client to ClientConfig
            config = ClientConfig(
                streaming=False,
                httpx_client=httpx_client
            )
            client = await create_client(agent=public_agent_card, client_config=config)
            
            # Creates a new text message to be sent to the A2A Server.
            message = new_text_message(text_query, role=Role.ROLE_USER)
            request = SendMessageRequest(message=message)
            
            print('\nResponse: ', end="")
            
            async for chunk in client.send_message(request):
               # Resolve any Pydantic RootModel wrapping if present
                data = chunk.root if hasattr(chunk, "root") else chunk
                payload = data.result if hasattr(data, "result") else data
                
                # Extract the 'task' container (supports both object and dict structures)
                task = None
                if hasattr(payload, "task") and payload.task:
                    task = payload.task
                elif hasattr(data, "task") and data.task:
                    task = data.task
                elif isinstance(payload, dict) and "task" in payload:
                    task = payload["task"]
                
                # Traverse task -> artifacts -> parts -> text
                if task:
                    # Retrieve the list of artifacts
                    artifacts = getattr(task, "artifacts", []) if not isinstance(task, dict) else task.get("artifacts", [])
                    for artifact in artifacts:
                        # Retrieve the list of parts in each artifact
                        parts = getattr(artifact, "parts", []) if not isinstance(artifact, dict) else artifact.get("parts", [])
                        for part in parts:
                            # Unwrap Pydantic RootModel from parts if wrapped
                            p = part.root if hasattr(part, "root") else part
                            
                            # Safely extract and print the text string
                            text = getattr(p, "text", "") if not isinstance(p, dict) else p.get("text", "")
                            if text:
                                print(text, end="", flush=True)
                                
            print()
            await client.close()
            
    except A2AClientError as e:
        # Catch JSON-RPC Errors, Timeouts, HTTP errors from the A2A SDK cleanly
        print(f"[A2A Client Error] {e}")
        
    except httpx.HTTPStatusError as e:
        # Catch direct HTTP status issues from the underlying HTTP layer
        print(f"[HTTP Error] Server returned status code {e.response.status_code}: {e.response.text}")
        
    except Exception as e:
        # Catch unexpected Python errors
        print(f"[Unexpected Error] {e}")


#------------------------------------------------------------------------#
# Entry 
#------------------------------------------------------------------------#
if __name__ == "__main__":
    
    access_token = get_access_token_3_legged()
    print('\nStarting an internactive session with A2A Server')
    print('Use `exit` to quit.')
    prompt = input('user > ')
    while prompt and prompt != 'exit':
        asyncio.run(send_message(prompt, access_token))
        prompt = input('--\nuser > ')

