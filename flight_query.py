# This is the beginning of fly-4less-ai
import os
from google import genai
from dotenv import load_dotenv
from fast_flights import FlightData, Passengers, get_flights

load_dotenv()

api_key = os.environ.get('GEMINI_API_KEY')

if not api_key:
    raise ValueError("API Key not found. Make sure to set GEMINI_API_KEY in env/.env")

client = genai.Client(api_key=api_key)

def extract_flight_details(user_input):
    """
    Uses Gemini API to extract structured flight query details from natural language input.
    """
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[f"""
        Extract structured flight details from the following query:

        Query: "{user_input}"

        Return only the output JSON. Do not include explanations or any extra text.
        Return output in JSON format with:
        - departure airport code (airport code)
        - destination airport code (airport code)
        - departure date (departure date with the current year)
        - return date (return date with the current year)
        """])

    return response.text 


def search_flights_fastflights(departure, destination, depart_date, return_date=None, adults=1, children=0):
    flight_data = [FlightData(date=depart_date, from_airport=departure, to_airport=destination)]
    trip_type = "one-way"
    if return_date:
        # We add return flight data if return_date is provided.
        flight_data.append(FlightData(date=return_date, from_airport=destination, to_airport=departure))
        trip_type = "round-trip"
    passengers = Passengers(adults=adults, children=children, infants_in_seat=0, infants_in_lap=0)
    results = get_flights(
        flight_data=flight_data,
        trip=trip_type,
        seat="economy",
        passengers=passengers,
        fetch_mode="fallback"
        )
    return results
    

user_input = "Find me the cheapest flight from Toronto to New York from March 10-15, 2025"
structured_data = extract_flight_details(user_input)
print(structured_data)