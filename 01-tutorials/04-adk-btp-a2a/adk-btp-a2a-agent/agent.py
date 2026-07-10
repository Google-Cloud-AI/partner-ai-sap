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
import requests
from google.adk.models import Gemini
from google.adk.agents.llm_agent import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.genai import types, Client
from context_store import request_credentials_ctx, request_client_ctx
from dotenv import load_dotenv


load_dotenv(override=True)
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION")

FRANKFURTER_API_URL = "https://api.frankfurter.app/latest"

# ----------------------------------------------------- #
# Convert amount from one currency to another
# ----------------------------------------------------- #
def convert_currency(amount, from_currency, to_currency):
    """
    Fetches the current exchange rate between two currencies using the Frankfurter API.

    Args:
        currency_from (str): The ISO 4217 code for the source currency (e.g., 'USD').
        currency_to (str): The ISO 4217 code for the target currency (e.g., 'EUR').

    Returns:
        dict: A dictionary containing the exchange rate data on success, or an error message if the request fails.
              Example success: {"amount": 1.0, "base": "USD", "date": "2023-10-27", "rates": {"EUR": 0.95}}
              Example failure: {"error": "..."}

    Raises:
        requests.exceptions.RequestException: If the network request fails (handled by try-except).
    """
    try:
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        params = {
            "amount": amount,
            "from": from_currency,
            "to": to_currency
        }
        response = requests.get(FRANKFURTER_API_URL, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------- #
# Thread-Safe Context-Credential LLM Subclass
# ---------------------------------------------------------------------- #
class ContextCredentialGemini(Gemini):
    """
    A custom Gemini model integration that dynamically resolves and caches
    credentials on a per-request basis using thread-safe context variables.
    """
    @property
    def api_client(self) -> Client:

        # Check if we already have a cached client in this request context
        cached_client = request_client_ctx.get()
        if cached_client is not None:
            return cached_client

        active_credentials = request_credentials_ctx.get()
        
        if active_credentials:
            # Create the client using the supplied context credentials
            client = Client(
                vertexai=True,
                credentials=active_credentials,
                project=GOOGLE_CLOUD_PROJECT,
                location=VERTEX_AI_LOCATION,
                http_options=types.HttpOptions(
                    headers=self._tracking_headers(),
                    retry_options=self.retry_options,
                )
            )
        else:
            # Fallback client replicating standard ADK behavior (ADC)
            client = Client(
                http_options=types.HttpOptions(
                    headers=self._tracking_headers(),
                    retry_options=self.retry_options,
                )
            )
        
        # Cache the client in the context so it survives garbage collection for this request
        request_client_ctx.set(client)
        return client


# ----------------------------------------------------- #
# Root agent
# ----------------------------------------------------- #
root_agent = Agent(
    name="root_agent",
    model=ContextCredentialGemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="Answer user questions by using the tools available to you. If the user asks for currency conversion, use the convert_currency to convert the currency.",
    tools=[convert_currency],
)

# ----------------------------------------------------- #
# Dynamic credential executor 
# ----------------------------------------------------- #
def dynamic_credential_executor_factory(runner, **kwargs):
    """
    Called by the A2A runtime whenever a new JSON-RPC agent message is processed.
    """
    # Fetch the  token assigned to this specific concurrent execution thread
    active_credentials = request_credentials_ctx.get()
    
    if active_credentials:
        # Rebind the underlying impersonated service account credential
        runner.client = Client(
            vertexai=True,
            credentials=active_credentials,
            project=GOOGLE_CLOUD_PROJECT,
            location=VERTEX_AI_LOCATION
        )
    
    return A2aAgentExecutor(runner=runner, **kwargs)

# ----------------------------------------------------- #
# Create an A2A agent
# ----------------------------------------------------- #
a2a_app = to_a2a(
    root_agent, 
    port=os.getenv('PORT', 8001),
    # agent_executor_factory=dynamic_credential_executor_factory
)