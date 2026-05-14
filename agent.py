import os
from dotenv import load_dotenv
import anthropic
import requests
from geopy.geocoders import Nominatim

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
                "expression": {"type": "string", "description": "Math expression to evaluate, e.g. '2 + 2'"}
            },
            "required": ["expression"]
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
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weathercode,windspeed_10m",
            "temperature_unit": "fahrenheit",
            "windspeed_unit": "mph"
        }
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

def handle_tool(name, inputs):
    if name == "get_weather":
        return get_weather(inputs["city"])
    elif name == "calculator":
        return calculator(inputs["expression"])
    return "Tool not found"

def run_agent(user_message):
    print(f"\nYou: {user_message}")
    messages = [{"role": "user", "content": user_message}]
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )
        if response.stop_reason == "end_turn":
            answer = response.content[0].text
            print(f"Agent: {answer}")
            return answer
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [using tool: {block.name} with {block.input}]")
                    result = handle_tool(block.name, block.input)
                    print(f"  [tool result: {result}]")
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})

if __name__ == "__main__":
    run_agent("What's the weather like in Boston?")
    run_agent("What is 347 multiplied by 19?")
    run_agent("What's the weather in Miami and what is 100 divided by 4?")