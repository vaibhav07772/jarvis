"""JARVIS Tools — functions Jarvis can call"""
import datetime
import psutil
import requests
from typing import Dict, Any


def get_time() -> str:
    """Get current time"""
    now = datetime.datetime.now()
    return now.strftime("It's %I:%M %p, sir.")


def get_date() -> str:
    """Get current date"""
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %B %d, %Y.")


def get_system_info() -> str:
    """Get system stats"""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    battery_str = f"Battery at {battery.percent:.0f} percent." if battery else ""
    return f"CPU usage is {cpu:.0f} percent, RAM is at {ram:.0f} percent. {battery_str}"


def search_wikipedia(query: str) -> str:
    """Search Wikipedia using search API (better results for common topics)"""
    try:
        headers = {"User-Agent": "JarvisAssistant/1.0 (educational project)"}

        # Step 1: Search for topic
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1,
        }

        search_response = requests.get(
            search_url,
            params=search_params,
            headers=headers,
            timeout=5,
        )

        if search_response.status_code != 200:
            return f"Search failed for {query}."

        search_data = search_response.json()
        search_results = search_data.get("query", {}).get("search", [])

        if not search_results:
            return f"I couldn't find information about {query}."

        page_title = search_results[0]["title"]

        # Step 2: Get page summary
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title.replace(' ', '_')}"
        summary_response = requests.get(summary_url, headers=headers, timeout=5)

        if summary_response.status_code == 200:
            data = summary_response.json()
            extract = data.get("extract", "")
            if len(extract) > 300:
                extract = extract[:300] + "..."
            return extract

        return f"I found {page_title} but couldn't retrieve details."

    except Exception as e:
        return f"Search failed: {str(e)[:50]}"


def get_weather(city: str = "Mumbai") -> str:
    """Get weather (using free wttr.in — no API key needed)"""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            current = data["current_condition"][0]
            temp = current["temp_C"]
            desc = current["weatherDesc"][0]["value"]
            humidity = current["humidity"]
            return f"In {city}, it's {temp} degrees Celsius with {desc.lower()}. Humidity is {humidity} percent."
        return f"Couldn't fetch weather for {city}."
    except Exception as e:
        return f"Weather lookup failed."


def calculate(expression: str) -> str:
    """Safe calculator"""
    try:
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return "Sorry, I can only do basic math."

        result = eval(expression)
        return f"The answer is {result}."
    except Exception as e:
        return "Sorry, I couldn't calculate that."


# ─────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────
TOOLS = {
    "get_time": get_time,
    "get_date": get_date,
    "get_system_info": get_system_info,
    "search_wikipedia": search_wikipedia,
    "get_weather": get_weather,
    "calculate": calculate,
}


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current time",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_date",
            "description": "Get today's date",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get CPU, RAM, battery info of the computer",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": "Search Wikipedia for information about a topic",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic to search"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, default Mumbai"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Calculate a math expression like '2 + 2' or '15 * 3'",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression"}
                },
                "required": ["expression"],
            },
        },
    },
]


def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """Execute a tool by name"""
    if name not in TOOLS:
        return f"Unknown tool: {name}"

    try:
        return TOOLS[name](**args)
    except Exception as e:
        return f"Tool error: {str(e)[:100]}"


if __name__ == "__main__":
    print("=== TOOL TESTS ===")
    print(f"Time:    {get_time()}")
    print(f"Date:    {get_date()}")
    print(f"System:  {get_system_info()}")
    print(f"Weather: {get_weather('Mumbai')}")
    print(f"Calc:    {calculate('15 * 3 + 7')}")
    print(f"\nWiki (Mumbai):")
    print(f"  {search_wikipedia('Mumbai')}")
    print(f"\nWiki (Iron Man):")
    print(f"  {search_wikipedia('Iron Man')}")