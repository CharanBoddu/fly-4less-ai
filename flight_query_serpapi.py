# flight_query_serpapi.py (FIXED VERSION)
import os
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime
import json
import asyncio

load_dotenv()

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SERPAPI_KEY = os.environ.get('SERPAPI_KEY')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY not found in .env. Get one at https://serpapi.com/")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

SERPAPI_BASE_URL = "https://serpapi.com/search"


def extract_flight_details(user_input):
    """
    Uses Gemini API to extract structured flight query details from natural language input.
    """
    try:
        response = model.generate_content(
            contents=[f"""You are a flight booking assistant. Extract flight details from this query and return ONLY valid JSON, nothing else.

Query: "{user_input}"

Return ONLY this JSON format (no markdown, no explanation):
{{"departure": "airport_code", "destination": "airport_code", "depart_date": "YYYY-MM-DD", "return_date": "YYYY-MM-DD or null", "adults": 1, "children": 0}}

Example: {{"departure": "YYZ", "destination": "JFK", "depart_date": "2025-03-10", "return_date": "2025-03-15", "adults": 1, "children": 0}}
"""])

        text = response.text.strip()
        text = text.replace(chr(96), "").strip()
        if text.startswith("json"):
            text = text[4:].strip()
        
        flight_data = json.loads(text)
        return flight_data
    
    except Exception as e:
        print(f"Error extracting flight details: {e}")
        return None


def validate_flight_data(flight_data):
    """
    Validates flight data and returns missing fields.
    """
    if not flight_data:
        return False, [], "I couldn't understand your request. Could you rephrase it?"
    
    required_fields = {
        'departure': 'departure airport (e.g., YYZ for Toronto)',
        'destination': 'destination airport (e.g., JFK for New York)',
        'depart_date': 'departure date (e.g., March 10, 2025)'
    }
    
    missing = []
    for field, description in required_fields.items():
        if not flight_data.get(field) or flight_data.get(field) == "null":
            missing.append(description)
    
    if missing:
        message = "I need more information:\n" + "\n".join([f"• {item}" for item in missing])
        return False, missing, message
    
    try:
        depart = datetime.strptime(flight_data['depart_date'], '%Y-%m-%d')
        if depart < datetime.now():
            return False, ['depart_date'], "The departure date must be in the future."
        
        if flight_data.get('return_date') and flight_data['return_date'] != "null":
            return_date = datetime.strptime(flight_data['return_date'], '%Y-%m-%d')
            if return_date <= depart:
                return False, ['return_date'], "The return date must be after the departure date."
    except ValueError:
        return False, ['date_format'], "Invalid date format. Please use a clear date format."
    
    return True, [], "All required information is present."


def normalize_airport_code(code):
    """
    Normalizes airport codes to uppercase 3-letter IATA code.
    """
    if not code or code == "null":
        return None
    
    code = code.upper().strip()
    
    if len(code) == 3 and code.isalpha():
        return code
    
    return None


def _search_flights_serpapi(departure, destination, depart_date, return_date=None, adults=1, children=0, deep_search=True, show_hidden=True):
    """
    Search flights using SerpAPI.
    """
    try:
        flight_type = 1 if return_date and return_date != "null" else 2
        
        params = {
            "engine": "google_flights",
            "departure_id": departure,
            "arrival_id": destination,
            "outbound_date": depart_date,
            "type": flight_type,
            "gl" : "ca",
            "currency": "CAD",
            "adults": adults,
            "children": children,
            "api_key": SERPAPI_KEY,
            "deep_search": "true" if deep_search else "false",
            "show_hidden": "true" if show_hidden else "false",
        }
        
        if return_date and return_date != "null":
            params["return_date"] = return_date
        
        print(f"🔍 Searching SerpAPI...")
        response = requests.get(SERPAPI_BASE_URL, params=params, timeout=120)
        response.raise_for_status()
        
        return response.json()
    
    except Exception as e:
        print(f"Error in SerpAPI search: {e}")
        raise


