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
import json
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import uvicorn
from cfenv import AppEnv
from sap import xssec


from google.auth import identity_pool
from google.auth import impersonated_credentials
from google.auth import exceptions

from context_store import request_credentials_ctx, credential_cache
from agent import a2a_app


load_dotenv(override=True)

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_PROJECT_NUMBER = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER")
WIF_POOL_ID = os.getenv("WIF_POOL_ID")
WIF_POOL_LOCATION = os.getenv("WIF_POOL_LOCATION")
WIF_PROVIDER_ID = os.getenv("WIF_PROVIDER_ID")
TARGET_SERVICE_ACCOUNT = os.getenv("TARGET_SERVICE_ACCOUNT")

_isbtp = os.getenv('AGENT_RUNTIME_IS_BTP',"N").upper()
    
# ----------------------------------------------------- #
# Get BTP access token
# ----------------------------------------------------- #
def get_btp_access_token(request):
    """
    Extracts the BTP access token from the 'Authorization' header of the incoming request.

    Args:
        request: The incoming FastAPI request object.

    Returns:
        str: The BTP access token string if found, otherwise an empty string.
    """
    try:
        btp_access_token = request.headers.get('authorization')[7:]
        return btp_access_token
    except Exception as e:
        return ""

# ----------------------------------------------------- #
# BTP Auth Check
# ----------------------------------------------------- #
def btp_auth_check(btp_access_token:str):
    """
    Checks if the BTP access token is valid and authorized against the configured XSUAA service.

    This function performs the following steps:
    1. Retrieves the BTP access token from the request headers.
    2. Verifies that the BTP XSUAA service is configured in environment variables.
    3. Creates a security context using the access token and XSUAA credentials.
    4. Checks if the security context has the 'uaa.user' scope.

    If any of these checks fail, an HTTPException with status code 403 Forbidden is raised.

    Args:
        request: The incoming FastAPI request object.

    Raises:
        HTTPException: If the access token is missing, invalid, or not authorized.
    """
    try:
        if btp_access_token == "":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access token missing"
            )
        btp_app_env = AppEnv()
        btp_xsuaa = os.environ.get('BTP_XSUAA_SERVICE',"") 
        if btp_xsuaa == "":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="XSUAA service missing in environment variables"
                )
        uaa_service = btp_app_env.get_service(name=btp_xsuaa).credentials   
        security_context = xssec.create_security_context(btp_access_token, uaa_service)
        isAuthorized = security_context.check_scope('uaa.user')
        if not isAuthorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access token is avaiable but not authorized"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )  

#------------------------------------------------------------------------#
# Token supplier class
#------------------------------------------------------------------------#
class InMemoryTokenSupplier(identity_pool.SubjectTokenSupplier):
    
    def __init__(self, token: str):
        self.token = token

    def get_subject_token(self, context, request):
        # Simply return the in-memory token when requested by Google's STS
        if not self.token:
            raise exceptions.RefreshError("In-memory token is empty or missing.")
        return self.token

# -------------------------------------------------------------- #
# Using Workload Identity Federation, 
# get an impersonated service account credentials
# -------------------------------------------------------------- #
def get_credentials_using_wif(token: str) -> impersonated_credentials.Credentials:
    """
    Exchanges an external (BTP) OIDC token for Google STS tokens in-memory,
    and then generates impersonated credentials for a Google Service Account.
    """
    audience = (
        f"//iam.googleapis.com/projects/{GOOGLE_CLOUD_PROJECT_NUMBER}/"
        f"locations/{WIF_POOL_LOCATION}/workloadIdentityPools/{WIF_POOL_ID}/"
        f"providers/{WIF_PROVIDER_ID}"
    )
    token_supplier = InMemoryTokenSupplier(token)

    # Exchange the external BTP user JWT for a Google federated token
    pool_credentials = identity_pool.Credentials(
        audience=audience,
        subject_token_type="urn:ietf:params:oauth:token-type:jwt",
        token_url="https://sts.googleapis.com/v1/token",
        subject_token_supplier=token_supplier
    )

    # Impersonate your target Google Cloud Service Account using the identity pool
    scoped_credentials = impersonated_credentials.Credentials(
        source_credentials=pool_credentials,
        target_principal=TARGET_SERVICE_ACCOUNT,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    return scoped_credentials

# -------------------------------------------------------------- #
# Middleware - Preprocess request to check for BTP authentication
# -------------------------------------------------------------- #
class BTPAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Starlette middleware to preprocess incoming requests.
        """
        access_token = get_btp_access_token(request)

        # Check if the request is for the agent card
        if request.url.path == "/.well-known/agent-card.json":
            # Override the response with our security schemas
            response = await call_next(request)
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            try:
                # Parse the auto-generated card structure compiled by the ADK
                card_data = json.loads(body.decode("utf-8"))
                
                # Get the URL
                scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
                netloc = request.headers.get("x-forwarded-host") or request.url.netloc
                base_url = f"{scheme}://{netloc}"                

                # Dynamic Injection: Inject your structural fields 
                card_data["url"] = base_url
                card_data["securitySchemes"] = {
                    "Bearer": {
                        "bearerFormat": "JWT",
                        "description": "OAuth 2.0 JWT token required",
                        "scheme": "bearer",
                        "type": "http"
                    }
                }
                # Re-serialize back to transmission bytes
                new_body = json.dumps(card_data).encode("utf-8")

                async def new_iterator():
                    yield new_body
                response.body_iterator = new_iterator()

                response.headers["content-length"] = str(len(new_body))
                return response
            except Exception as e:
                # Fallback to the original payload if parsing fails
                print(f"Failed to patch agent card dynamically: {e}")
                return response
            
        else:
            try:
                # if the runtime is BTP, check if the user is indeed authorized to proceed
                # we do this check so we can debug locally 
                if _isbtp == "Y":
                    btp_auth_check(access_token)
                
                # Check if the credentials are already cached for this request matching the access_token
                cached_creds = credential_cache.get(access_token)

                # The cache only return the token if the google cloud credentials attached to this token are still valid
                if cached_creds:
                    credentials = cached_creds
                else:
                    # Get a new impersonated service account credentials
                    credentials = get_credentials_using_wif(access_token)

                    # Update the cache with the new token and expiry
                    credential_cache.set(access_token, credentials)
                
                # Bind the valid credentials to the request context so that the agent can use this
                token_token = request_credentials_ctx.set(credentials)

                try:
                    return await call_next(request)
                finally:
                    request_credentials_ctx.reset(token_token)      

            except Exception as e:
                # Prevent internal implementation leakage on credential fetching errors
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": f"Authentication/Federation failed: {str(e)}"}
                )           


# ----------------------------------------------------- #
# API Server
# ----------------------------------------------------- #
a2a_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Disable this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

a2a_app.add_middleware(BTPAuthMiddleware)

# ----------------------------------------------------- #
#    Run the app
# ----------------------------------------------------- #
uvicorn.run(a2a_app, host="0.0.0.0", port=os.getenv('PORT', 8001))