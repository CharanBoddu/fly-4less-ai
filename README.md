# ✈️ Fly-4-Less AI Telegram Bot

A smart Telegram bot that finds the cheapest flights using natural language. Just tell it where and when you want to fly, and it'll handle the rest!



---

## ✨ Features

* **Natural Language Processing:** Powered by Google's Gemini API to understand queries like *"Find me a flight from Toronto to NYC from Oct 10 to 20"* without needing rigid commands.
* **One-Way & Round-Trip:** Automatically detects whether you're looking for a one-way or round-trip ticket.
* **Real-time Flight Search:** Uses the `fast-flights` library to fetch up-to-date flight information.
* **Easy to Use:** A simple and intuitive chat interface through Telegram.

---

## ⚙️ How It Works

The bot follows a simple three-step process:

1.  **Parse:** A user sends a message to the Telegram bot (e.g., "flight from HYD to BER on Oct 2").
2.  **Understand:** The `python-telegram-bot` library forwards this message to our script. We then send the text to the **Gemini API**, which extracts structured JSON data (`departure_airport_code`, `destination_airport_code`, dates, etc.).
3.  **Search:** This structured data is passed to the `fast-flights` library, which performs the actual flight search.
4.  **Reply:** The flight results are formatted and sent back to the user in the Telegram chat.

### Technology Stack

* **Telegram Bot Framework:** `python-telegram-bot`
* **Natural Language Understanding:** Google Gemini (`google-generativeai`)
* **Flight Data:** `fast-flights` library
* **Environment Management:** `python-dotenv`
