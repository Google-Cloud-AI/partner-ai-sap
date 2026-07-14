![Tutorials](assets/tutorials.png)

# SAP + Google Cloud: AI Innovation Space - Tutorials
This repository offers a curated path of tutorials, beginning with the fundamentals and progressively advancing toward complex integrations between SAP and Google Cloud AI capabilities.

---

## 📂 Repository Structure

| Module | Description |
| :--- | :--- |
| [**`01-adk-btp-simple`**](./01-adk-btp-simple) | In this tutorial, you will learn how to build a simple **Google Cloud Agent Development Kit (ADK)** agent that interacts with an SAP BTP service. You will build a python based REST API on SAP BTP to convert currencies and deploy it to the BTP Cloud Foundry runtime. Then, you will consume that API through the ADK agent. This establishes a foundation for more complex integrations where SAP processes and data are exposed to AI agents. 
| [**`02-adk-btp-secure`**](./02-adk-btp-secure) | In this tutorial, you will secure the REST API you created in the previous tutorial with BTP XSUAA service and then use the ADK agent to interact with it using OAuth access tokens. You will also register the ADK agent with Gemini Enterprise and interact with it using natural language to demonstrate how to securely integrate your AI agents with SAP BTP services.
| [**`03-adk-btp-secure-apim`**](./03-adk-btp-secure-apim) | Building on our previous tutorial, this tutorial covers exposing a backend SAP ERP OData API as a SAP BTP API Management (APIM) API and consuming it through an ADK-based agent deployed to Agent Runtime. You will learn to configure the policies, destinations and supporting services for principal propagation in SAP BTP API management so that the user context accessing the agent on Gemini Enterprise is also carried over to the backend SAP ERP applications.
| [**`04-adk-btp-a2a`**](./04-adk-btp-a2a) | This tutorial demonstrates how to deploy a Google Cloud ADK agent to SAP BTP and consume it from Gemini Enterprise using the A2A Protocol. The ADK Agent on BTP will use Workload Identity Federation to authenticate to Google Cloud. This allows for secure communication between SAP BTP and Google Cloud without the need for API keys or other credentials.

---


