# app.py
import io
import json
import re
import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, List

import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from groq import Groq

def get_secret(key, default=None):
    # 1) prefer environment variables (useful locally)
    v = os.getenv(key)
    if v:
        return v
    # 2) then try Streamlit secrets (safe: catch errors if none exist)
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

GROQ_KEY = get_secret("GROQ_API_KEY")
GROQ_MODEL = get_secret("GROQ_MODEL", "llama-3.1-8b-instant")

if not GROQ_KEY:
    st.error("GROQ_API_KEY not found. Add it to Streamlit Secrets (cloud) or set it locally in .env/.streamlit/secrets.toml")
    st.stop()

groq_client = Groq(api_key=GROQ_KEY)

# ---------- Page config ----------
st.set_page_config(page_title="AI Nutrition Assistant", layout="wide", initial_sidebar_state="expanded")

REMOTE_BG = "https://as2.ftcdn.net/v2/jpg/02/49/58/87/1000_F_249588708_tfhSIvYkdS2RLrMeNUSqMJhkOJ5En7EW.jpg"
LOCAL_BG = Path("assets/food_blur.jpg")
bg_url = LOCAL_BG.as_posix() if LOCAL_BG.exists() else REMOTE_BG

PAGE_CSS = f"""
<style>
.stApp {{
    background-image: url('{bg_url}');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}
.stApp::before {{
    content: "";
    position: fixed;
    inset: 0;
    background: rgba(255,255,255,0.74);
    backdrop-filter: blur(3px);
    z-index: 0;
}}
.block-container, .stApp > .main {{
    position: relative;
    z-index: 1;
}}
.main-card {{
    backdrop-filter: blur(6px) saturate(120%);
    background: rgba(255,255,255,0.82);
    border-radius: 14px;
    padding: 18px;
    box-shadow: 0 8px 30px rgba(22,23,24,0.06);
    border: 1px solid rgba(200,200,210,0.35);
}}
.recipe-card {{
    background: rgba(255,255,255,0.95);
    border-radius: 10px;
    padding: 12px;
    margin-bottom: 12px;
}}
.assistant-box {{
    background: rgba(220,235,255,0.95);
    padding: 14px;
    border-radius: 8px;
    border: 1px solid rgba(170,200,230,0.9);
    color: #0e3b66;
    
}}
</style>
"""
st.markdown(PAGE_CSS, unsafe_allow_html=True)

FORCE_MOBILE_CSS = r"""
<style>
/* make sure base uses your bg */
html, body, .stApp {
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
  color: #111 !important;             /* force dark text */
}

/* desktop overlay (keeps look) */
.stApp::before {
  content: "" !important;
  position: fixed !important;
  inset: 0 !important;
  background: rgba(255,255,255,0.72) !important;
  backdrop-filter: blur(4px) !important;
  -webkit-backdrop-filter: blur(4px) !important;
  z-index: 0 !important;
}

/* content above overlay */
.block-container, .stApp > .main, .css-1d391kg { /* added common streamlit containers */
  position: relative !important;
  z-index: 1 !important;
  color: #111 !important;            /* also force text color for children */
}

/* hero / cards */
.main-card, .recipe-card, .assistant-box {
  background: rgba(255,255,255,0.90) !important;
  color: #0b2540 !important;
}

/* Force header color & weight so it's readable */
.stApp h1, .stApp h2, .stApp h3, .stMarkdown h1, .stMarkdown h2 {
  color: #0b2540 !important;
  text-shadow: none !important;
}

/* Prevent mobile browsers from applying 'dark mode' colors */
@media (prefers-color-scheme: dark) {
  html, body, .stApp, .block-container {
    background-color: transparent !important;
    color: #111 !important;
  }
  .stApp::before { background: rgba(255,255,255,0.78) !important; }
}

/* ----- PHONE-SPECIFIC OVERRIDES ----- */
@media (max-width: 900px) {
  /* switch to a lighter background image on phones (your lighter image) */
  .stApp {
    background-image: url("https://as2.ftcdn.net/v2/jpg/02/49/58/87/1000_F_249588708_tfhSIvYkdS2RLrMeNUSqMJhkOJ5En7EW.jpg") !important;
    background-position: center top !important;
    background-size: cover !important;
    background-attachment: scroll !important; /* avoid fixed on mobile */
  }

  /* stronger overlay for phones so text pops */
  .stApp::before {
    background: rgba(255,255,255,0.86) !important; /* increase opacity for readability */
    backdrop-filter: blur(3px) !important;
    -webkit-backdrop-filter: blur(3px) !important;
  }

  /* shrink big hero & make text bold & dark */
/* shrink or adjust hero title ONLY on phones */
@media (max-width: 900px) {
    .stApp h1 {
        font-size:40px !important;       /* bigger title for phone */
        font-weight: 800 !important;
        line-height: 1.2 !important;
        color: #0b2540 !important;
        margin: 10px 0 14px 0 !important;
        text-align: center !important;
    }

    .stApp h2 { font-size: 22px !important; }
    .stApp h3 { font-size: 18px !important; }
}

  .stApp h2, .stApp h3 { color: #0b2540 !important; }

  /* reduce spacing and padding so things fit on small screens */
  .main-card { padding: 10px !important; border-radius: 10px !important; }
  .recipe-card { padding: 8px !important; }
  .assistant-box { padding: 10px !important; font-size: 14px !important; }

  /* make buttons expand full width */
  .stButton>button, .stDownloadButton>button, .stTextInput>input {
    width: 100% !important;
  }

  /* force sidebar-to-top area readable */
  .css-1d391kg, .css-1lcbmhc, .css-1v0mbdj { /* common streamlit wrapper classes (may vary) */
    background: rgba(255,255,255,0.92) !important;
    color: #111 !important;
  }

  /* hide small decorative images in header if they collide */
  .stMarkdown img { max-height: 36px !important; max-width: 36px !important; }

  /* ensure the plan notice box (blue) remains readable */
  .assistant-box, .css-1o4c2k3 { background: rgba(220,235,255,0.98) !important; color: #072241 !important; }

  /* If any Streamlit internal class forces white text, override */
  .stText, .stText > div, .stMarkdown, .stMarkdown > div {
    color: #111 !important;
  }
}

/* extremely narrow phones */
@media (max-width: 420px) {
  .stApp h1 { font-size: 20px !important; }
  .assistant-box { font-size: 13px !important; padding: 8px !important; }
}
</style>
"""

# inject
st.markdown(FORCE_MOBILE_CSS, unsafe_allow_html=True)


# ---------- small starter dataset (seed recipes) ----------
SAMPLE_RECIPES = {
    "moong_dal_chilla": {
        "title": "Moong Dal Chilla",
        "cal": 180,
        "ingredients": ["moong dal batter - 100g", "onion - 30g", "coriander - small bunch"],
        "steps": ["Prepare batter", "Cook thin pancakes on tawa until golden"],
        "cuisine": "indian",
        "tags": ["breakfast", "vegan", "indian", "south"]
    },
    "idli_steamed": {
        "title": "Idli (steamed)",
        "cal": 150,
        "ingredients": ["idli batter - 2 small idlis", "coconut chutney - small serving"],
        "steps": ["Steam idlis for 10-12 min", "Serve with chutney"],
        "cuisine": "indian",
        "tags": ["breakfast", "vegetarian", "indian", "south"]
    },
    "khichdi_light": {
        "title": "Khichdi (Light)",
        "cal": 300,
        "ingredients": ["moong dal - 50g", "rice - 40g", "turmeric", "salt"],
        "steps": ["Soak dal (optional)", "Cook dal and rice together until porridge-like", "Season lightly"],
        "cuisine": "indian",
        "tags": ["lunch", "dinner", "vegetarian", "indian"]
    },
    "sprouts_salad": {
        "title": "Sprouts Salad",
        "cal": 100,
        "ingredients": ["sprouts - 50g", "lemon - 1/2", "salt to taste"],
        "steps": ["Mix sprouts with lemon and seasoning", "Serve fresh"],
        "cuisine": "global",
        "tags": ["snacks", "vegan", "quick"]
    },
    "roasted_almonds": {
        "title": "Roasted Almonds",
        "cal": 170,
        "ingredients": ["almonds - 25g"],
        "steps": ["Roast almonds lightly and cool"],
        "cuisine": "global",
        "tags": ["snacks", "vegetarian", "quick"]
    }
}

# ---------- cuisine token map ----------
CUISINE_MAP = {
    "No preference": "",
    "Indian (South)": "indian_south",
    "Indian (North)": "indian_north",
    "Indian (All regions)": "indian",
    "Chinese": "chinese",
    "Mexican": "mexican",
    "Global": "global"
}

# ---------- deterministic helper ----------
def _stable_choices(seed_str: str, options: List[str], k: int = 1) -> List[str]:
    if not options:
        return []
    h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    picks = []
    i = 0
    while len(picks) < k:
        chunk = h[2 * i:2 * i + 8]
        if not chunk:
            h = hashlib.sha256(h.encode()).hexdigest()
            chunk = h[0:8]
            i = 0
        idx = int(chunk, 16) % len(options)
        if idx not in picks:
            picks.append(idx)
        i += 1
    return [options[i] for i in picks]

