# This is the beginning of fly-4less-ai
import os
from google import genai
from dotenv import load_dotenv

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

        Return output in JSON format with:
        - departure airport code (airport code)
        - destination airport code (airport code)
        - departure date (departure date with the current year)
        - return date (return date with the current year)
        """])

    return response.text 

user_input = "Find me the cheapest flight from Toronto to New York from March 10-15, 2025"
structured_data = extract_flight_details(user_input)
print(structured_data)