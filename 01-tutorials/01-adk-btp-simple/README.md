#  **Connecting SAP BTP with ADK Agents Using a Custom API**
**Tech Stack:** `Python`, `SAP BTP`, `Cloud Foundry`, `FastAPI`

# **1\. Introduction**

## **Objective**
In this tutorial, you will learn how to build a production-ready API on SAP BTP using Python and FastAPI. This API will serve as a tool for a Google Cloud ADK (Agent Development Kit) agent in a subsequent tutorial.

## **Goals**
* Initialize a Python project using `uv`.
* Implement a currency conversion API using FastAPI.
* Test the API locally.
* Deploy the API to the SAP BTP, Cloud Foundry runtime.
* Secure the API with SAP BTP's UAA service.

### **Scope**

* Single API deployment on SAP BTP.
* Securing the API with a UAA service instance.

### **Out of Scope**

* Building the ADK agent that consumes this API.
* Complex SAP BTP service integrations beyond UAA.
* Building a custom frontend UI.

## **2\. Prerequisites & Setup**

Before you begin, ensure you have the following:

### **SAP BTP Resources**

* An [**SAP BTP Account**](https://account.hana.ondemand.com/) (Trial or Enterprise).
* The [**Cloud Foundry Environment**](https://help.sap.com/docs/SAP_CLOUD_PLATFORM/65de2977205c403bbc107264b8eccf4b/a4d3dd7482de4089b6572a63753d0434.html) enabled in your subaccount.
* A [**Space**](https://help.sap.com/docs/SAP_CLOUD_PLATFORM/65de2977205c403bbc107264b8eccf4b/1a2f6431947846c0a0f95c47a2aca0bd.html) created in your Cloud Foundry organization.

### **Local Development Environment**

* **uv** [installed](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10+ available.
* **Cloud Foundry CLI** [installed](https://github.com/cloudfoundry/cli#installation) and logged into your SAP BTP account (`cf login`).

```shell
# Create a uv project and navigate in to it
uv init adk-btp-simple-api
cd adk-btp-simple-api

# Create and activate python virtual environment
uv venv
source ./.venv/bin/activate

# Install the dependencies
uv add fastapi uvicorn requests cfenv sap-xssec
```

## **3\. Architecture Overview**

The architecture is straightforward:

1.  **The API:** A FastAPI application provides a simple REST endpoint for currency conversion. It runs within the SAP BTP Cloud Foundry runtime.
2.  **External Service:** The FastAPI application calls the public Frankfurter API to retrieve exchange rates.
3.  **Security:** SAP's User Account and Authentication (UAA) service will be used to secure the endpoint (though full implementation of the security logic in the Python code is out of scope for this guide).
4.  **The Agent (Future):** A Google ADK agent will make authenticated calls to the deployed API on SAP BTP to perform currency conversion tasks.

![Architecture Overview](assets/01-architecture-overview-btp.png)  
*(Note: You will need to create a corresponding architecture diagram `01-architecture-overview-btp.png` in the `assets` folder.)*

## **4\. Building the API**

### **Step 1: Create the API file**

Create a `main.py` file in your project directory (`adk-btp-simple-api`).

```shell
touch main.py
```

Open `main.py` and paste the following code. This creates a simple FastAPI server with one endpoint, `/convert`.

```python
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
```

### **Step 2: Run the API locally**

Start the local development server using `uvicorn`.

```shell
uvicorn main:app --port 8000 --reload
```

### **Step 3: Test the API locally**

Open a new terminal and use `curl` to send a request to your local API.

```shell
curl "http://localhost:8000/convert?amount=100&from_currency=usd&to_currency=eur"
```

You should see a JSON response with the converted amount.

## **5\. Deploying the API to SAP BTP**

### **Step 1: Create a `requirements.txt` file**

The Cloud Foundry buildpack needs a `requirements.txt` file to install dependencies.

```shell
uv pip freeze > requirements.txt
```

### **Step 2: Create the UAA Security Descriptor (`xs-security.json`)**

This file defines the security scopes and roles for your application. Create a file named `xs-security.json`.

```shell
touch xs-security.json
```

Paste the following content into `xs-security.json`.

```json
{
  "xsappname": "pyuaa",
  "tenant-mode": "dedicated",
  "description": "Security profile for Python UAA",
  "scopes": [
    {
      "name": "$XSAPPNAME.user",
      "description": "Default user scope"
    }
  ],
  "role-templates": [
    {
      "name": "User",
      "description": "Default user role",
      "scope-references": [
        "$XSAPPNAME.user"
      ]
    }
  ]
}
```

### **Step 3: Create the UAA Service Instance**

Run the following `cf` command to create an instance of the UAA service. You can change `pyuaa` to a more meaningful name.

```shell
# For dedicated tenants:
cf create-service xsuaa application pyuaa -c xs-security.json -t dedicated

# For shared tenants:
# cf create-service xsuaa application pyuaa -c xs-security.json
```

### **Step 4: Create the Deployment Manifest (`manifest.yml`)**

The manifest file tells Cloud Foundry how to deploy your application. Create a file named `manifest.yml`.

```shell
touch manifest.yml
```

Paste the following content into `manifest.yml`. This configuration binds the UAA service instance to your application.

```yaml
---
applications:
- name: currency-conversion-api
  random-route: true
  path: ./
  memory: 256M
  disk_quota: 1G 
  buildpacks: 
  - python_buildpack
  command: uvicorn main:app --host 0.0.0.0 --port $PORT
  services:
  - pyuaa
```

### **Step 5: Deploy to SAP BTP**

Push the application to your Cloud Foundry space.

```shell
cf push
```

## **6\. Testing the Deployed Agent**

Once the deployment is complete, find your application's URL.

```shell
cf apps
```

In the output, find the `currency-conversion-api` application and its URL under the `routes` column. You can then call your deployed API using `curl` again, this time with the BTP URL.

```shell
# Replace YOUR_APP_URL with the URL from 'cf apps'
curl "https://YOUR_APP_URL/convert?amount=100&from_currency=usd&to_currency=eur"
```

## **7\. Summary**

In this tutorial, you learned how to:
- Build a Python API using FastAPI.
- Run and test the API locally.
- Configure security using SAP's UAA service.
- Deploy a Python application to the SAP BTP, Cloud Foundry runtime.

This API is now ready to be consumed by other applications, including a Google ADK agent.

## **8\. Resources**

* [SAP BTP, Cloud Foundry Environment](https://help.sap.com/docs/SAP_CLOUD_PLATFORM/65de2977205c403bbc107264b8eccf4b/a4d3dd7482de4089b6572a63753d0434.html)
* [FastAPI Documentation](https://fastapi.tiangolo.com/)
* [Cloud Foundry CLI Reference](https://docs.cloudfoundry.org/cf-cli/cf-cli-ref.html)
* [uv Python Installer and Resolver](https://docs.astral.sh/uv/)
