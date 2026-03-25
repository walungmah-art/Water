# config/credit_costs.py
"""
Credit cost for each command
"""

CREDIT_COSTS = {
    "/co": 1,
    "/bco": 1,
    "/st": 1,
    "/mst": 1,  # Per card - handled separately
    "/txt": 1,  # Per card - handled separately
    "/addproxy": 0,  # Free (proxy management)
    "/proxy": 0,
    "/removeproxy": 0,
    "/bininfo": 0,
}

# Commands that cost per card in bulk operations
PER_CARD_COST = 1  # Each card in multi-card commands costs 1 credit

def get_command_cost(command: str, bypass_strength: str = "none", card_count: int = 1) -> int:
    """Calculate credit cost for a command based on bypass strength and card count"""
    base_cost = CREDIT_COSTS.get(command, 1)
    
    bypass_multipliers = {
        "none": 1,
        "light": 1,
        "medium": 2,
        "maximum": 3,
        "extreme": 4
    }
    multiplier = bypass_multipliers.get(bypass_strength, 1)
    
    if command in ["/mst", "/txt"]:
        return base_cost * multiplier * max(1, card_count)
    
    return base_cost * multiplier

# Commands that are free (no credit deduction)
FREE_COMMANDS = [
    "/start",
    "/help",
    "/bininfo",
    "/proxy",
    "/addproxy",
    "/removeproxy",
    "/gen",
]

# Commands restricted to admins/owner only
ADMIN_COMMANDS = [
    "/addcredits",
    "/removecredits",
    "/setcredits",
    "/broadcast",
    "/stats",
    "/adduser",
    "/removeuser",
    "/ban",
    "/unban",
]