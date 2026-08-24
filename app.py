# AI Travel Planner using LangGraph + Groq + Streamlit
import os
import streamlit as st
from typing import TypedDict, List, Dict, Annotated, Any
from operator import add
from dotenv import load_dotenv

# Load Environment
load_dotenv()
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
os.environ["STAYING_API_KEY"] = os.getenv("STAYING_API_KEY", "")
os.environ["OPENWEATHER_API_KEY"] = os.getenv("OPENWEATHER_API_KEY", "")
os.environ["IGNAV_API_KEY"] = os.getenv("IGNAV_API_KEY", "")
os.environ["PEXELS_API_KEY"] = os.getenv("PEXELS_API_KEY", "")

from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage

# Import internal services and tools
from services.mock_apis import get_flight_data, get_hotel_data, get_weather_data
from services.pexels_service import get_pexels_image
from tools.estimators import calculate_distance, estimate_train_fare, estimate_bus_fare
from utils.budget import calculate_budget, parse_budget

# LLM & GRAPH LOGIC
llm = ChatGroq(model="qwen/qwen3.6-27b", temperature=0.3)

class TravelState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage], add]
    source_city: str
    destination: str
    budget: str
    days: int
    start_date: str
    end_date: str
    interests: List[str]
    hotel_type: str
    transport_mode: str
    
    # New state fields from PRD
    weather: Dict[str, Any]
    places_to_visit: List[Dict]
    flights: List[Dict]
    hotels: List[Dict]
    train_estimate: Dict[str, Any]
    bus_estimate: Dict[str, Any]
    food_recommendations: List[Dict]
    itinerary: List[Dict]
    budget_breakdown: Dict[str, Any]
    warnings: List[str]
    
    estimated_cost: str
    current_step: str

# --- Nodes ---

def collect_preferences(state: TravelState):
    return {"current_step": "Preferences Collected"}

def get_weather(state: TravelState):
    weather_data = get_weather_data(state['destination'])
    return {"weather": weather_data, "current_step": "Weather Fetched"}

def get_hotels(state: TravelState):
    hotel_data = get_hotel_data(state['destination'], state['start_date'], state['end_date'], state['hotel_type'])
    return {"hotels": [hotel_data], "current_step": "Hotels Found"}

def get_flights(state: TravelState):
    flight_data = get_flight_data(state['source_city'], state['destination'], state['start_date'])
    return {"flights": [flight_data], "current_step": "Flights Found"}

def estimate_transport(state: TravelState):
    dist = calculate_distance(state['source_city'], state['destination'])
    train_est = estimate_train_fare(dist)
    bus_est = estimate_bus_fare(dist)
    return {"train_estimate": train_est, "bus_estimate": bus_est, "current_step": "Transport Estimated"}

def find_places(state: TravelState):
    prompt = f"Suggest the top 6 tourist attractions in {state['destination']} for interests: {', '.join(state['interests'])}. Give ONLY the place names, one per line."
    response = llm.invoke(prompt)
    
    place_names = [p.strip("- *") for p in response.content.split("\n") if p.strip()][:6]
    
    places_with_images = []
    for name in place_names:
        img_info = get_pexels_image(f"{name} {state['destination']}")
        places_with_images.append({
            "name": name,
            "image": img_info
        })
        
    return {"places_to_visit": places_with_images, "current_step": "Places Found"}

def food_recommendation_node(state: TravelState):
    prompt = f"Suggest 6 famous foods in {state['destination']}. Only names."
    response = llm.invoke(prompt)
    
    food_names = [f.strip("- *") for f in response.content.split("\n") if f.strip()][:6]
    
    foods_with_images = []
    for name in food_names:
        img_info = get_pexels_image(f"{name} {state['destination']}")
        foods_with_images.append({
            "name": name,
            "image": img_info
        })
        
    return {"food_recommendations": foods_with_images, "current_step": "Food Found"}

