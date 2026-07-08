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

"""ADK BTP Simple Agent with secure authentication.

This agent demonstrates how to integrate with a secured OpenAPI endpoint
using Google ADK's OpenAPIToolset and manage authentication headers via
ToolContext state.
"""

from aiohttp import client_middleware_digest_auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import os
import re
import json
import google.auth
from google.adk.tools import ToolContext
from google.adk.tools.openapi_tool import OpenAPIToolset
from pathlib import Path

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

#Auth ID used in Gemini Enterprise. Change this if you used a different auth ID
GE_AUTH_ID = "btp-xsuaa-adk-demos"
CURRENCY_CONVERSION_API_SPEC_FILENAME = "currency-conversion-apispec.json"
SALES_ORDERS_API_SPEC_FILENAME = "API_SALES_ORDER_SRV_Optimized.json"


# ----------------------------------------------------- #
# Get Auth headers from the state
# ----------------------------------------------------- #
def get_auth_headers(context: ToolContext) -> dict:
    """Retrieves authentication headers from the tool context state.

    Args:
        context: The ToolContext object containing the current state.

    Returns:
        A dictionary with the Authorization header if a token is present,
        otherwise an empty dictionary.
    """
    token = context.state.get(GE_AUTH_ID)
    if not token:
        return {"Authorization": f"Bearer {os.getenv('TEMP_TOKEN')}"}

    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------- #
# Load API Specification for creating OpenAPI Toolset
# ----------------------------------------------------- #
def get_open_api_spec(spec_file_name:str) -> dict:
    base_dir = Path(__file__).resolve().parent
    apispec_file_path = f"{base_dir}/{spec_file_name}"
    openapi_spec_dict = {}
    with open(apispec_file_path, "r") as f:
        openapi_spec_dict = json.load(f)

    # remove the security entry - not needed for toolset creation, as we are using header_provider
    if "security" in openapi_spec_dict:
        del openapi_spec_dict["security"]
    return openapi_spec_dict

#------------------------------------------------------------------------#
# OpenAPI Toolsets
#------------------------------------------------------------------------#

currency_conversion_toolset = OpenAPIToolset(
    spec_dict=get_open_api_spec(CURRENCY_CONVERSION_API_SPEC_FILENAME),
    header_provider=get_auth_headers
)

sales_orders_toolset = OpenAPIToolset(
    spec_dict=get_open_api_spec(SALES_ORDERS_API_SPEC_FILENAME),
    header_provider=get_auth_headers,
)


#------------------------------------------------------------------------#
# Tool for printing out the state - only use in Dev
#------------------------------------------------------------------------#
def get_agent_state(tool_context: ToolContext):
    """Returns the agent's current state as a JSON string.

    This function is intended for development and debugging purposes.

    Args:
        tool_context: The ToolContext object containing the agent's state.

    Returns:
        A JSON string representation of the agent's state, or an error message
        if an exception occurs.
    """
    try:
        _state = tool_context.state.to_dict()
        return json.dumps(_state)
    except Exception as e:
        return f"Error in getting state {e}"

# ----------------------------------------------------- #
# Create Root Agent
# ----------------------------------------------------- #
root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""
    Answer user questions by using the tools available to you. 
    If the user asks for currency conversion, use the `currency_conversion_toolset` to convert the currency. 
    If the user asks about Sales Orders, use the `sales_orders_toolset` to get the sales orders.
    Return the exact response of `get_agent_state` when asked to print the tool context or print the state
    """,
    tools=[
        currency_conversion_toolset,
        sales_orders_toolset,
        get_agent_state
    ],
)

# ----------------------------------------------------- #
# Create Application
# ----------------------------------------------------- #
app = App(
    root_agent=root_agent,
    name="app",
)
