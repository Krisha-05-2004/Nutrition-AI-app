# prompts.py
import json

def build_mealplan_prompt(user: dict) -> str:
    return f"""
You are a professional nutritionist. Create a personalized meal plan.

IMPORTANT:
- Respond ONLY with a SINGLE valid JSON object.
- Do NOT wrap values in backticks or markdown.
- Do NOT include JSON inside strings.
- "summary_markdown" must contain ONLY plain markdown text, NOT JSON.

Valid JSON schema:
{{
  "daily_calories_estimate": 2000,
  "meals": {{
    "breakfast": [
      {{
        "name": "Oat porridge",
        "calories": 350,
        "recipe": {{
          "ingredients": ["oats - 50g", "milk - 200ml"],
          "steps": ["Mix oats and milk", "Cook 5 minutes"]
        }},
        "alternatives": ["Fruit yogurt bowl"]
      }}
    ],
    "lunch": [],
    "dinner": [],
    "snacks": []
  }},
  "grocery_list": ["oats", "milk"],
  "summary_markdown": "**Daily calories:** 2000\\n- Breakfast: Oat porridge (350 kcal)"
}}

User info:
{user}
"""