def generate_itinerary(state: TravelState):
    place_names = [p["name"] for p in state.get("places_to_visit", [])]
    food_names = [f["name"] for f in state.get("food_recommendations", [])]
    
    weather_info = state.get("weather", {}).get("condition", "Unknown")
    
    prompt = f"""Detailed {state['days']}-day itinerary for {state['destination']} 
    visiting: {', '.join(place_names)}
    and eating: {', '.join(food_names)}.
    Weather is expected to be {weather_info}.
    Use Markdown with headers for each day.
    
    IMPORTANT: OUTPUT ONLY THE ITINERARY IN MARKDOWN FORMAT. DO NOT OUTPUT ANY THINKING, REASONING, OR CONVERSATIONAL FILLER."""
    
    response = llm.invoke(prompt)
    content = response.content
    
    # Strip <think> blocks if the model generates them
    if "<think>" in content and "</think>" in content:
        content = content.split("</think>")[-1].strip()
        
    return {"itinerary": [{"plan": content}], "current_step": "Itinerary Generated"}

def calculate_budget_node(state: TravelState):
    budget_info = calculate_budget(state)
    return {
        "budget_breakdown": budget_info,
        "estimated_cost": f"{budget_info['total']:,} {budget_info['currency']}",
        "current_step": "Budget Calculated"
    }

def check_budget_node(state: TravelState):
    user_budget = parse_budget(state['budget'])
    calc_budget = state.get("budget_breakdown", {}).get("total", 0)
    warnings = state.get("warnings", [])
    
    if user_budget > 0 and calc_budget > user_budget:
        warnings.append(f"Calculated trip cost ({calc_budget:,}) exceeds target budget ({user_budget:,}). Recommended adjusting transport mode, hotel tiers, or duration.")
        
    return {"warnings": warnings, "current_step": "Completed"}

# --- Graph Build ---
builder = StateGraph(TravelState)

builder.add_node("collect_preferences", collect_preferences)
builder.add_node("get_weather", get_weather)
builder.add_node("get_hotels", get_hotels)
builder.add_node("get_flights", get_flights)
builder.add_node("estimate_transport", estimate_transport)
builder.add_node("find_places", find_places)
builder.add_node("food_recommendation_node", food_recommendation_node)
builder.add_node("generate_itinerary", generate_itinerary)
builder.add_node("calculate_budget_node", calculate_budget_node)
builder.add_node("check_budget_node", check_budget_node)

builder.add_edge(START, "collect_preferences")
builder.add_edge("collect_preferences", "get_weather")
builder.add_edge("get_weather", "get_hotels")
builder.add_edge("get_hotels", "get_flights")
builder.add_edge("get_flights", "estimate_transport")
builder.add_edge("estimate_transport", "find_places")
builder.add_edge("find_places", "food_recommendation_node")
builder.add_edge("food_recommendation_node", "generate_itinerary")
builder.add_edge("generate_itinerary", "calculate_budget_node")
builder.add_edge("calculate_budget_node", "check_budget_node")
builder.add_edge("check_budget_node", END)

graph = builder.compile()