# ---------- title builder ----------
def _make_title_from_base(cuisine_token: str, base: str, protein: str, vegs: List[str], meal_type: str) -> str:
    token = (cuisine_token or "global").lower()
    if token.startswith("indian"):
        token = "indian"

    base_l = base.lower()
    prot = protein.lower()
    veg_l = [v.lower() for v in vegs]

    if token == "indian":
        if any(d in prot for d in ["toor", "tuvar", "arhar"]):
            if "rice" in base_l:
                if "tomato" in veg_l:
                    return "Tomato Toor Dal + Rice"
                return "Toor Dal + Rice"
            if "roti" in base_l or "phulka" in base_l:
                return "Toor Dal Fry + Roti"
            return "Toor Dal Khichdi"

        if any(d in prot for d in ["moong", "mung"]):
            if "rice" in base_l:
                if "tomato" in veg_l:
                    return "Tomato Moong Dal + Rice"
                return "Moong Dal + Rice"
            if "roti" in base_l or "phulka" in base_l:
                return "Moong Dal Fry + Roti"
            return "Moong Dal Khichdi"

        if "chana" in prot:
            if "rice" in base_l:
                return "Chana Dal + Rice"
            if "roti" in base_l or "phulka" in base_l:
                return "Chana Dal Fry + Roti"
            return "Chana Dal Khichdi"

        if "paneer" in prot:
            if "rice" in base_l:
                return "Paneer Masala Bowl"
            return "Paneer Bhurji + Roti"

        if "roti" in base_l or "phulka" in base_l:
            if "spinach" in veg_l:
                return "Palak Sabzi + Roti"
            if "peas" in veg_l:
                return "Matar Sabzi + Roti"
            return "Mixed Veg Sabzi + Roti"

        if "rice" in base_l:
            return "Veg Rice Bowl"

        return "Indian Veg Meal"

    if token == "chinese":
        if "noodles" in base_l:
            if "tofu" in prot:
                return "Stir-Fried Tofu Noodles"
            return "Vegetable Chow Mein"
        if "rice" in base_l:
            if "edamame" in prot:
                return "Edamame Fried Rice"
            return "Veg Fried Rice"
        if "bok" in " ".join(veg_l):
            return "Stir-Fried Veg with Tofu"
        return "Chinese Veg Stir-Fry"

    if token == "mexican":
        if "tortilla" in base_l or "taco" in base_l:
            if "beans" in prot:
                return "Bean Tacos"
            if "tofu" in prot:
                return "Tofu Soft Tacos"
            return "Veg Tacos"
        if "rice" in base_l:
            if "beans" in prot:
                return "Mexican Bean Rice Bowl"
            return "Mexican Veg Rice Bowl"
        if "quinoa" in base_l:
            return "Quinoa Burrito Bowl"
        return "Mexican Veg Plate"

    if token == "global":
        if "quinoa" in base_l:
            return "Quinoa & Veg Bowl"
        if "grains" in base_l:
            return "Mixed Grain Bowl"
        if "noodles" in base_l:
            return "Veg Noodle Bowl"
        if "rice" in base_l:
            return "Veg Rice Bowl"
        return "Fresh Veg Meal"

    return "Healthy Meal"

# ---------- generation pools ----------
GEN_POOLS = {
    "mexican": {
        "bases": ["brown rice", "tortilla (small)", "quinoa"],
        "proteins": ["black beans", "pinto beans", "tofu (firm)"],
        "vegs": ["corn", "bell pepper", "onion", "tomato", "lettuce"],
        "extras": ["salsa", "avocado", "lime", "cilantro"],
        "spices": ["cumin powder", "paprika", "chili powder"]
    },
    "chinese": {
        "bases": ["steamed rice", "noodles"],
        "proteins": ["tofu (firm)", "edamame"],
        "vegs": ["capsicum", "spring onion", "peas", "bok choy"],
        "extras": ["light soy sauce", "sesame oil", "garlic", "ginger"],
        "spices": ["white pepper"]
    },
    "indian": {
        "bases": ["rice", "phulka/roti"],
        "proteins": ["moong dal", "toor dal", "chana", "paneer"],
        "vegs": ["onion", "tomato", "spinach", "peas"],
        "extras": ["turmeric", "cumin seeds", "coriander"],
        "spices": ["red chili powder"]
    },
    "global": {
        "bases": ["mixed grains", "couscous"],
        "proteins": ["lentils", "beans", "tofu"],
        "vegs": ["mixed veg", "salad greens"],
        "extras": ["lemon", "olive oil"],
        "spices": ["salt", "black pepper"]
    }
}

# ---------- synthetic generator ----------
def generate_synthetic_recipe(cuisine_token: str, meal_type: str, disliked: List[str], seed_hint: str = "", diet_pref: List[str] = None) -> str:
    token = (cuisine_token or "global").lower()
    pool_key = token
    if pool_key.startswith("indian"):
        pool_key = "indian"
    if pool_key not in GEN_POOLS:
        pool_key = "global"
    pool = GEN_POOLS[pool_key]

    seed = f"{token}|{meal_type}|{','.join(sorted(disliked))}|{seed_hint}"
    short_seed = hashlib.md5(seed.encode()).hexdigest()[:8]

    base = _stable_choices(short_seed + "_base", pool["bases"], k=1)[0]
    protein = _stable_choices(short_seed + "_prot", pool["proteins"], k=1)[0]
    vegs = _stable_choices(short_seed + "_vegs", pool["vegs"], k=min(2, len(pool["vegs"])))
    extra = _stable_choices(short_seed + "_extra", pool["extras"], k=1)[0]
    spice = _stable_choices(short_seed + "_spice", pool["spices"], k=1)[0]

    if diet_pref and any(d.lower() == "vegan" for d in diet_pref):
        veg_options = ["tofu", "lentil", "beans", "edamame", "moong"]
        if not any(v in protein.lower() for v in veg_options):
            for p in pool["proteins"]:
                if any(v in p.lower() for v in veg_options):
                    protein = p
                    break

    def avoid(items):
        filtered = [it for it in items if not any(d.strip().lower() in it.lower() for d in disliked)]
        return filtered if filtered else items

    base = avoid([base])[0]
    protein = avoid([protein])[0]
    vegs = avoid(vegs)
    extra = avoid([extra])[0]
    spice = avoid([spice])[0]

    title = _make_title_from_base(token, base, protein, vegs, meal_type)

    ingredients = []
    base_lower = base.lower()
    if any(w in base_lower for w in ["rice", "noodles", "quinoa", "grains"]):
        ingredients.append(f"80g {base}")
    elif "phulka" in base_lower or "roti" in base_lower:
        ingredients.append("1 phulka/roti")
    else:
        ingredients.append(f"1 {base}")

    ingredients.append(f"100g {protein}")
    for v in vegs:
        ingredients.append(f"50g {v}")
    ingredients.append(f"{extra}")
    ingredients.append(f"Salt and {spice} to taste")

    steps = ["(recipe steps omitted)"]

    cal_est = 200
    protein_low = protein.lower()
    if any(legume in protein_low for legume in ["beans", "dal", "chana", "lentil", "moong"]):
        cal_est += 130
    if any(w in base_lower for w in ["rice", "pasta", "quinoa", "grains"]):
        cal_est += 90
    if "phulka" in base_lower or "roti" in base_lower:
        cal_est += 80
    cal_est = int(cal_est)

    key_base = f"{pool_key}_{meal_type}_{short_seed}".replace(" ", "_")
    key = key_base
    i = 1
    while key in SAMPLE_RECIPES:
        i += 1
        key = f"{key_base}_{i}"

    tags = [meal_type, pool_key, "vegetarian"]
    if diet_pref and any(d.lower() == "vegan" for d in diet_pref):
        tags.append("vegan")
    elif any(x in protein_low for x in ["paneer", "milk", "yogurt", "egg"]):
        tags.append("non-vegan")
    else:
        tags.append("vegetarian")

    SAMPLE_RECIPES[key] = {
        "title": title,
        "cal": cal_est,
        "ingredients": ingredients,
        "steps": steps,
        "cuisine": pool_key,
        "tags": tags
    }
    return key

# ---------- ensure pool ----------
def ensure_pool_size(cuisine_pref: str, meal_type: str, disliked: List[str], required: int, day_idx_start: int = 0, diet_pref: List[str] = None):
    tag_needed = "snacks" if meal_type == "snacks" else meal_type
    candidates = []
    for key, rec in SAMPLE_RECIPES.items():
        tags = rec.get("tags", [])
        if tag_needed not in tags:
            continue
        rec_cuisine = rec.get("cuisine","").lower()
        if cuisine_pref and cuisine_pref != "" and cuisine_pref != "global":
            if cuisine_pref.startswith("indian"):
                if rec_cuisine != "indian":
                    continue
            else:
                if rec_cuisine != cuisine_pref:
                    continue
        if any(d.strip() and (d.strip().lower() in key.lower() or any(d.strip().lower() in ing.lower() for ing in rec.get("ingredients", []))) for d in disliked):
            continue
        if diet_pref and any(d.lower() == "vegan" for d in diet_pref):
            tags_low = [t.lower() for t in tags]
            if "vegan" not in tags_low:
                continue
        candidates.append(key)

    safety = 0
    while len(candidates) < required and safety < 30:
        seed_hint = f"gen{len(candidates)}_{day_idx_start}"
        new_key = generate_synthetic_recipe(cuisine_pref or "global", meal_type, disliked, seed_hint=seed_hint, diet_pref=diet_pref)
        if new_key not in candidates:
            candidates.append(new_key)
        safety += 1

    return candidates

# ---------- detect base ----------
def detect_base_token(rec_key):
    rec = SAMPLE_RECIPES.get(rec_key, {})
    ings = " ".join(rec.get("ingredients", [])).lower()
    for token in ["phulka", "roti", "rice", "noodles", "quinoa", "grains", "tortilla"]:
        if token in ings:
            return token
    return "other"

# ---------- matches cuisine ----------
def matches_cuisine(rec, cuisine_token):
    if not cuisine_token or cuisine_token == "global":
        return True
    rec_cuisine = rec.get("cuisine", "").lower()
    if cuisine_token.startswith("indian"):
        if rec_cuisine != "indian":
            return False
        if cuisine_token == "indian_south":
            return "south" in [t.lower() for t in rec.get("tags", [])]
        if cuisine_token == "indian_north":
            return "north" in [t.lower() for t in rec.get("tags", [])]
        return True
    return rec_cuisine == cuisine_token.lower()

