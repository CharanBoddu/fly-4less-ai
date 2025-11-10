import os
import google.generativeai as genai
from dotenv import load_dotenv
from fast_flights import FlightData, Passengers, get_flights
import json
import re
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("API Key not found. Make sure to set GEMINI_API_KEY in .env")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')


def _get_flights_in_thread(flight_data, trip_type, seat, passengers):
    """
    Helper function to run get_flights in a separate thread with its own event loop.
    """
    try:
        results = get_flights(
            flight_data=flight_data,
            trip=trip_type,
            seat=seat,
            passengers=passengers,
            fetch_mode="local"
        )
        return results
    except Exception as e:
        print(f"Error in thread: {e}")
        raise


def _deep_search_flights(flight_data, trip_type, seat, passengers, num_scrolls=3):
    """
    Performs a deep search by making multiple requests and aggregating results.
    This mimics SerpAPI's deep_search feature.
    
    Args:
        num_scrolls: Number of times to "scroll" through results (default 3)
    """
    all_flights = []
    seen_flights = set()  # Track flights we've already seen
    
    try:
        for scroll in range(num_scrolls):
            print(f"Deep search iteration {scroll + 1}/{num_scrolls}...")
            
            # Make request
            results = get_flights(
                flight_data=flight_data,
                trip=trip_type,
                seat=seat,
                passengers=passengers,
                fetch_mode="local"
            )
            
            # Collect unique flights
            if results and hasattr(results, 'flights'):
                for flight in results.flights:
                    # Create unique identifier for flight
                    flight_id = f"{flight.name}_{flight.departure}_{flight.arrival}_{flight.price}"
                    
                    if flight_id not in seen_flights:
                        seen_flights.add(flight_id)
                        all_flights.append(flight)
                
                print(f"Found {len(all_flights)} unique flights so far...")
            
            # Small delay between scrolls to let Google Flights update
            if scroll < num_scrolls - 1:
                import time
                time.sleep(15)
        
        # Return modified result object with all flights
        if results:
            # Replace flights list with our aggregated list
            results.flights = all_flights
        
        return results
    
    except Exception as e:
        print(f"Error in deep search: {e}")
        raise


# Keep all your existing functions from before
def extract_flight_details(user_input):
    """
    Uses Gemini API to extract structured flight query details from natural language input.
    Returns a dictionary with flight details or None if parsing fails.
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
        
        print(f"DEBUG - Raw response: '{text}'")
        
        # Remove markdown code blocks if present
        text = text.replace(chr(96), "").strip()
        if text.startswith("json"):
            text = text[4:].strip()
        
        print(f"DEBUG - After cleanup: '{text}'")
        
        flight_data = json.loads(text)
        
        print(f"DEBUG - Parsed successfully: {flight_data}")
        
        return flight_data
    
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Text that failed to parse: '{text}'")
        return None
    except Exception as e:
        print(f"Error extracting flight details: {e}")
        return None


def validate_flight_data(flight_data):
    """
    Validates flight data and returns missing fields.
    Returns (is_valid: bool, missing_fields: list, message: str)
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
    
    # Validate date format
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
    Normalizes airport codes to uppercase 3-letter IATA format.
    """
    if not code or code == "null":
        return None
    
    code = code.upper().strip()
    
    # Validate it's a 3-letter code
    if len(code) == 3 and code.isalpha():
        return code
    
    return None


async def search_flights_fastflights(departure, destination, depart_date, return_date=None, adults=1, children=0, deep_search=True):
    """
    Searches for flights using the fast_flights library with LOCAL mode.
    Supports deep search for more comprehensive results.
    
    Args:
        deep_search: If True, performs multiple searches to get all available flights
    """
    # Normalize airport codes
    departure = normalize_airport_code(departure)
    destination = normalize_airport_code(destination)
    
    if not departure or not destination:
        raise ValueError("Invalid airport codes provided")
    
    flight_data = [FlightData(date=depart_date, from_airport=departure, to_airport=destination)]
    trip_type = "one-way"
    
    if return_date and return_date != "null":
        flight_data.append(FlightData(date=return_date, from_airport=destination, to_airport=departure))
        trip_type = "round-trip"
    
    passengers = Passengers(
        adults=int(adults) if adults else 1,
        children=int(children) if children else 0,
        infants_in_seat=0,
        infants_on_lap=0
    )
    
    try:
        loop = asyncio.get_event_loop()
        
        if deep_search:
            print("🔎 Performing DEEP SEARCH (this takes longer but finds more flights)...")
            results = await loop.run_in_executor(
                None,
                _deep_search_flights,
                flight_data,
                trip_type,
                "economy",
                passengers,
                5  # num_scrolls
            )
        else:
            print("🔍 Performing standard search...")
            results = await loop.run_in_executor(
                None,
                _get_flights_in_thread,
                flight_data,
                trip_type,
                "economy",
                passengers
            )
        
        return results
    
    except Exception as e:
        print(f"Error fetching flights: {e}")
        raise
