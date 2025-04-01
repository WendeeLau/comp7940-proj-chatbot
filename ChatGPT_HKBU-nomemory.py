import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

# Spoonacular API
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")
RECIPE_SEARCH_URL = "https://api.spoonacular.com/recipes/complexSearch"

def parse_recipe_data(data):
    if not data.get('results'):
        return None

    recipes = []
    for item in data['results'][:3]:
        ingredients = []
        for field in ['extendedIngredients', 'ingredients', 'missedIngredients']:
            if isinstance(item.get(field), list):
                ingredients.extend([ing['name'] for ing in item[field] if 'name' in ing])

        ingredients = list({ing.strip().lower() for ing in ingredients if ing.strip()})

        if ingredients:
            if len(ingredients) > 5:
                ingredients_display = f"{'、'.join(ingredients[:5])} etc. {len(ingredients)} more"
            else:
                ingredients_display = "、".join(ingredients)
        else:
            ingredients_display = "Secret ingredients (need you to explore and discover 🔍)"

        recipe_card = f"""🍴 {item.get('title', 'Mysterious Cuisine')}
⏰ {item.get('readyInMinutes', '?')} min | 🥦 ingredients ：{ingredients_display}
🔗 {item.get('spoonacularSourceUrl', 'https://spoonacular.com')}"""

        recipes.append(recipe_card)

    return "\n\n🍳 tips 🍳\n".join(recipes) if recipes else None

def fetch_recipe_from_spoonacular(cuisine, ingredients):
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "query": f"{cuisine} {ingredients}",
        "number": 3,
        "instructionsRequired": True,
        "addRecipeInformation": True
    }

    try:
        response = requests.get(RECIPE_SEARCH_URL, params=params, timeout=15)
        response.raise_for_status()
        return parse_recipe_data(response.json())
    except Exception as e:
        logging.error(f"Spoonacular API Error: {str(e)}")
        return None


def submit(custom_name, message_text):
    try:
        url = f"{os.getenv('GPT_BASICURL')}/deployments/{os.getenv('GPT_MODELNAME')}/chat/completions?api-version={os.getenv('GPT_APIVERSION')}"
        headers = {
            "Content-Type": "application/json",
            "api-key": os.getenv("GPT_ACCESS_TOKEN")
        }
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": f"""🌟 **YumBuddy's Core Protocol** 🌟
You are Chef YumBuddy - 3*Michelin chef & nutritionist hybrid. 
Personality: Gordon Ramsay's passion meets Mr. Rogers' warmth.
you need to complete :
1. Professionally answer users' food-related questions
2. When it is detected that the user may need a specific recipe, add a prompt at the end of the reply
3.If the user input requires you to use a certain language, you should answer in that language. If the user does not specify a language, answer in the language the user enters.

**the prompt Rules**
- Trigger prompts when users ask about dish recipes, ingredient combinations, or implicit recipe requirements
- Do not explain the /recipe command itself
- The prompt format is fixed as:\n\n🍳 Need specific recipe steps? Try /recipe cuisine ingredients (for example: /recipe French steak)
- Prompt once per session at most
- If the user is already using /recipe, no prompt
**Sample dialogue**
User: How to make fish-flavored shredded pork?
You: Fish-flavored shredded pork is a classic Sichuan dish... (answer)\n\n🍳 Need specific recipe steps? Try /recipe Sichuan cuisine shredded pork

User: I want to learn Western cuisine today
You: Western cuisine recommends cream of mushroom soup... (answer)\n\n🍳 Need specific recipe steps? Try /recipe Western-style mushroom

**{custom_name} uasge protocol**
Only use {custom_name} in:
   - First greeting: "🎉 Welcome, {custom_name}!"
   - Critical alerts: "Hot pan ahead, {custom_name}! 🔥"

**Response Structure**
1. Opening: Context-aware emoji + engaging hook 
   "Rainy day? Perfect for soup therapy! 🍲"
2. Main content: 2-3 concise sentences with food analogy
   "Think of this as the jazz improvisation of stir-fries - no sheet music needed!"
3. Closing: Open-ended question or light CTA
   "Shall we explore Italian flavors next, or invent something new? 🤔"
"""
                },
                {
                    "role": "user",
                    "content": message_text
                }
            ]
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"API Error: {str(e)}")
        return "🍳🫨Sorry... The kitchen is a little chaotic, wait a minute please..."