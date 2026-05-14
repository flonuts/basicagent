import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import anthropic
import requests
from geopy.geocoders import Nominatim

load_dotenv()

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

conversation_history = []

tools = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculator",
        "description": "Perform basic math calculations",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression to evaluate"}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for current information on any topic",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    }
]

def get_weather(city):
    try:
        geolocator = Nominatim(user_agent="basicagent")
        location = geolocator.geocode(city)
        if not location:
            return f"Could not find location: {city}"
        lat = location.latitude
        lon = location.longitude
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "current": "temperature_2m,weathercode,windspeed_10m", "temperature_unit": "fahrenheit", "windspeed_unit": "mph"}
        response = requests.get(url, params=params)
        data = response.json()
        current = data["current"]
        temp = current["temperature_2m"]
        wind = current["windspeed_10m"]
        code = current["weathercode"]
        weather_descriptions = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "icy fog", 51: "light drizzle", 53: "moderate drizzle", 55: "heavy drizzle", 61: "light rain", 63: "moderate rain", 65: "heavy rain", 71: "light snow", 73: "moderate snow", 75: "heavy snow", 80: "light showers", 81: "moderate showers", 82: "heavy showers", 95: "thunderstorm"}
        description = weather_descriptions.get(code, f"weather code {code}")
        return f"{city}: {temp}F, {description}, wind {wind} mph"
    except Exception as e:
        return f"Weather error: {str(e)}"

def calculator(expression):
    try:
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {str(e)}"

def web_search(query):
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        response = requests.get(url, params=params)
        data = response.json()
        results = []
        if data.get("AbstractText"):
            results.append(data["AbstractText"])
        for topic in data.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(topic["Text"])
        if results:
            return "\n".join(results)
        return "No results found. Try rephrasing your search."
    except Exception as e:
        return f"Search error: {str(e)}"

def handle_tool(name, inputs):
    if name == "get_weather":
        return get_weather(inputs["city"])
    elif name == "calculator":
        return calculator(inputs["expression"])
    elif name == "web_search":
        return web_search(inputs["query"])
    return "Tool not found"

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    global conversation_history
    data = request.json
    user_message = data.get("message", "")

    if data.get("reset"):
        conversation_history = []
        return jsonify({"response": "Conversation cleared."})

    conversation_history.append({"role": "user", "content": user_message})

    messages = conversation_history.copy()

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="You are a helpful assistant with access to weather, calculator, and web search tools. Be concise and friendly.",
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            answer = response.content[0].text
            conversation_history.append({"role": "assistant", "content": answer})
            return jsonify({"response": answer})

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = handle_tool(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})

if __name__ == "__main__":
    app.run(debug=True, port=5000)