# utils.py (Groq ONLY – clean version)
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


if not GROQ_API_KEY:
    raise RuntimeError("ERROR: GROQ_API_KEY is missing. Add it to your .env file.")

client = Groq(api_key=GROQ_API_KEY)

def call_llm(prompt: str):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.2
    )
    return resp.choices[0].message.content

def generate_meal_plan(user):
    from prompts import build_mealplan_prompt
    prompt = build_mealplan_prompt(user)

    raw_text = call_llm(prompt)

    # Try parsing JSON
    try:
        start = raw_text.index("{")
        end = raw_text.rindex("}") + 1
        json_text = raw_text[start:end]
        return json.loads(json_text)
    except Exception:
        return {"raw_text": raw_text, "summary_markdown": raw_text}