# ---------- core plan generator (minimize repeats) ----------
def safe_sample_recipes(pref: Optional[str], dislikes: List[str], days: int,
                        calorie_target: int, frequency: str = "repeat",
                        diet_pref: List[str] = None, time_per_meal: str = "Under 30 minutes",
                        cooking_skill: str = "Intermediate") -> Dict:
    meal_names = ("breakfast", "lunch", "dinner", "snacks")
    plan = {"daily_calories_estimate": calorie_target, "meals": {}}
    base_counter = {}
    cuisine_pref = (pref or "")

    def _gather_name_pool(meal_type: str, cuisine_token: str) -> List[str]:
        names = []
        if cuisine_token and cuisine_token in CANONICAL_DISHES:
            names.extend(CANONICAL_DISHES[cuisine_token].get(meal_type, []))
        if not cuisine_token or cuisine_token == "" or cuisine_token == "global":
            names.extend(CANONICAL_DISHES["global"].get(meal_type, []))

        for k, rec in SAMPLE_RECIPES.items():
            tags = rec.get("tags", [])
            rec_c = rec.get("cuisine", "")
            if meal_type == "snacks":
                tag_needed = "snacks"
            else:
                tag_needed = meal_type
            if tag_needed in tags:
                if cuisine_token and cuisine_token != "" and cuisine_token != "global":
                    if not matches_cuisine(rec, cuisine_token):
                        continue
                title = rec.get("title")
                if title and title not in names:
                    names.append(title)
        return names

    def _ensure_name_pool(meal_type: str, cuisine_token: str, disliked: List[str], need: int, seed_hint_base: str = ""):
        pool = _gather_name_pool(meal_type, cuisine_token)
        def hates(name):
            low = name.lower()
            return any(d.strip().lower() and d.strip().lower() in low for d in disliked)
        pool = [p for p in pool if not hates(p)]
        if diet_pref and any(d.lower() == "vegan" for d in diet_pref):
            # keep only items that are likely vegan: quick heuristic - filter out known dairy words
            pool = [p for p in pool if not any(x in p.lower() for x in ("paneer","curd","buttermilk","yogurt","milk"))]
        attempts = 0
        while len(pool) < need and attempts < 30:
            seed_hint = f"{seed_hint_base}_{len(pool)}_{attempts}"
            try:
                new_key = generate_synthetic_recipe(cuisine_token or "global", meal_type, disliked, seed_hint=seed_hint, diet_pref=diet_pref)
                title = SAMPLE_RECIPES[new_key].get("title", new_key.replace("_", " ").title())
                if not hates(title) and title not in pool:
                    if diet_pref and any(d.lower() == "vegan" for d in diet_pref):
                        tags_low = [t.lower() for t in SAMPLE_RECIPES[new_key].get("tags", [])]
                        if "vegan" not in tags_low:
                            attempts += 1
                            continue
                    pool.append(title)
            except Exception:
                pass
            attempts += 1
        return pool

    per_meal_pools = {}
    for meal in meal_names:
        need = days if frequency == "prefer_new_daily" else max(days, 6)
        pool = _ensure_name_pool(meal, cuisine_pref or "global", dislikes, need, seed_hint_base=f"{meal}")
        if len(pool) < need and cuisine_pref != "global":
            pool2 = _ensure_name_pool(meal, "global", dislikes, need, seed_hint_base=f"{meal}_global")
            for p in pool2:
                if p not in pool:
                    pool.append(p)
        per_meal_pools[meal] = pool

    used_names_per_meal = {m: [] for m in meal_names}
    time_map = {"Under 15 minutes": 15, "Under 30 minutes": 30, "Under 60 minutes": 60}
    estimated_time_min = time_map.get(time_per_meal, 30)

    for d in range(days):
        day_key = f"day_{d+1}"
        plan["meals"][day_key] = {}
        for meal_name in meal_names:
            pool = per_meal_pools.get(meal_name, [])[:]
            if not pool:
                pool = [rec.get("title", k) for k, rec in SAMPLE_RECIPES.items()]

            pool = [p for p in pool if not any(dd.strip().lower() in p.lower() for dd in dislikes)]

            chosen_name = None
            if frequency == "prefer_new_daily":
                candidates = [p for p in pool if p not in used_names_per_meal[meal_name]]
                if candidates:
                    seed = hashlib.sha256(f"{meal_name}-{d}-{len(candidates)}".encode()).hexdigest()
                    chosen_name = candidates[int(seed, 16) % len(candidates)]
                else:
                    usage_counts = {p: used_names_per_meal[meal_name].count(p) for p in pool}
                    pool_sorted = sorted(pool, key=lambda x: (usage_counts.get(x, 0), x))
                    chosen_name = pool_sorted[0] if pool_sorted else pool[0]
            else:
                candidates = [p for p in pool if p not in used_names_per_meal[meal_name]]
                if not candidates:
                    candidates = pool
                seed = hashlib.sha256(f"{meal_name}-{d}-{len(candidates)}".encode()).hexdigest()
                chosen_name = candidates[int(seed, 16) % len(candidates)]

            used_names_per_meal[meal_name].append(chosen_name)

            kcal = None
            matched_key = None
            for k, rec in SAMPLE_RECIPES.items():
                if rec.get("title", "").lower() == chosen_name.lower():
                    kcal = rec.get("cal", 200)
                    matched_key = k
                    break
            if kcal is None:
                if meal_name == "breakfast":
                    kcal = 220
                elif meal_name == "snacks":
                    kcal = 150
                else:
                    kcal = 380

            recipe_details = {"ingredients": SAMPLE_RECIPES[matched_key].get("ingredients", []) if matched_key else [],
                              "steps": SAMPLE_RECIPES[matched_key].get("steps", []) if matched_key else []}

            entry = {
                "name": chosen_name,
                "calories": kcal,
                "recipe": recipe_details,
                "estimated_time_min": estimated_time_min,
                "skill_level": cooking_skill
            }

            plan["meals"][day_key][meal_name] = [entry]

            if matched_key:
                base_tok = detect_base_token(matched_key)
                base_counter[base_tok] = base_counter.get(base_tok, 0) + 1
            else:
                low_chosen = chosen_name.lower()
                for cname, ings in CANONICAL_INGS.items():
                    if cname.lower() in low_chosen or low_chosen in cname.lower():
                        base_tok = detect_base_token(cname)
                        base_counter[base_tok] = base_counter.get(base_tok, 0) + 1
                        break

    plan["base_counts"] = base_counter

    if days == 1:
        plan["meals"] = plan["meals"]["day_1"]

    return plan

# ---------- calorie helpers ----------
def estimate_calories_lookup(item: str) -> Optional[int]:
    m = {
        "chocolate": 230, "chocolate bar": 230,
        "biscuit": 40, "biscuits": 40,
        "apple": 80, "banana": 100, "chips": 150, "cookie": 70,
        "sandwich": 300, "yogurt": 120
    }
    key = item.lower().strip()
    for k, v in m.items():
        if k in key:
            return v
    m2 = re.match(r'(\d+)\s*(biscuit|biscuits|chocolate|cookies?)', key)
    if m2:
        num = int(m2.group(1))
        token = m2.group(2)
        base = m.get(token if token in m else token.rstrip('s'), None)
        if base:
            return num * base
    return None

def estimate_calories_from_text(txt: str) -> int:
    tokens = re.split(r'[,\.\n;]', txt.lower())
    total = 0
    found_any = False
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        est = estimate_calories_lookup(t)
        if est:
            total += est
            found_any = True
        else:
            for word in ["chocolate", "biscuit", "cookie", "chips", "apple", "banana"]:
                if word in t:
                    e = estimate_calories_lookup(word)
                    if e:
                        m = re.search(r'(\d+)\s*' + word, t)
                        cnt = int(m.group(1)) if m else 1
                        total += e * cnt
                        found_any = True
                        break
    return total if found_any else 0

def make_compensation_advice(kcal: int) -> str:
    if kcal <= 0:
        return "I couldn't estimate the calories. Try 'I ate 2 biscuits' or 'I had a chocolate bar'."
    trim_per_day = int(round(kcal / 7))
    advice = (
        f"Matched snack estimate: **~{kcal} kcal**.\n\n"
        f"Immediate options to compensate today:\n"
        f"- Take a brisk 30–40 min walk (~{max(140, int(kcal * 0.7))} kcal burn depending on intensity).\n"
        f"- Or reduce ~{trim_per_day} kcal from later meals today (small portion change).\n\n"
        f"Simple 7-day adjustment: reduce daily intake by ~{trim_per_day} kcal for the next 7 days (or add 15–25 min moderate activity on 3–4 days).\n\n"
        f"One snack won't ruin progress — return to your usual plan tomorrow."
    )
    return advice

