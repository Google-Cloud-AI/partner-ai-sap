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

from fastapi import FastAPI, HTTPException, Query
import requests

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