def _parse_serpapi_results(api_response):
    """
    Parses SerpAPI response properly.
    """
    try:
        flights_data = {
            'flights': [],
            'price_level': None,
            'lowest_price': None,
            'error': None
        }
        
        # Check for errors
        if api_response.get('search_metadata', {}).get('status') == 'Error':
            flights_data['error'] = api_response.get('search_metadata', {}).get('error')
            print(f"API Error: {flights_data['error']}")
            return flights_data
        
        # Get price insights
        price_insights = api_response.get('price_insights', {})
        flights_data['price_level'] = price_insights.get('price_level', 'unknown')
        flights_data['lowest_price'] = price_insights.get('lowest_price')
        
        print(f"Price insights: lowest={flights_data['lowest_price']}, level={flights_data['price_level']}")
        
        # Parse best flights
        best_flights = api_response.get('best_flights', [])
        print(f"Found {len(best_flights)} best flights")
        
        for flight_group in best_flights:
            flight_info = _extract_flight_info(flight_group)
            if flight_info:
                flights_data['flights'].append(flight_info)
        
        # Parse other flights
        other_flights = api_response.get('other_flights', [])
        print(f"Found {len(other_flights)} other flights")
        
        for flight_group in other_flights:
            flight_info = _extract_flight_info(flight_group)
            if flight_info:
                flights_data['flights'].append(flight_info)
        
        # Sort by price
        flights_data['flights'].sort(key=lambda x: x['price'] if isinstance(x['price'], (int, float)) else float('inf'))
        
        print(f"✅ Total flights: {len(flights_data['flights'])}")
        
        return flights_data
    
    except Exception as e:
        print(f"Error parsing: {e}")
        import traceback
        traceback.print_exc()
        return {'flights': [], 'error': str(e), 'price_level': 'unknown', 'lowest_price': None}


def _extract_flight_info(flight_group):
    """
    Extracts flight information from SerpAPI flight group.
    Handles multi-leg flights (with layovers).
    """
    try:
        flights = flight_group.get('flights', [])
        if not flights:
            return None
        
        # Get first and last flight
        first_flight = flights[0]
        last_flight = flights[-1]
        
        # Get price
        price = flight_group.get('price')
        if price is None:
            return None
        
        # Format departure time (from first flight)
        dep_time = first_flight.get('departure_airport', {}).get('time', 'N/A')
        
        # Format arrival time (from last flight)
        arr_time = last_flight.get('arrival_airport', {}).get('time', 'N/A')
        
        # Format duration
        total_duration = flight_group.get('total_duration', 0)
        hours = total_duration // 60
        minutes = total_duration % 60
        duration_str = f"{hours}h {minutes}m"
        
        # Count stops (layovers)
        layovers = flight_group.get('layovers', [])
        stops = len(layovers)
        
        # Get airline (for multi-airline, show first)
        airline = first_flight.get('airline', 'Unknown')
        
        flight_info = {
            'airline': airline,
            'departure': dep_time,
            'arrival': arr_time,
            'duration': duration_str,
            'stops': stops,
            'price': price,
            'price_str': f"${price}",
        }
        
        print(f"  ✓ {airline} - ${price} ({duration_str}, {stops} stops)")
        
        return flight_info
    
    except Exception as e:
        print(f"Error extracting flight: {e}")
        return None


async def search_flights_serpapi(departure, destination, depart_date, return_date=None, adults=1, children=0, deep_search=True, show_hidden=True):
    """
    Search for flights using SerpAPI.
    """
    departure = normalize_airport_code(departure)
    destination = normalize_airport_code(destination)
    
    if not departure or not destination:
        raise ValueError("Invalid airport codes provided")
    
    try:
        print(f"🔎 Searching SerpAPI (deep_search={deep_search}, show_hidden={show_hidden})...")
        
        loop = asyncio.get_event_loop()
        api_response = await loop.run_in_executor(
            None,
            _search_flights_serpapi,
            departure,
            destination,
            depart_date,
            return_date,
            adults,
            children,
            deep_search,
            show_hidden
        )
        
        parsed_results = _parse_serpapi_results(api_response)
        return parsed_results
    
    except Exception as e:
        print(f"Error fetching flights: {e}")
        import traceback
        traceback.print_exc()
        raise