# ---------- enhanced intent parser ----------
def parse_message_intent(text: str) -> Tuple[str, dict]:
    """
    Expanded parser to match many nutrition-related queries. Returns an intent and metadata.
    """
    t = text.strip().lower()
    meta = {}

    if not t:
        return "none", meta

    # urgent / medical / safety
    if re.search(r'\b(emergency|choking|breathless|unable to breathe|anaphylax|loss of consciousness)\b', t):
        return "urgent", meta
    if re.search(r'\b(pregnant|pregnancy|i am pregnant|im pregnant)\b', t):
        return "pregnancy", meta
    if re.search(r'\b(allerg(y|ic)|hives|swollen|anaphylaxis|reaction)\b', t):
        return "allergic_reaction", meta

    # supplements: separate powder vs tablets
    if re.search(r'\b(tablet|pill|iron tablet|folic acid|multivitamin)\b', t):
        return "supplement_tablet", meta
    if re.search(r'\bprotein powder\b|\b(whey|casein|pea protein|soy protein)\b|\bsupplement\b', t):
        return "supplement_query", meta

    # grocery / shopping
    if re.search(r'\bgrocery list\b|\bwhat ingredients\b|\bshopping list\b|\bwhat to buy\b', t):
        return "grocery_request", meta

    # recipe/how-to
    if re.search(r'\bhow to\b|\brecipe\b|\bmake\b|\bhow do i cook\b|\bhow to make\b', t):
        m = re.search(r'(?:how to make|recipe for|how to cook|how to prepare)\s+(.*)', t)
        meta['dish'] = m.group(1).strip() if m else ""
        return "recipe_request", meta

    # goal-based: lose/gain/muscle/maintain
    if re.search(r'\b(lose weight|weight loss|low-?calorie|1200|1400|kcal|under \d+ kcal)\b', t):
        return "goal_lose", {"text": t}
    if re.search(r'\b(gain weight|gain|high-?calorie|bulk|calorie surplus)\b', t):
        return "goal_gain", {"text": t}
    if re.search(r'\b(muscle|high-?protein|build muscle|protein rich|20-25g|protein-rich|100g protein)\b', t):
        return "goal_muscle", {"text": t}
    if re.search(r'\b(maintain|maintenance|maintaining weight|1600|1800)\b', t):
        return "goal_maintain", {"text": t}

    # time relative or workout related
    if re.search(r'\b(before workout|after workout|pre workout|post workout)\b', t):
        return "workout_timing", {"text": t}

    # simple logging "I ate ..." pattern
    if re.search(r'\bi ate\b|\bi had\b|\bhad\b|\bjust ate\b', t):
        m = re.search(r'(?:i ate|i had|had|just ate)\s+(.*)', t)
        items = m.group(1) if m else t
        return "ate", {"items": items}

    # swap / dislike / avoid
    if re.search(r'\bswap\b|\breplace\b', t):
        m = re.search(r'swap\s+(.*?)\s+(?:for|with|to)\s+(.*)', t)
        if m:
            return "swap", {"from": m.group(1).strip(), "to": m.group(2).strip()}
        return "swap", {"raw": t}
    if re.search(r"(don't like|dont like|i dislike|avoid|dont include|do not include|avoid them)", t):
        m = re.search(r"(?:don't like|dont like|i dislike|avoid|dont include|do not include)\s*(.*)", t)
        return "dislike", {"items": m.group(1).strip() if m else ""}

    # ask for a plan
    if re.search(r'\b(meal plan|7-day|7 day|1-day|one day|weekly plan|give meal plan|make me a|create a)\b', t):
        return "generate_plan", {"text": t}

    # cuisine-based request
    for cuisine in ["south indian", "north indian", "indian", "chinese", "mexican", "italian", "global"]:
        if cuisine in t:
            return "cuisine_request", {"cuisine": cuisine, "text": t}

    # calorie/macro questions
    if re.search(r'\b(under \d+ calories|under \d+ kcal|300 calories|400 kcal|protein-rich|protein breakfasts|100g protein)\b', t):
        return "macro_calorie", {"text": t}

    # lifestyle questions
    if re.search(r'\b(bloated|during periods|periods|hostel|travel-friendly|travel friendly|what to eat today)\b', t):
        return "lifestyle", {"text": t}

    # fallback to general question / chat
    return "question", {"q": t}

# ---------- canonical dishes & ingredients ----------
CANONICAL_DISHES = {
    "indian_south": {
        "breakfast": [
            "Idli and sambar",
            "Plain dosa + chutney",
            "Masala dosa (small)",
            "Rava dosa (small)",
            "Upma",
            "Pongal (light)",
            "Pesarattu (moong dosa)",
            "Appam + veg stew",
            "Ragi dosa + chutney",
            "Vegetable idiyappam",
            "Oats upma"
        ],
        "lunch": [
            "Sambar rice + veg",
            "Curd rice + pickle (small)",
            "Vegetable biryani (small)",
            "Lemon rice + poriyal",
            "Tomato rice + veg kootu",
            "Rasam + rice + poriyal",
            "South Indian thali (light)",
            "Mixed veg kootu + rice",
            "Pongal with vegetable curry"
        ],
        "dinner": [
            "Idli (2) + sambar",
            "Dosa (plain) + chutney",
            "Vegetable upma",
            "Rasam bowl + veg",
            "Moong dal + rice (light)",
            "Idiyappam + stew",
            "Vegetable uttapam (small)",
            "Tomato dosa (small)",
            "Light lemon rice + veg"
        ],
        "snacks": [
            "Sundal (white chana)",
            "Roasted peanuts",
            "Steamed corn cup",
            "Fruit bowl",
            "Buttermilk + peanuts",
            "Mini veg salad cup",
            "Cucumber + chaat masala",
            "Roasted makhana",
            "Sprouts chaat",
            "Ragi malt drink",
            "Tender coconut water"
        ]
    },
    "indian_north": {
        "breakfast": [
            "Aloo paratha (small)",
            "Paneer paratha (small)",
            "Besan chilla",
            "Moong dal chilla",
            "Poha with peas",
            "Vegetable sandwich (small)",
            "Stuffed roti + curd",
            "Suji cheela",
            "Dalia upma",
            "Roti + light sabzi"
        ],
        "lunch": [
            "Dal tadka + Roti",
            "Chana masala + Roti",
            "Rajma + Rice (small bowl)",
            "Paneer bhurji + Roti",
            "Aloo gobi + Roti",
            "Mixed veg curry + Roti",
            "Kadhi + Rice (small)",
            "Lauki sabzi + Roti",
            "Palak paneer + Roti",
            "Veg pulao + raita"
        ],
        "dinner": [
            "Moong dal + Phulka",
            "Vegetable khichdi",
            "Palak dal + rice",
            "Sprouted lentil sabzi + roti",
            "Baingan bharta + roti",
            "Light paneer curry + roti",
            "Gajar matar sabzi + roti",
            "Tomato dal + 1 phulka",
            "Veg soup + roti (light)"
        ],
        "snacks": [
            "Roasted chana",
            "Sprouts chaat",
            "Roasted makhana",
            "Fruit chaat",
            "Masala peanuts",
            "Cucumber sticks + salt",
            "Carrot sticks (skip if allergy)",
            "Small poha bowl",
            "Boiled moong salad",
            "Buttermilk + peanuts"
        ]
    },
    "indian": {
        "breakfast": [
            "Idli and sambar",
            "Masala dosa (small)",
            "Upma",
            "Poha with peas",
            "Besan chilla",
            "Moong dal chilla",
            "Rava dosa (small)",
            "Oats upma",
            "Dalia upma",
            "Stuffed paratha (small)"
        ],
        "lunch": [
            "Dal tadka + Roti",
            "Toor dal khichdi",
            "Chana masala + Roti",
            "Paneer bhurji + Rice",
            "Sambar rice + veg",
            "Rajma + Rice (small)",
            "Veg biryani (small)",
            "Lemon rice + poriyal",
            "Mixed veg sabzi + roti"
        ],
        "dinner": [
            "Moong dal + Phulka",
            "Vegetable khichdi",
            "Rasam + Rice (small)",
            "Palak paneer + roti",
            "Sprouted lentil sabzi + roti",
            "Tomato rice + curd",
            "Idli + chutney (light)",
            "Veg stew + appam"
        ],
        "snacks": [
            "Roasted chana",
            "Sprouts chaat",
            "Roasted makhana",
            "Fruit chaat",
            "Sundal",
            "Corn cup",
            "Veg soup cup",
            "Buttermilk + peanuts",
            "Ragi malt drink",
            "Mini salad cup"
        ]
    },
    "chinese": {
        "breakfast": [
            "Veg congee",
            "Steamed buns",
            "Scallion pancake (vegan)",
            "Tofu scramble (Asian style)",
            "Rice porridge with veg",
            "Mini steamed dim sum platter",
            "Plain noodle soup (small)",
            "Corn porridge",
            "Savory soy oats",
            "Mung bean pancake"
        ],
        "lunch": [
            "Veg fried rice",
            "Vegetable chow mein",
            "Hakka noodles + veg",
            "Szechuan veg bowl",
            "Stir-fried tofu with capsicum",
            "Steamed veg + brown rice bowl",
            "Edamame rice bowl",
            "Mixed mushroom stir-fry + rice",
            "Tofu & bok choy bowl",
            "Vegetable lo mein (small)"
        ],
        "dinner": [
            "Clear veg noodle soup",
            "Garlic edamame + rice",
            "Tofu & veg stir-fry",
            "Hot-and-sour veg soup + small rice",
            "Stir-fried greens + steamed rice",
            "Vegetable hotpot (small)",
            "Steamed fish + greens (light)",
            "Miso-ish veg soup + noodles",
            "Teriyaki tofu + steamed rice",
            "Light vegetable congee"
        ],
        "snacks": [
            "Steamed dumplings (veg)",
            "Edamame (steamed)",
            "Veg spring rolls (baked)",
            "Veg salad mini bowl",
            "Boiled corn cup",
            "Tofu cubes with soy-ginger",
            "Veg soup cup",
            "Fruit bowl (small)",
            "Rice crackers",
            "Momo (veg, steamed)",
            "Seaweed snack + edamame",
            "Cucumber salad small cup"
        ]
    },
    "mexican": {
        "breakfast": [
            "Vegan breakfast burrito (small)",
            "Scrambled eggs with salsa",
            "Mexican-style oats",
            "Corn tortillas + beans",
            "Huevos rancheros (light)",
            "Black bean toast (small)",
            "Avocado toast (Mexican-style)",
            "Chilaquiles (light)"
        ],
        "lunch": [
            "Black bean bowl",
            "Veg fajita bowl",
            "Mexican rice + grilled veg",
            "Quinoa burrito bowl",
            "Bean & corn salad bowl",
            "Grilled veg tacos (2 small)",
            "Lentil taco salad",
            "Chicken taco (small)"
        ],
        "dinner": [
            "Tortilla soup",
            "Vegetable fajitas",
            "Black bean stew + rice",
            "Veg enchiladas (small)",
            "Grilled fish tacos",
            "Stuffed peppers (Mexican spice)",
            "Quinoa & corn stuffed tortillas"
        ],
        "snacks": [
            "Guacamole + veg sticks",
            "Roasted spiced peanuts",
            "Mini corn cup",
            "Baked tortilla chips + salsa (small)",
            "Bean & corn salad (small)",
            "Fruit bowl (small)",
            "Veg quesadilla mini piece",
            "Cucumber-lime cups"
        ]
    },
    "global": {
        "breakfast": [
            "Overnight oats (plant milk)",
            "Greek-style tofu scramble",
            "Berry porridge",
            "Smoothie bowl (small)",
            "Wholegrain toast + avocado",
            "Quinoa porridge",
            "Chia pudding (small)"
        ],
        "lunch": [
            "Mediterranean buddha bowl",
            "Quinoa & veg salad",
            "Lentil salad bowl",
            "Grilled vegetable wrap (small)",
            "Chickpea & cucumber salad",
            "Farro salad with veg",
            "Mediterranean pita + hummus"
        ],
        "dinner": [
            "Veg pasta in tomato-herb sauce",
            "Grilled protein + salad",
            "Lentil stew",
            "Roasted veg + couscous",
            "Baked salmon + steamed veg (small)",
            "Stuffed portobello + salad",
            "Vegetable curry (global style) + grains"
        ],
        "snacks": [
            "Hummus + veggie sticks",
            "Roasted almonds",
            "Fruit & nut mix",
            "Greek yogurt mini cup",
            "Mixed salad small bowl",
            "Protein bar (small)",
            "Mini oats cup",
            "Smoothie small glass",
            "Cottage cheese + fruit (small)",
            "Rice cakes + nut butter"
        ]
    }
}

