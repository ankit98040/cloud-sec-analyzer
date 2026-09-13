import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from openai import AsyncOpenAI
# pyrefly: ignore [missing-import]
from agents import (
    Agent,
    Runner,
    function_tool,
    OpenAIChatCompletionsModel,
    set_default_openai_client,
    set_tracing_disabled,
)
# pyrefly: ignore [missing-import]
import gradio as gr
import sqlite3
import traceback


load_dotenv(override=True)

api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
model_name = os.getenv("MODEL_NAME", "nvidia/nemotron-3-nano-30b-a3b")

client = AsyncOpenAI(
    base_url=base_url,
    api_key=api_key,
)
set_default_openai_client(client, use_for_tracing=False)
set_tracing_disabled(True)

agent_model = OpenAIChatCompletionsModel(
    model=model_name,
    openai_client=client,
)

instructions = "You are a helpful assistant for an Airline called FlightAI. "
instructions += "Use your tools to get ticket prices and calculate discounts. Trips to London have a 10% discount on the price. "
instructions += "Always be accurate. If you don't know the answer, say so."

DB = "prices.db"
initial_ticket_prices = {"london": 799, "paris": 899, "tokyo": 1400, "sydney": 2999}


with sqlite3.connect(DB) as conn:
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS prices (city TEXT PRIMARY KEY, price REAL)")
    for city, price in initial_ticket_prices.items():
        cursor.execute(f"INSERT OR IGNORE INTO prices (city, price) VALUES ('{city}', {price})")
    conn.commit()


@function_tool
def get_ticket_price(city: str) -> str:
    """Get the price of a ticket to a given city.

    Args:
        city: The city to get the price of a ticket to
    """
    print(f"TOOL CALLED: Getting price for {city}", flush=True)
    query = f"SELECT price FROM prices WHERE city = '{city.lower()}'"
    try:
        with sqlite3.connect(DB) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            return f"${result[0]}" if result else "Not found"
    except Exception as e:
        return f"Error: {traceback.format_exc()}"


@function_tool
def calculate(expr: str) -> str:
    """Evaluate a numeric expression - use this for example to make calculations about prices

    Args:
        expr: The expression to evaluate
    """
    print(f"TOOL CALLED: Calculating {expr}", flush=True)
    return str(eval(expr))


async def chat(message, history):
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages += [{"role": "user", "content": message}]
    agent = Agent(
        name="FlightAI", instructions=instructions, model=agent_model, tools=[get_ticket_price, calculate]
    )
    result = await Runner.run(agent, messages)
    return result.final_output


gr.ChatInterface(chat, type="messages").launch(inbrowser=True)
