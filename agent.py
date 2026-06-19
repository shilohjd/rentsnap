from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from tools.listing_search import listing_search
from tools.comp_analyzer import comp_analyzer
from tools.db_logger import db_logger
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatAnthropic(model="claude-haiku-4-5-20251001")

tools = [listing_search, comp_analyzer, db_logger]

agent = create_react_agent(llm, tools)

def analyze_unit(unit: dict) -> str:
    prompt = (
        f"Analyze the rental market for this unit:\n"
        f"Unit ID: {unit['id']}\n"
        f"Address: {unit['address']}\n"
        f"Bedrooms: {unit['bedrooms']}\n"
        f"Bathrooms: {unit['bathrooms']}\n"
        f"Current rent: ${unit['current_rent']}/mo\n"
        f"Notes: {unit['notes']}\n\n"
        f"Steps:\n"
        f"1. Search for comparable {unit['bedrooms']} bedroom rentals near {unit['address']}\n"
        f"2. Use the comp analyzer to determine market position\n"
        f"3. Log the results to the database\n"
        f"4. Return a plain English summary with rent recommendation"
    )

    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    return result["messages"][-1].content