CANONICAL_INGS = {
    "Poha with peas": ["Poha (flattened rice)", "Peas", "Onion", "Mustard seeds", "Curry leaves", "Lemon"],
    "Besan chilla": ["Besan (gram flour)", "Onion", "Tomato", "Coriander"],
    "Idli and sambar": ["Idli batter", "Toor dal", "Sambar vegetables", "Tamarind"],
    "Upma": ["Rava (semolina)", "Onion", "Mustard seeds", "Peas"],
    "Veg fried rice": ["Rice", "Mixed vegetables", "Soy sauce"],
    "Steamed dumplings (veg)": ["Dumpling wrappers", "Mixed veg filling"],
    "Black bean bowl": ["Black beans", "Corn", "Tomato", "Avocado (optional)"],
    "Guacamole + veg sticks": ["Avocado", "Tomato", "Lime", "Veg sticks"],
    "Mediterranean buddha bowl": ["Quinoa", "Chickpeas", "Cucumber", "Tomato", "Olive oil"],
    "Hummus + veggie sticks": ["Chickpeas", "Tahini", "Veg sticks"],
    "Roasted almonds": ["Almonds"],
    "Fruit & nut mix": ["Dried fruit", "Nuts"],
}

# ---------- suggestion helper (no grocery output) ----------
def create_suggestion_block(user_query: str, cuisine_sidebar: str, dislikes_text: str) -> str:
    q = user_query.lower()
    meal_type = None
    for token in ("breakfast", "lunch", "dinner", "snack", "snacks"):
        if token in q:
            meal_type = "snacks" if token.startswith("snack") else token
            break
    cuisine_from_query = None
    for k in ["south indian", "north indian", "indian", "chinese", "mexican", "global"]:
        if k in q:
            cuisine_from_query = k
            break
    if cuisine_from_query:
        cuisine_token = "indian" if "indian" in cuisine_from_query else cuisine_from_query
    else:
        cuisine_token = CUISINE_MAP.get(cuisine_sidebar, "") or ""
        if cuisine_token.startswith("indian"):
            cuisine_token = "indian"
        if cuisine_token == "":
            cuisine_token = "global"

    disliked = [d.strip().lower() for d in (dislikes_text or "").split(",") if d.strip()]

    canon_for_cuisine = CANONICAL_DISHES.get(cuisine_token, CANONICAL_DISHES["global"])
    mt = meal_type or "lunch"
    options = canon_for_cuisine.get(mt, canon_for_cuisine.get("lunch", []))

    seed = hashlib.md5(user_query.encode("utf-8")).hexdigest()
    picks = _stable_choices(seed + "_canon", options, k=min(6, len(options)))

    final_picks = []
    for p in picks:
        ings = CANONICAL_INGS.get(p, [])
        low_ings = " ".join(ings).lower()
        if any(d in low_ings for d in disliked if d):
            continue
        final_picks.append((p, ings))
    if not final_picks:
        final_picks = [(p, CANONICAL_INGS.get(p, [])) for p in picks]

    suggestions_out = []
    for dish_name, ings in final_picks:
        cal = None
        dn_low = dish_name.lower()
        for key, rec in SAMPLE_RECIPES.items():
            title = rec.get("title", "").lower()
            # rough match
            if any(tok in title for tok in dn_low.split()) or dn_low in title or title in dn_low:
                cal = rec.get("cal")
                break
        if cal is None:
            if mt == "breakfast":
                cal = 250
            elif mt == "snacks":
                cal = 150
            else:
                cal = 400
        suggestions_out.append((dish_name, cal, ings))

    if meal_type:
        header = f"Here are quick suggestions for {meal_type.title()} (no plan changes):"
    else:
        header = "Here are quick dish suggestions (no plan changes):"

    lines = [header, ""]
    for t, c, ings in suggestions_out:
        lines.append(f"- {t} — {c} kcal")
        if ings:
            # show brief ingredient hints inline (not a grocery list)
            ing_line = ", ".join(ings[:4])  # short sample
            lines.append(f"  (main ingredients: {ing_line})")
    lines.append("")
    lines.append("Tip: ask 'give meal plan' to apply changes or 'make a 7-day plan' to generate a weekly rotation.")
    return "\n".join(lines)

# ---------- serious/medical detection ----------
def is_serious_query(text: str) -> Optional[str]:
    """
    Return a short reason if the query looks medically-serious or about a clinical condition
    that requires a clinician/dietitian. Otherwise return None.
    """
    t = text.lower()
    # keywords that indicate medical / clinical / risky situation
    serious_terms = [
        "diabetes", "type 1", "type 2", "insulin", "hypogly", "blood sugar",
        "heart attack", "chest pain", "cardiac", "heart disease", "stroke",
        "kidney", "renal", "dialysis", "liver", "cirrhosis",
        "cancer", "chemotherapy", "oncology",
        "pregnancy complication", "gestational diabetes", "pre-eclampsia", "miscarriage",
        "surgery", "post-op", "post operative", "organ transplant", "immunosuppressed",
        "food poisoning", "anaphylaxis", "severe allergic", "unable to breathe",
        "severe swelling", "unconscious", "hospital", "emergency"
    ]
    for p in serious_terms:
        if p in t:
            return p
    # if user mentions a prescription drug or says 'medication' + 'affect diet' etc.
    if re.search(r'\b(medication|medications|prescription|beta blocker|warfarin|metformin|insulin|statin)\b', t):
        return "medication"
    return None

