from langchain_core.tools import tool
import re

@tool
def comp_analyzer(search_results: str, bedrooms: int, current_rent: float) -> str:
    """Analyze rental search results to find comparable units and determine market position."""
    
    prices = []
    lines = search_results.split("\n")
    
    for line in lines:
        matches = re.findall(r'\$[\d,]+(?:/mo|/month| per month)?', line, re.IGNORECASE)
        for match in matches:
            digits = re.sub(r'[^\d]', '', match)
            if digits:
                price = int(digits)
                if 400 < price < 3000:
                    prices.append(price)

    if not prices:
        return "No comparable rental prices found in search results."

    prices = sorted(set(prices))
    median = sorted(prices)[len(prices) // 2]
    low = min(prices)
    high = max(prices)
    diff = current_rent - median
    count = len(prices)

    if diff < -75:
        position = "BELOW market"
        action = f"Room to increase rent by ~${abs(diff)}/mo at next renewal"
    elif diff > 75:
        position = "ABOVE market"
        action = "Monitor vacancy risk — priced above most comps"
    else:
        position = "AT market"
        action = "Hold current rate"

    return (
        f"Comps analyzed: {count} prices found\n"
        f"Range: ${low}/mo — ${high}/mo\n"
        f"Median comp rent: ${median}/mo\n"
        f"Your rent: ${current_rent}/mo\n"
        f"Position: {position} (${abs(diff)} {'below' if diff < 0 else 'above'} median)\n"
        f"Recommendation: {action}"
    )