# =========================
# PROFESSIONAL CHATBOT UI
# =========================
st.set_page_config(
    page_title="VoyageAI 2.0 | Agent", 
    layout="wide", 
    page_icon="🤖", 
    initial_sidebar_state="expanded" 
)

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    [data-testid="stSidebar"] { background-color: #161B22; border-right: 1px solid #30363D; }
    .main-header { font-size: 2.5rem; font-weight: 800; background: linear-gradient(90deg, #58A6FF, #BC8CFF); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }
    .chat-bubble { background-color: #1F2937; padding: 20px; border-radius: 15px; border-left: 5px solid #2563EB; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
    .metric-card { background: #161B22; border: 1px solid #30363D; border-radius: 10px; padding: 15px; text-align: center; }
    .stButton>button { border-radius: 8px; background: linear-gradient(135deg, #238636 0%, #2ea043 100%); color: white; border: none; font-weight: 600; padding: 0.6rem; transition: transform 0.2s ease;}
    .stButton>button:hover { transform: translateY(-2px); }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #161B22; border: 1px solid #30363D; border-radius: 8px 8px 0 0; padding: 10px 20px; color: #8B949E; }
    .stTabs [aria-selected="true"] { background-color: #1F2937; border-bottom: 2px solid #58A6FF; color: #58A6FF; }
    header[data-testid="stHeader"] { background-color: transparent !important; }
    .badge-live { background-color: #2ea043; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .badge-est { background-color: #d29922; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .badge-unavail { background-color: #da3633; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("<h2 style='color: #58A6FF;'>🤖 Voyage Agent 2.0</h2>", unsafe_allow_html=True)
    st.caption("AI-Powered Travel Intelligence (Real-Time)")
    st.divider()
    
    with st.expander("📍 Route Details", expanded=True):
        src = st.text_input("Origin", "Mumbai")
        dest = st.text_input("Destination", "Tokyo")
        col1, col2 = st.columns(2)
        s_date = col1.date_input("Start")
        e_date = col2.date_input("End")
    
    with st.expander("💳 Budget & Comfort", expanded=True):
        budget_val = st.text_input("Target Budget", "200,000 INR")
        trans_mode = st.selectbox("Preferred Transport", ["Flight", "Train", "Bus"])
        h_type = st.selectbox("Hotel Class", ["Budget", "3-star", "4-star", "5-star"])
    
    user_interests = st.multiselect("Interests", ["Food", "Adventure", "Culture", "Shopping", "Nature"], default=["Food", "Culture"])
    
    st.write("")
    generate_btn = st.button("🚀 Plan My Journey")

# --- Main Interface ---
if not generate_btn:
    st.markdown("<h1 class='main-header'>Welcome to VoyageAI 2.0</h1>", unsafe_allow_html=True)
    st.markdown("#### Your personal AI travel concierge. Fill in the details on the left to generate a professional travel blueprint utilizing live data.")
    
    st.write("")
    st.write("")
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        st.info("🧠 **Agentic Search**\n\nAI agents find real locations, activities, and hotels based on your specific interests.")
    with c2: 
        st.info("🚆 **Dynamic Transit**\n\nReal-time flight data combined with smart deterministic train and bus cost estimators.")
    with c3: 
        st.info("📊 **Budget Optimized**\n\nSmart mathematical routing ensures your entire itinerary stays perfectly within range, checking live vs target budget.")
        
else:
    with st.spinner("🤖 **Agent is formulating your perfect trip using Live Data & Estimators...**"):
        d_count = (e_date - s_date).days if (e_date - s_date).days > 0 else 1
        result = graph.invoke({
            "source_city": src, "destination": dest, "budget": budget_val,
            "days": d_count, "start_date": str(s_date), "end_date": str(e_date),
            "interests": user_interests, "hotel_type": h_type, "transport_mode": trans_mode,
            "weather": {}, "places_to_visit": [], "flights": [], "hotels": [],
            "train_estimate": {}, "bus_estimate": {}, "food_recommendations": [],
            "itinerary": [], "budget_breakdown": {}, "warnings": [],
            "estimated_cost": "", "messages": [], "current_step": ""
        })

    if result.get("warnings"):
        for w in result["warnings"]:
            st.warning(f"⚠️ {w}")

    # Summary Bar
    st.markdown(f"### 🌏 Journey to {dest}")
    
    w_data = result.get("weather", {})
    w_badge = "<span class='badge-live'>LIVE</span>" if w_data.get("source_type") == "LIVE" else "<span class='badge-unavail'>UNAVAILABLE</span>"
    w_text = f"{w_data.get('temperature', '--')}°C, {w_data.get('condition', '--')}"
    
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f"<div class='metric-card'><small>DURATION</small><br><b style='font-size: 1.2rem; color: #58A6FF;'>{d_count} Days</b></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-card'><small>WEATHER</small> {w_badge}<br><b style='font-size: 1.2rem; color: #58A6FF;'>{w_text}</b></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-card'><small>PREF. TRANSPORT</small><br><b style='font-size: 1.2rem; color: #58A6FF;'>{trans_mode}</b></div>", unsafe_allow_html=True)
    with m4: st.markdown(f"<div class='metric-card'><small>CALC. TRIP COST</small><br><b style='font-size: 1.2rem; color: #3FB950;'>{result['estimated_cost']}</b></div>", unsafe_allow_html=True)

    st.write("")

    # Chat-Style Results Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Full Itinerary", "🏨 Logistics & Booking", "✨ Highlights Gallery", "💰 Budget Breakdown"])

    with tab1:
        with st.chat_message("assistant"):
            st.markdown("Here is your detailed daily schedule optimized for your interests:")
            if result.get("itinerary"):
                st.markdown(f"<div class='chat-bubble'>{result['itinerary'][0]['plan']}</div>", unsafe_allow_html=True)

    with tab2:
        with st.chat_message("assistant"):
            st.write("I've analyzed live APIs and fallback estimators for your stay and travel:")
            c_h, c_t = st.columns(2)
            
            with c_h:
                st.subheader("🏠 Stays")
                for h in result.get("hotels", []):
                    if h.get("source_type") == "LIVE":
                        st.success(f"**{h.get('name')}** [LIVE (StayingAPI)]\n\nPrice: {h.get('price_per_night')} {h.get('currency')}/night\n\nRating: {h.get('rating')}/5.0")
                    else:
                        st.info(f"**Fallback Estimate** [ESTIMATED]\n\nReason: {h.get('reason')}\n\nPrice: {h.get('price_per_night')} {h.get('currency')}/night")
                        
            with c_t:
                st.subheader("🎫 Transport Options")
                # Flight
                for f in result.get("flights", []):
                    if f.get("source_type") == "LIVE":
                        st.success(f"**Flight ({f.get('airline')})** [LIVE (Ignav)]\n\nPrice: {f.get('price')} {f.get('currency')}")
                    else:
                        st.error(f"**Flight** [UNAVAILABLE]\n\nReason: {f.get('error')}")
                
                # Train
                t_est = result.get("train_estimate", {})
                if t_est:
                    st.warning(f"**Train** [ESTIMATED]\n\nFare Range: {t_est.get('min_price')} - {t_est.get('max_price')} {t_est.get('currency')}")
                
                # Bus
                b_est = result.get("bus_estimate", {})
                if b_est:
                    st.warning(f"**Bus** [ESTIMATED]\n\nFare Range: {b_est.get('min_price')} - {b_est.get('max_price')} {b_est.get('currency')}")

    with tab3:
        with st.chat_message("assistant"):
            st.write("Visualizing your journey... here are the top spots and eats you shouldn't miss:")
            
            st.subheader("📍 Must-Visit Attractions")
            cols = st.columns(2)
            for idx, place in enumerate(result.get("places_to_visit", [])):
                with cols[idx % 2]:
                    with st.container(border=True):
                        st.markdown(f"<h5 style='text-align: center;'>{place['name']}</h5>", unsafe_allow_html=True)
                        if place.get('image', {}).get('available'):
                            st.image(place['image']['image_url'], use_container_width=True)
                            st.caption(f"📷 Photo by {place['image'].get('photographer', 'Unknown')} on Pexels")
                        else:
                            st.info("📷 Image unavailable")

            st.divider()
            
            st.subheader("🍱 Local Eats")
            f_cols = st.columns(3)
            for idx, food in enumerate(result.get("food_recommendations", [])):
                with f_cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"<h6 style='text-align: center;'>🍴 {food['name']}</h6>", unsafe_allow_html=True)
                        if food.get('image', {}).get('available'):
                            st.image(food['image']['image_url'], use_container_width=True)
                            st.caption(f"📷 Photo by {food['image'].get('photographer', 'Unknown')} on Pexels")
                        else:
                            st.info("📷 Image unavailable")

    with tab4:
        with st.chat_message("assistant"):
            st.write("Here is the detailed cost breakdown:")
            breakdown = result.get("budget_breakdown", {}).get("breakdown", {})
            curr = result.get("budget_breakdown", {}).get("currency", "INR")
            
            st.markdown(f"""
            - **Transport**: {breakdown.get('transport', 0):,} {curr}
            - **Hotel**: {breakdown.get('hotel', 0):,} {curr}
            - **Food**: {breakdown.get('food', 0):,} {curr}
            - **Activities**: {breakdown.get('activities', 0):,} {curr}
            
            **Total Estimated Cost**: {result['estimated_cost']}
            """)

    st.toast("Travel plan finalized and formatted!", icon="✅")
