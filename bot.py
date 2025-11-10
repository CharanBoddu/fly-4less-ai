import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flight_query_serpapi import extract_flight_details, validate_flight_data, search_flights_serpapi


load_dotenv()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Hi! Tell me where you want to fly, and I'll help you find the cheapest tickets!\n\n"
        "Example: \"Find me flights from Toronto to New York on March 10, returning March 15\""
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    structured = extract_flight_details(user_input)
    
    if not structured:
        await update.message.reply_text(
            "Sorry, I couldn't understand that. Please tell me:\n"
            "• Where you're flying from\n"
            "• Where you're flying to\n"
            "• When you want to depart\n"
            "• When you want to return (optional)"
        )
        return
    
    if 'flight_data' not in context.user_data:
        context.user_data['flight_data'] = {}
    
    for key, value in structured.items():
        if value and value != "null":
            context.user_data['flight_data'][key] = value
    
    is_valid, missing_fields, message = validate_flight_data(context.user_data['flight_data'])
    
    if not is_valid:
        await update.message.reply_text(message)
        return
    
    await update.message.reply_text(
        "🔎 Searching for flights with deep search enabled...\n"
        "This gives results identical to Google Flights in the browser."
    )
    
    try:
        flight_data = context.user_data['flight_data']
        results = await search_flights_serpapi(
            departure=flight_data['departure'],
            destination=flight_data['destination'],
            depart_date=flight_data['depart_date'],
            return_date=flight_data.get('return_date'),
            adults=flight_data.get('adults', 1),
            children=flight_data.get('children', 0),
            deep_search=True,
            show_hidden=True
        )
        
        response = format_flight_results(results, flight_data)
        await update.message.reply_text(response, parse_mode='Markdown')
        
        context.user_data.clear()
        
    except Exception as e:
        await update.message.reply_text(
            f"Sorry, I encountered an error while searching for flights: {str(e)}\n\n"
            "Please try again with a different search."
        )
        context.user_data.clear()


def format_flight_results(results, flight_data):
    """
    Formats SerpAPI flight results into a readable message.
    """
    if results.get('error'):
        return (
            f"❌ API Error: {results['error']}\n\n"
            "This might be a temporary issue. Please try again."
        )
    
    if not results or not results.get('flights') or len(results['flights']) == 0:
        return (
            "😔 No flights found for your search.\n\n"
            f"Route: {flight_data['departure']} → {flight_data['destination']}\n"
            f"Dates: {flight_data['depart_date']}"
            f"{' → ' + flight_data.get('return_date', '') if flight_data.get('return_date') else ' (one-way)'}\n\n"
            "Try different dates or airports."
        )
    
    available_flights = results['flights'][:5]
    
    trip_type = "Round-trip" if flight_data.get('return_date') else "One-way"
    message = f"✈️ *{trip_type} Flights Found*\n\n"
    message += f"📍 {flight_data['departure']} → {flight_data['destination']}\n"
    message += f"📅 {flight_data['depart_date']}"
    
    if flight_data.get('return_date'):
        message += f" → {flight_data['return_date']}"
    
    message += f"\n👥 {flight_data.get('adults', 1)} adult(s)"
    if flight_data.get('children', 0) > 0:
        message += f", {flight_data['children']} child(ren)"
    
    message += "\n\n📊 *Top 5 Cheapest Options:*\n\n"
    
    for idx, flight in enumerate(available_flights, 1):
        message += f"{idx}. *{flight['price_str']}* - {flight['airline']}\n"
        message += f"   ⏰ {flight['departure']} → {flight['arrival']}\n"
        message += f"   ⏱ Duration: {flight['duration']}\n"
        message += f"   🛫 Stops: {flight['stops']}\n\n"
    
    message += f"💡 Price level: {results.get('price_level', 'unknown')}\n"
    if results.get('lowest_price'):
        message += f"💰 Lowest price: ${results['lowest_price']}\n"
    message += "_Want to search again? Just send me another request!_"
    
    return message



async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Search cancelled. Send me a new flight request anytime!")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Flight Search Bot Commands*\n\n"
        "/start - Start a new conversation\n"
        "/cancel - Cancel current search\n"
        "/help - Show this help message\n\n"
        "*How to search for flights:*\n"
        "Just describe your trip in natural language!\n\n"
        "*Examples:*\n"
        "• _Find flights from Toronto to New York on March 10_\n"
        "• _I want to fly from LAX to JFK, leaving April 5 and returning April 12_\n"
        "• _Show me flights from London to Paris next Monday_"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