# ---------- free chat responder (expanded) ----------
def free_chat_response(intent: str, meta: dict, text: str, user_payload: dict) -> str:
    """
    A rule-based open chat responder covering general, goal-based, cuisine-based,
    calorie/macro, recipe, grocery, lifestyle, supplement and safety intents.
    Adds clear referral to clinician/dietitian for serious topics.
    """
    t = text.strip()
    t_low = t.lower()

    # immediate: if query looks medically serious, advise clinician
    serious = is_serious_query(t)
    if serious:
        return ("I may not be able to provide clinical nutrition advice for that condition.\n"
                "This looks like a medical topic (keyword: '{}'). Please consult your doctor or a registered dietitian for tailored, safe guidance.").format(serious)

    # urgent
    if intent == "urgent":
        return "If someone is in immediate danger (severe breathing difficulty, unconsciousness, severe swelling), call emergency services now."

    # eaten / log
    if intent == "ate":
        items = meta.get("items", text)
        kcal = estimate_calories_from_text(items)
        advice = make_compensation_advice(kcal)
        return advice + "\n\nNote: calorie estimates are rough. For medical weight management, consult a registered dietitian."

    # pregnancy: sample day + small grocery hints
    if intent == "pregnancy":
        day_plan = [
            ("Breakfast", "Oats porridge with milk/plant milk + fruit — 300–350 kcal"),
            ("Snack", "Greek yogurt or roasted chana — 120 kcal"),
            ("Lunch", "Brown rice + dal + cooked veg + salad — 450–550 kcal"),
            ("Snack", "Sprouts or nut butter on toast — 120 kcal"),
            ("Dinner", "Light khichdi or dal + 1–2 phulkas + cooked greens — 350–450 kcal"),
        ]
        lines = ["Pregnancy-friendly sample day (general guidance):", ""]
        for m, d in day_plan:
            lines.append(f"- {m}: {d}")
        lines.append("")
        lines.append("Ingredient hints: oats, milk/plant milk, brown rice, moong dal, mixed vegetables, leafy greens, sprouts, yogurt/curd, nuts")
        lines.append("")
        lines.append("Safety note: This is general guidance. For personalised recommendations (iron/folate requirements, gestational diabetes, high-risk pregnancy) consult your OB/GYN or a registered dietitian.")
        return "\n".join(lines)

    if intent == "allergic_reaction":
        return ("If you're experiencing severe symptoms (trouble breathing, swelling of face/throat, dizziness), call emergency services immediately. "
                "For mild reactions, stop the food, take an antihistamine if appropriate and contact your doctor. I can remove that ingredient from future plans.")

    # supplements: tablet vs powder
    if intent == "supplement_tablet":
        return ("Tablets/pills usually mean micronutrient or prescription supplements (e.g., iron, folic acid, multivitamin). "
                "Protein tablets are different from protein powders — powders supply grams of protein (macros), tablets usually give small amounts of specific nutrients. "
                "If this is for pregnancy or a medical condition, speak to your clinician before starting.")

    if intent == "supplement_query":
        out = ("Protein powders: common types and quick guidance:\n"
               "- Whey (dairy): fast-absorbing, good post-workout for muscle gain.\n"
               "- Casein (dairy): slower-release, useful at night.\n"
               "- Plant proteins (pea, soy, rice): for vegans or dairy intolerance.\n\n"
               "For muscle gain: aim to include 20–30 g protein at main meals. Protein powders can help reach daily protein targets.")
        # if user mentions pregnancy or medical, add consult note
        if "preg" in t_low or "medic" in t_low:
            out += "\n\nIf you are pregnant, breastfeeding or on medication, consult your clinician before starting supplements."
        return out

    # grocery request: give short ingredient hints if plan present
    if intent == "grocery_request":
        plan = st.session_state.get("plan", {})
        if plan:
            lines = ["Ingredients (short hints) for the current plan:"]
            meals = plan.get("meals", {})
            seen = set()
            count = 0
            if isinstance(meals, dict):
                # pick first day if multi-day
                day = next(iter(meals)) if any(k.startswith("day_") for k in meals.keys()) else None
                if day:
                    day_meals = meals[day]
                    for meal_items in day_meals.values():
                        for it in meal_items:
                            ings = it.get("recipe", {}).get("ingredients", []) or []
                            for g in ings:
                                if g not in seen:
                                    lines.append(f"- {g}")
                                    seen.add(g)
                                    count += 1
                                    if count >= 30:
                                        break
                            if count >= 30:
                                break
                        if count >= 30:
                            break
                else:
                    for meal_items in meals.values():
                        for it in meal_items:
                            ings = it.get("recipe", {}).get("ingredients", []) or []
                            for g in ings:
                                if g not in seen:
                                    lines.append(f"- {g}")
                                    seen.add(g)
                                    count += 1
                                    if count >= 30:
                                        break
                            if count >= 30:
                                break
                        if count >= 30:
                            break
            if len(lines) == 1:
                lines.append("- No recipe-level ingredients found; ask 'show ingredients for X' or generate a plan first.")
            return "\n".join(lines)
        return "No plan generated yet. Use 'Generate Meal Plan' then ask 'what ingredients do I need'."

    # recipe request: return a compact, practical recipe
    if intent == "recipe_request":
        dish = meta.get("dish", "") or text
        dish = dish.strip()
        # Try to find canonical recipe
        for k, vals in CANONICAL_INGS.items():
            if dish.lower() in k.lower() or k.lower() in dish.lower():
                ings = CANONICAL_INGS.get(k, [])
                steps = SAMPLE_RECIPES.get(next((s for s in SAMPLE_RECIPES if SAMPLE_RECIPES[s].get("title","").lower()==k.lower()), ""), {}).get("steps", [])
                out = [f"Recipe: {k}", ""]
                if ings:
                    out.append("Ingredients:")
                    for g in ings:
                        out.append(f"- {g}")
                if steps:
                    out.append("")
                    out.append("Steps:")
                    for s in steps:
                        out.append(f"- {s}")
                else:
                    out.append("")
                    out.append("Steps: (short)\n- Prepare the main ingredient, season, cook until done. Serve hot.")
                return "\n".join(out)
        # fallback short recipe
        return f"I don't have the detailed recipe for '{dish}' in the small dataset. Ask 'simple recipe for lemon rice' or a specific dish and I'll give a short step-by-step."

    # goal-based handlers
    if intent.startswith("goal_"):
        goal_text = intent.split("_", 1)[1]
        if goal_text == "lose":
            return ("Low-calorie weight-loss guidance (general, non-medical):\n"
                    "- Aim for a moderate deficit (e.g., 300–500 kcal/day below maintenance).\n"
                    "- Prefer high-fiber veggies, lean protein (dal, tofu, paneer in moderation), whole grains in small portions.\n"
                    "- Sample day: Breakfast: moong dal chilla; Lunch: 1 cup brown rice + dal + veg; Dinner: light khichdi + salad.\n"
                    "Ask 'give me a 7-day low-calorie South Indian plan' to generate a structured plan.\n\n"
                    "If you have medical conditions (diabetes, kidney disease), consult a clinician/dietitian for a tailored plan.")
        if goal_text == "gain":
            return ("High-calorie / weight-gain guidance (general):\n"
                    "- Increase calorie density using nuts, healthy oils, dairy or plant-based calories.\n"
                    "- Include 3–4 meals + 2 snacks. Add a protein source each meal.\n"
                    "- Sample snack ideas: peanut butter toast, banana + milkshake, roasted chana + jaggery.\n"
                    "Ask 'make a high-calorie Indian meal plan' to generate a structured plan.")
        if goal_text == "muscle":
            return ("Muscle-building guidance (general):\n"
                    "- Aim for 1.4–2.0 g protein/kg bodyweight per day depending on activity.\n"
                    "- Target 20–30 g protein per main meal. Include protein-rich breakfasts (moong chilla, paneer bhurji), lunches (dal + rice + salad) and post-workout protein (whey/plant powder).\n"
                    "- Before workout: small carb + protein (banana + peanut butter). After workout: 20–30 g protein shake or dal + roti + veg.\n"
                    "Ask 'Make me a high-protein Indian diet for muscle gain' for a structured daily plan.")
        if goal_text == "maintain":
            return ("Maintenance guidance (general):\n"
                    "- Balanced meals across day, moderate portions of whole grains, legumes, vegetables and protein.\n"
                    "- Sample: 1600–1800 kcal balanced home-style thali with 1 cup rice or 2 rotis, dal, vegetable sabzi and salad.")
    # workout timing
    if intent == "workout_timing":
        return ("Before workout: small carbohydrate + little protein (banana + peanut butter or toast + curd) 30–60 min before.\n"
                "After workout: 20–30 g protein within 1 hour (protein shake or dal + roti) + some carbs to replenish glycogen.")

    # cuisine requests
    if intent == "cuisine_request":
        c = meta.get("cuisine", "indian")
        if "south" in c:
            return ("South Indian plan idea (weight loss focus):\n"
                    "- Breakfast: idli (2) + sambar\n- Mid snack: buttermilk\n- Lunch: lemon rice (small) + veg kootu + salad\n- Evening: roasted chana\n- Dinner: moong dal khichdi + steamed veg\nAsk 'give meal plan' to make this a 7-day plan.")
        if "north" in c:
            return ("North Indian muscle-building idea:\n"
                    "- Breakfast: moong dal chilla or paneer paratha\n- Lunch: rajma or chana + rice/roti + salad\n- Snacks: roasted peanuts/roasted chana\n- Dinner: paneer bhurji + roti\nInclude protein powder post-workout for extra protein if needed.")
        return create_suggestion_block(text, user_payload.get("cuisine", ""), user_payload.get("dislikes", ""))

    # macro/calorie specific
    if intent == "macro_calorie":
        return ("Calorie / macro guidance (examples):\n"
                "- Meals under 300–400 kcal: moong dal chilla (~180 kcal), small idli + sambar (~150–200 kcal), sprouts salad (~100 kcal).\n"
                "- Protein-rich Indian breakfasts: moong chilla, besan chilla with paneer, paneer bhurji on toast.\n"
                "- For 100 g protein/day: aim for ~25–30 g protein per meal and 2 high-protein snacks.")

    # lifestyle
    if intent == "lifestyle":
        q = meta.get("text", t_low)
        if "bloated" in q:
            return ("If you feel bloated: prefer light cooking, avoid high-FODMAP foods for that meal, try warm water/lemon, light soup or steamed vegetables. "
                    "Avoid carbonated drinks and very high-fat meals until you feel better.")
        if "period" in q or "during periods" in q:
            return ("During periods: eat iron- and magnesium-rich foods, include whole grains, legumes, leafy greens, nuts; warm soups and hydrating foods help with cramps. "
                    "Small balanced meals with protein help energy.")
        if "hostel" in q or "travel" in q or "travel-friendly" in q:
            return ("Hostel/Travel-friendly tips:\n- Carry roasted chana, peanut butter sachets, fruit, nuts, and instant oats. \n- Opt for grilled/steamed items and avoid deep-fried street food where possible.")
        return "Lifestyle tip: ask more specifically (e.g., 'what to eat when bloated' or 'hostel-friendly high-protein snacks')."

    # swap/dislike
    if intent == "swap":
        if meta.get("from") and meta.get("to"):
            return (f"Swap noted: replace '{meta['from']}' with '{meta['to']}' in future plans. To apply now, press 'Generate Meal Plan' or ask 'give meal plan'.")
        return ("Swap noted. If you tell me 'swap X for Y' now I can mark X as disliked for future plans. To apply, press 'Generate Meal Plan' or ask 'give meal plan'.")

    if intent == "dislike":
        items = meta.get("items", "")
        return (f"Got it — I'll avoid '{items}' in regenerated plans. To apply now, ask 'give meal plan' or press Generate Meal Plan. For severe allergies, seek medical advice.")

    # recipe/dish related (fallback to suggestions)
    food_terms = ["dish", "recipe", "meal", "mexican", "indian", "chinese", "breakfast", "lunch", "dinner", "snack", "vegan", "vegetarian", "keto", "low-carb", "what to eat"]
    if any(ft in t_low for ft in food_terms):
        return create_suggestion_block(text, user_payload.get("cuisine", ""), user_payload.get("dislikes", ""))

    # fallback general chat answer
    # broaden what we say so the user can ask many of the examples you provided
    fallback = [
        "I can answer many nutrition and food-related questions including:",
        "- Goal-based plans (lose/gain/build muscle/maintain).",
        "- Cuisine-specific suggestions (South Indian, North Indian, Chinese, Mexican, etc.).",
        "- Food preferences and allergies handling (vegan, no-dairy, avoid carrots, include chicken X times/week).",
        "- Calorie/macro queries (meals under X kcal, protein-rich breakfasts, 100 g protein day).",
        "- Rice/roti/thali questions and healthy dosa options.",
        "- Grocery/ingredient hints for a generated plan (short hints, not full shopping lists by default).",
        "- Recipes and low-oil cooking tips.",
        "- Lifestyle questions (bloating, periods, hostel/travel-friendly meals).",
        "",
        "Examples you can ask directly:",
        "- 'Make me a high-protein Indian diet for muscle gain.'",
        "- 'Give a 7-day low-calorie South Indian plan.'",
        "- 'What should I eat before and after workout?'",
        "- 'Show me a simple recipe for lemon rice.'",
        "- 'I am allergic to carrots — avoid them in my plan.'",
        "",
        "If a question is medical or complex (diabetes, kidney disease, pregnancy complications, or interactions with prescription medication), I'll advise consulting a clinician/dietitian."
    ]
    return "\n".join(fallback)

