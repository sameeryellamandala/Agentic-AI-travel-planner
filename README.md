# ✈️ AI Travel Planner

An **Agentic AI-powered travel planning system** that creates personalized travel itineraries by combining **LLM reasoning, real-time travel APIs, user preferences, budget constraints, and deterministic fallback estimation**.

The system uses **LangGraph** to orchestrate specialized tools for flights, hotels, weather, and transportation, while **Groq LLM** performs reasoning, ranking, constraint handling, and dynamic replanning.

---

## 🚀 Features

- 🤖 **Agentic AI Travel Planning**
  - Understands natural-language travel requirements.
  - Automatically selects and invokes appropriate tools.
  - Generates personalized day-by-day itineraries.

- ✈️ **Real-Time Flight Search**
  - Uses **Ignav API** for flight offers and pricing.
  - Supports date-specific flight search where available.

- 🏨 **Real-Time Hotel Search**
  - Uses **StayingAPI** for hotel availability and pricing.
  - Supports user preferences such as:
    - 3-Star
    - 4-Star
    - 5-Star
  - Falls back to estimated hotel pricing when live data is unavailable.

- 🌦️ **Weather-Aware Planning**
  - Uses **OpenWeather API**.
  - Adjusts itinerary recommendations according to weather conditions.

- 🚆 **Train Cost Estimation**
  - No unreliable/free train API dependency.
  - Estimates train costs using distance and configurable fare rates.

- 🚌 **Bus Cost Estimation**
  - Estimates bus fares using route distance and configurable transport rates.

- 💰 **Budget-Aware Planning**
  - Calculates the complete estimated trip cost.
  - Compares the plan against the user's budget.

- 🔄 **Dynamic Replanning**
  - If the initial plan exceeds the budget, the agent searches for alternatives and replans the trip.

- 🔎 **Live vs Estimated Data Transparency**
  - Clearly distinguishes between:
    - `LIVE`
    - `ESTIMATED`
    - `UNAVAILABLE`

- 🔐 **Secure API Key Management**
  - API credentials are stored using environment variables.
  - Secrets are never hardcoded into the application.

---

# 🏗️ System Architecture

```mermaid
flowchart TD

    A[👤 User] --> B[🧠 LangGraph Travel Agent]

    B --> C[Requirement Analysis]

    C --> D1[✈️ Flight Tool]
    C --> D2[🏨 Hotel Tool]
    C --> D3[🌦️ Weather Tool]
    C --> D4[🚆 Train Estimator]
    C --> D5[🚌 Bus Estimator]

    D1 --> E1[Ignav API]
    D2 --> E2[StayingAPI]
    D3 --> E3[OpenWeather API]

    D4 --> F1[Distance Calculation]
    D5 --> F1

    F1 --> F2[Deterministic Fare Estimator]

    E1 --> G[🔄 Data Normalization]
    E2 --> G
    E3 --> G
    F2 --> G

    G --> H[🎯 Preference Filtering]

    H --> I[📊 Option Ranking]

    I --> J[💰 Budget Calculation]

    J --> K{Within Budget?}

    K -->|Yes| L[📝 Generate Itinerary]

    K -->|No| M[🔄 Dynamic Replanning]

    M --> H

    L --> N[🤖 Groq LLM]

    N --> O[🌍 Final Personalized Itinerary]
