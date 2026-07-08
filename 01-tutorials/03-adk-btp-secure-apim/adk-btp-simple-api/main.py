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
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from cfenv import AppEnv
from sap import xssec

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
def btp_auth_check(request:Request):
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
        btp_access_token = get_btp_access_token(request)
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

# ----------------------------------------------------- #
# API Server
# ----------------------------------------------------- #
app = FastAPI(
    title="Currency Conversion API",
    description="A simple API for getting currency conversions using the Frankfurter API.",
    version="1.0.0"
)

FRANKFURTER_API_URL = "https://api.frankfurter.app/latest"

# ----------------------------------------------------- #
# Middleware - CORS
# ----------------------------------------------------- #
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], # Disable this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------------------------------- #
# Middleware - Preprocess request to check for BTP authentication
# ----------------------------------------------------- #
@app.middleware("http")
async def preprocess_request_middleware(request: Request, call_next):
    """
    FastAPI middleware to preprocess incoming requests.

    This middleware performs the following actions:
    - For any request path other than "/apispec.json", it calls `btp_auth_check`
      to validate BTP authentication.
    - If `btp_auth_check` raises an HTTPException (e.g., due to missing or invalid
      token), the middleware will propagate that exception, resulting in a 403 Forbidden response.
    - If authentication passes or the path is "/apispec.json", it proceeds to the
      next handler in the request-response cycle.

    Args:
        request: The incoming FastAPI request object.
        call_next: The next ASGI callable in the middleware stack.

    Returns:
        fastapi.responses.Response: The response generated by the subsequent
                                     middleware or route handler.
    """
    if not request.url.path == "/apispec.json":
        btp_auth_check(request)
    response = await call_next(request)
    return response

# ----------------------------------------------------- #
# OpenAPI spec endpoint
# ----------------------------------------------------- #
@app.get("/apispec.json",  include_in_schema=False)
async def get_open_api_endpoint(request: Request):
    """
    Generates and returns the OpenAPI specification (swagger JSON) for this API.

    This endpoint dynamically sets the server URL in the OpenAPI schema based on
    the incoming request's base URL, making the documentation self-contained
    and correct for different deployment environments.

    Args:
        request: The incoming FastAPI request object.

    Returns:
        JSONResponse: A FastAPI JSONResponse containing the OpenAPI schema.
    """
    base_url = str(request.base_url).rstrip("/")
    openapi_schema = get_openapi(
        title="Currency Conversion API",
        version="1.0.0",
        routes=app.routes,
    )

    openapi_schema["servers"] = [{"url": base_url}]
    return JSONResponse(content=openapi_schema)

# ----------------------------------------------------- #
# BTP API Endpoint
# ----------------------------------------------------- #
@app.get("/convert", summary="Convert Currency", tags=["Currency"])
async def convert_currency(
    amount: float = Query(..., gt=0, description="The amount to convert"),
    from_currency: str = Query(..., min_length=3, max_length=3, description="Base currency code (e.g., USD)"),
    to_currency: str = Query(..., min_length=3, max_length=3, description="Target currency code (e.g., EUR)")
):
    """
    Convert a specific amount from one currency to another using the Frankfurter API.

    This endpoint takes an amount, a source currency, and a target currency,
    then queries the Frankfurter API to perform the conversion.

    Args:
        amount: The numerical amount to be converted. Must be greater than 0.
        from_currency: The 3-letter currency code (ISO 4217) of the base currency.
                       Example: "USD".
        to_currency: The 3-letter currency code (ISO 4217) of the target currency.
                     Example: "EUR".

    Returns:
        dict: A dictionary containing the conversion results from the Frankfurter API.

    Raises:
        HTTPException:
            - 400 Bad Request: If the Frankfurter API returns an error (e.g., invalid currency codes).
            - 500 Internal Server Error: If there is an issue connecting to the Frankfurter API
                                         or other unexpected internal errors.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    params = {
        "amount": amount,
        "from": from_currency,
        "to": to_currency
    }
    try:
        response = requests.get(FRANKFURTER_API_URL, params=params)
        response.raise_for_status()
        return response.json()
    except requests.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Error from Frankfurter API: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error while connecting to the conversion service.")