# ---------- PDF generator ----------
def generate_pdf_bytes(plan: dict, user_meta: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    margin = 20 * mm
    y = h - margin
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "Personalized Meal Plan")
    c.setFont("Helvetica", 10)
    y -= 14
    c.drawString(margin, y, f"Name: {user_meta.get('name','-')}   Age: {user_meta.get('age','-')}   Goal: {user_meta.get('goal','-')}")
    y -= 12
    c.drawString(margin, y, f"Estimated daily calories: {plan.get('daily_calories_estimate','-')} kcal")
    y -= 16
    if "meals" in plan and isinstance(plan["meals"], dict):
        if any(k.startswith("day_") for k in plan["meals"].keys()):
            for day, contents in plan["meals"].items():
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margin, y, day.replace("_", " ").title())
                y -= 12
                for meal, items in contents.items():
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(margin + 8, y, meal.title())
                    y -= 12
                    c.setFont("Helvetica", 10)
                    for dish in items:
                        c.drawString(margin + 14, y, f"- {dish.get('name','Dish')} ({dish.get('calories','?')} kcal) [{dish.get('estimated_time_min','?')} min, {dish.get('skill_level','-')}]")
                        y -= 10
                        if y < margin + 80:
                            c.showPage(); y = h - margin
                y -= 8
                if y < margin + 80:
                    c.showPage(); y = h - margin
        else:
            for meal, items in plan["meals"].items():
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margin, y, meal.title())
                y -= 12
                c.setFont("Helvetica", 10)
                for dish in items:
                    c.drawString(margin + 8, y, f"- {dish.get('name','Dish')} ({dish.get('calories','?')} kcal) [{dish.get('estimated_time_min','?')} min]")
                    y -= 10
                    if y < margin + 80:
                        c.showPage(); y = h - margin
                y -= 8
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

# ---------- UI CSS ----------
PAGE_CSS_SMALL = """
<style>
.stApp { font-family: Inter, Roboto, "Segoe UI", Helvetica, Arial, sans-serif; }
.main-card { background: rgba(255,255,255,0.92); border-radius:12px; padding:18px; }
.recipe-card { background: white; padding:12px; border-radius:8px; margin-bottom:10px; }
.assistant-box { background: rgba(220,235,255,0.95); padding:14px; border-radius:8px; margin-bottom:14px; border:1px solid rgba(170,200,230,0.9); color:#0e3b66; }
.metric { display:inline-block; padding:6px 10px; border-radius:999px; background:#10b981; color:white; font-weight:600; }
.small-muted { color:#667085; font-size:13px; }
</style>
"""
st.markdown(PAGE_CSS_SMALL, unsafe_allow_html=True)

# ---------- session defaults ----------
if "plan" not in st.session_state:
    st.session_state["plan"] = {}
if "assistant_reply" not in st.session_state:
    st.session_state["assistant_reply"] = ""
if "last_intent" not in st.session_state:
    st.session_state["last_intent"] = None

# ---------- Sidebar (inputs + ask) ----------
with st.sidebar:
    st.header("User inputs")
    name = st.text_input("Name", value="", key="name_input")
    age = st.number_input("Age", min_value=1, max_value=120, value=21, key="age_input")
    weight = st.number_input("Weight (kg)", min_value=20.0, max_value=300.0, value=60.0, key="weight_input")
    height = st.number_input("Height (cm)", min_value=100.0, max_value=230.0, value=157.0, key="height_input")
    gender = st.selectbox("Gender", ["male", "female"], index=0, key="gender_input")
    activity = st.selectbox("Activity level", ["Sedentary", "Lightly active", "Moderately active", "Very active"], key="activity_input")
    goal = st.selectbox("Goal", ["Maintain weight", "Lose weight", "Gain weight", "Improve muscle"], key="goal_input")

    diet_pref = st.multiselect(
        "Dietary preference",
        ["Vegetarian", "Vegan", "Pescatarian", "Keto", "Low-carb", "No preference"],
        default=["No preference"],
        key="diet_pref_input"
    )

    allergies = st.text_input("Allergies / intolerances (comma separated)", value="", key="allergies_input")

    st.markdown("---")
    st.subheader("Meal preferences")

    cuisine = st.selectbox(
        "Cuisine (choose one)",
        [
            "No preference",
            "Indian (South)",
            "Indian (North)",
            "Indian (All regions)",
            "Chinese",
            "Mexican",
            "Global"
        ],
        index=0,
        key="cuisine_input"
    )

    likes = st.text_input("Likes (comma separated)", value="", key="likes_input")
    dislikes_food = st.text_input("Dislikes (comma separated)", value="", key="dislikes_input")

    meal_time_pref = st.selectbox("Meal-time preference", ["Neutral", "Heavy breakfast", "Light dinner", "Intermittent fasting"], index=0, key="meal_time_pref_input")
    cooking_skill = st.selectbox("Cooking skill & equipment", ["Beginner", "Intermediate", "Pro"], index=1, key="cooking_skill_input")
    time_per_meal = st.selectbox("Time per meal", ["Under 15 minutes", "Under 30 minutes", "Under 60 minutes"], index=1, key="time_per_meal_input")
    spice_level = st.selectbox("Spice / heat level", ["Mild", "Medium", "Spicy"], index=1, key="spice_level_input")
    freq_variety = st.selectbox("Frequency / variety", ["Prefer new recipe daily", "Rotate favorites", "Repeat favorites"], index=0, key="freq_variety_input")
    st.markdown("---")
    use_custom_calorie = st.checkbox("Specify custom daily calorie target?", value=False, key="use_custom_calorie_input")
    calorie_target = None
    if use_custom_calorie:
        calorie_target = st.number_input("Daily calorie target (kcal)", min_value=800, max_value=5000, value=2000, step=50, key="calorie_target_input")
    st.markdown("---")
    generate_weekly = st.checkbox("Generate 7-day plan (weekly)", value=False, key="generate_weekly_input")
    # single generate button (no duplicate)
    generate_btn = st.button("Generate Meal Plan (sidebar)", key="generate_btn_input")

    st.markdown("---")
    st.markdown("## Ask anything (chat)")
    st.markdown("<div class='small-muted'>Ask general questions (goals, cuisine, recipes, swaps, calorie checks, lifestyle).</div>", unsafe_allow_html=True)
    ask_input = st.text_input("Your message (ask)", value="", key="ask_input")
    ask_button = st.button("Ask", key="ask_button_input")

# ---------- utility: default calorie estimate & blurb ----------w
def estimate_default_calories(age, weight, height, gender, activity_str):
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    factor = 1.2
    if activity_str == "Lightly active":
        factor = 1.375
    elif activity_str == "Moderately active":
        factor = 1.55
    elif activity_str == "Very active":
        factor = 1.725
    return int(round(bmr * factor))

