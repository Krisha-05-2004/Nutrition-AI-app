# agents.py (fixed)

from langchain.agents import initialize_agent, Tool, AgentType
from langchain.chat_models import ChatOpenAI

# Example tool functions
def calorie_estimator_tool(user_json: str) -> str:
    # implement your calorie estimation logic
    return "Estimated daily calories: 2200"

def recipe_generator_tool(meal_request: str) -> str:
    # implement or call an LLM
    return '{"name": "Oats porridge", "calories": 300}'

tools = [
    Tool(
        name="CalorieEstimator",
        func=calorie_estimator_tool,
        description="Estimates daily calories"
    ),
    Tool(
        name="RecipeGenerator",
        func=recipe_generator_tool,
        description="Generate recipes for a dish"
    ),
]

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)