def make_personalized_blurb(user_payload: dict, plan: dict) -> str:
    age = user_payload.get("age", "?")
    weight = user_payload.get("weight", "?")
    height_cm = user_payload.get("height", None)
    feet_inches = ""
    if isinstance(height_cm, (int, float)):
        total_inches = height_cm / 2.54
        feet = int(total_inches // 12)
        inches = int(round(total_inches % 12))
        feet_inches = f"{feet}'{inches}\""
    diet = " ".join(user_payload.get("diet_pref") or []) or "No preference"
    allergies = user_payload.get("allergies", "") or "none"
    dislikes = user_payload.get("dislikes", "") or "none"
    maintenance = estimate_default_calories(age, weight, height_cm or 170, user_payload.get("gender", "male"), user_payload.get("activity", "Sedentary"))
    target = plan.get("daily_calories_estimate", maintenance)
    deficit = maintenance - target
    if deficit >= 800:
        deficit_note = ("This is a large deficit — doing it many days in a row may not be safe for most people. "
                        "Consider using short periods (2–3 days/week) or a milder deficit and consult a professional for long-term changes.")
    elif deficit >= 400:
        deficit_note = ("This is a moderate deficit and can support steady weight loss when combined with activity. "
                        "Ensure protein intake is adequate to preserve lean mass.")
    else:
        deficit_note = "This is a modest deficit suitable for gentle, sustainable progress."
    pref = user_payload.get("cuisine") or "No preference"
    cuisine_hint = pref
    diet_line = f"{cuisine_hint} {diet} plan" if diet and diet.lower() != "no preference" else f"{cuisine_hint} plan"

    blurb_lines = []
    blurb_lines.append(f"Here is a simple, {cuisine_hint.lower()}, {diet.lower()} nutrition-focused plan designed to match your inputs.")
    blurb_lines.append(f"Your stats: {age} yrs | {weight} kg | {feet_inches or f'{height_cm} cm'} | {diet.lower()} | Allergies: {allergies} | Dislikes: {dislikes}")
    blurb_lines.append(f"Your estimated maintenance calories: ~{maintenance} kcal/day")
    blurb_lines.append(f"Target intake set for this plan: ~{target} kcal/day — this creates a daily deficit of ~{max(0, maintenance - target)} kcal. {deficit_note}")
    blurb_lines.append("")
    blurb_lines.append(f"🌿 {diet_line} (~{target} kcal/day)")
    blurb_lines.append("")
    blurb_lines.append("Balanced, filling, and appropriate for short-term calorie goals. Below are sample meal ideas (pick one option from each slot).")
    blurb_lines.append("")

    sample_lines = []
    if "indian" in (pref or "").lower():
        sample_lines.extend([
            "✅ MORNING: Warm lemon water or jeera water (0–5 kcal)",
            "Breakfast: Moong dal chilla / idli — 150–250 kcal",
            "Mid-morning snack: Fruit or roasted chana — 70–120 kcal",
            "Lunch: 1 cup brown rice + dal + veg or 2 phulkas + sabzi — 300–450 kcal",
            "Evening: Sprouts salad or buttermilk — ~100 kcal",
            "Dinner: Light khichdi or dal + roti — 200–350 kcal",
        ])
    else:
        sample_lines.extend([
            "✅ MORNING: Lemon water or herbal tea (0–5 kcal)",
            "Breakfast: Overnight oats / tofu scramble — ~200–300 kcal",
            "Mid-morning snack: Fruit or nuts (small portion) — 70–100 kcal",
            "Lunch: Grain bowl or salad with legumes — 300–450 kcal",
            "Evening: Hummus + veg sticks or yogurt — ~100 kcal",
            "Dinner: Soup or grilled protein + veg — 250–400 kcal",
        ])

    blurb_lines.extend(sample_lines)
    blurb_lines.append("")
    blurb_lines.append("🌱 Foods to prefer: leafy greens, cucumbers, low-cal veg, soups, legumes, whole grains in small portions.")
    blurb_lines.append("🚫 Avoid: items you listed under allergies/dislikes, fried/very sugary foods, and very large portions of nuts/high-fat dairy if targeting low calories.")
    blurb_lines.append("")
    blurb_lines.append("Note: For long-term or large calorie changes, or if you have health conditions, consult a registered dietitian or clinician.")
    return "\n\n".join(blurb_lines)

# ---------- plan builder ----------
def build_and_store_plan(days: int, user_payload: dict, frequency_choice: str) -> Dict:
    cal_target = user_payload.get("calorie_target")
    if not cal_target:
        cal_target = estimate_default_calories(user_payload.get("age", 20), user_payload.get("weight", 60),
                                               user_payload.get("height", 170), user_payload.get("gender", "male"),
                                               user_payload.get("activity", "Sedentary"))
    cuisine_raw = user_payload.get("cuisine", "") or ""
    cuisine_token = CUISINE_MAP.get(cuisine_raw, "")   # preserve 'indian_south', 'indian_north', etc

    disliked = [d.strip() for d in (user_payload.get("dislikes", "") or "").split(",") if d.strip()]
    allergies = [a.strip() for a in (user_payload.get("allergies", "") or "").split(",") if a.strip()]
    avoid_list = list({d.lower() for d in disliked + allergies})

    plan = safe_sample_recipes(
        cuisine_token,
        avoid_list,
        days,
        cal_target,
        frequency=frequency_choice,
        diet_pref=user_payload.get("diet_pref", []),
        time_per_meal=user_payload.get("time_per_meal", "Under 30 minutes"),
        cooking_skill=user_payload.get("cooking_skill", "Intermediate")
    )
    st.session_state["plan"] = plan
    return plan

freq_map = {
    "Prefer new recipe daily": "prefer_new_daily",
    "Rotate favorites": "prefer_new_daily",
    "Repeat favorites": "repeat"
}

# ---------- suggestion helper (no grocery output) ----------
# (already defined above as create_suggestion_block)

def free_chat_response_groq(user_msg: str, user_payload: dict) -> str:
    """
    Smart hybrid AI nutrition chat using Groq (llama-3.1-8b-instant).
    Automatically generates:
    - Simple suggestions for simple questions
    - Detailed answers when needed
    - Recipes when asked
    - Calories when relevant
    - Safety guidance for medical topics
    """

    system_prompt = """
    You are a friendly, expert AI nutrition assistant.

    GENERAL BEHAVIOR:
    - Answer ANY food, diet, nutrition, calorie, cuisine, meal ideas, recipe, thali, weight-loss/gain,
      protein, digestion, hostel-food, travel-food, or ingredient question.
    - Give short, clear, practical answers.
    - If user asks for "ideas" → give 3–6 suggestions.
    - If user asks for recipes → give ingredients + 3–5 steps.
    - If user asks about calories → give approximate kcal.
    - If user asks “what to eat today” → give a simple 1-day plan.
    - If user asks for a 7-day plan → DO NOT generate here. Tell them to click the sidebar button.

    USER PREFERENCES:
    - Avoid foods listed in dislikes/allergies: {user_payload}
    - Follow their cuisine preference when possible.
    - Follow their diet preference (vegan/vegetarian/no-dairy etc.).

    SAFETY:
    - If question involves pregnancy, diabetes, thyroid, kidney, liver, heart issues,
      medications or medical symptoms:
      → Give general safe advice.
      → Add: "Please consult a clinician/dietitian for personalised medical guidance."

    STYLE:
    - Friendly, knowledgeable, not robotic.
    - No long paragraphs. No grocery lists unless user asks.
    """

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7,
            max_tokens=700
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error generating response: {str(e)}"


# ---------- handle generate button & ask ----------
if st.session_state.get("generate_btn_input") is None:
    st.session_state["generate_btn_input"] = False

generate_btn = st.session_state.get("generate_btn_input", False)

if generate_btn:
    days = 7 if generate_weekly else 1
    payload = {
        "name": name, "age": age, "weight": weight, "height": height,
        "gender": gender, "activity": activity, "goal": goal,
        "diet_pref": diet_pref, "allergies": allergies, "dislikes": dislikes_food,
        "cuisine": cuisine, "time_per_meal": time_per_meal, "cooking_skill": cooking_skill
    }
    if calorie_target:
        payload["calorie_target"] = calorie_target
    frequency_choice = freq_map.get(freq_variety, "prefer_new_daily")
    try:
        plan = build_and_store_plan(days, payload, frequency_choice)
        blurb = make_personalized_blurb(payload, plan)
        st.session_state["assistant_reply"] = blurb
    except Exception as e:
        st.session_state["assistant_reply"] = "Failed to generate plan: " + str(e)

if ask_button and ask_input.strip():
    try:
        # 1) Detect intent
        intent, meta = parse_message_intent(ask_input)
        st.session_state["last_intent"] = intent

        # 2) Build payload for context
        payload = {
            "name": name,
            "age": age,
            "weight": weight,
            "height": height,
            "gender": gender,
            "activity": activity,
            "goal": goal,
            "diet_pref": diet_pref,
            "allergies": allergies,
            "dislikes": dislikes_food,
            "cuisine": cuisine,
        }

        # 3) Rule-based intents
        RULE_BASED = [
            "urgent",
            "pregnancy",
            "allergic_reaction",
            "ate",
        ]

        if intent in RULE_BASED:
            st.session_state["assistant_reply"] = free_chat_response(
                intent, meta, ask_input, payload
            )

        # 4) Generate plan
        elif intent == "generate_plan":
            days = 7 if ("7" in ask_input or "weekly" in ask_input or generate_weekly) else 1
            plan = build_and_store_plan(
                days,
                payload,
                freq_map.get(freq_variety, "prefer_new_daily")
            )
            st.session_state["assistant_reply"] = make_personalized_blurb(payload, plan)

        # 5) EVERYTHING ELSE → Groq (normal chatbot mode)
        else:
            st.session_state["assistant_reply"] = free_chat_response_groq(
                ask_input, payload
            )

    except Exception as e:
        st.session_state["assistant_reply"] = (
            "Sorry — couldn't process that: " + str(e)
        )

# ---------- render main UI ----------
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown('<h1>🍃🥗 AI Nutrition Assistant</h1>', unsafe_allow_html=True)
    st.markdown("---")

    plan = st.session_state.get("plan", {})
    if plan:
        daily_cal = plan.get("daily_calories_estimate", "—")
        st.markdown(f"**Why this plan?** This plan provides a balanced mix of macronutrients and ~{daily_cal} kcal/day tailored to your goal.")
        st.markdown(f"For your inputs — age **{age}**, weight **{weight} kg** — this plan is designed to support energy needs.")
        st.markdown("---")

        meals = plan.get("meals", {})
        # render only dish name and calories (no recipe details)
        if any(k.startswith("day_") for k in meals.keys()):
            for day_key in sorted(meals.keys()):
                with st.expander(day_key.replace("_", " ").title(), expanded=False):
                    day_meals = meals[day_key]
                    for meal_name in ("breakfast", "lunch", "dinner", "snacks"):
                        items = day_meals.get(meal_name, []) or []
                        if not items:
                            continue
                        st.markdown(f"### {meal_name.title()}")
                        for dish in items:
                            name_display = dish.get("name")
                            kcal_display = dish.get("calories", "?")
                            tmin = dish.get("estimated_time_min", "?")
                            skill = dish.get("skill_level", "")
                            st.markdown(f'<div class="recipe-card">{name_display} — {kcal_display} kcal </div>', unsafe_allow_html=True)
        else:
            for meal_name in ("breakfast", "lunch", "dinner", "snacks"):
                items = meals.get(meal_name, []) or []
                if not items:
                    continue
                st.markdown(f'<div class="meal-heading"><h3 style="display:inline">{meal_name.title()}</h3></div>', unsafe_allow_html=True)
                for dish in items:
                    name_display = dish.get("name")
                    kcal_display = dish.get("calories", "?")
                    tmin = dish.get("estimated_time_min", "?")
                    skill = dish.get("skill_level", "")
                    st.markdown(f'<div class="recipe-card">{name_display} — {kcal_display} kcal </div>', unsafe_allow_html=True)

        base_counts = plan.get("base_counts", {})
        rice_count = base_counts.get("rice", 0) + base_counts.get("steamed rice", 0)
        roti_count = base_counts.get("phulka", 0) + base_counts.get("roti", 0)
        noodles_count = base_counts.get("noodles", 0)
        if rice_count + roti_count + noodles_count > 10:
            st.warning("This week has many rice/roti/noodle-based meals — change cuisine for more variety or use chatbox to suggest something different.")

        try:
            pdf_bytes = generate_pdf_bytes(plan, {"name": name, "age": age, "goal": goal})
            st.download_button("Download plan (PDF)", data=pdf_bytes, file_name="meal_plan.pdf", mime="application/pdf")
        except Exception:
            st.download_button("Download plan (JSON)", data=json.dumps(plan, indent=2), file_name="meal_plan.json", mime="application/json")
    else:
        st.info("No plan generated yet. Use the sidebar 'Generate Meal Plan (sidebar)' or ask in the sidebar (e.g. 'give meal plan' or '7-day plan').")

    st.markdown("---")
    reply = st.session_state.get("assistant_reply", "")
    if reply:
        st.markdown('<div class="assistant-box">', unsafe_allow_html=True)
        st.markdown("**Assistant suggestion / Summary:**")
        st.markdown(reply)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    # Grocery list UI removed by request — we keep a short features box instead
    st.header("📊Notes & Features")
    st.markdown("- Chat-box (sidebar)\n- 1-day & 7-day plan\n- Printable PDF\n")
    st.markdown("</div>", unsafe_allow_html=True)
