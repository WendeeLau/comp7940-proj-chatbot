import os
import redis
import json
import requests
import logging
from datetime import datetime, timedelta, timezone, tzinfo
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Redis config
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    #password=os.getenv("REDIS_PASSWORD", "Comp7940_"),
    db=0,
    decode_responses=True,
    #socket_connect_timeout=5
)

# MongoDB used for session logs record
mongo_client = MongoClient(os.getenv("MONGODB_URI"))
mongo_db = mongo_client["chatbot_mongodb"]
chatlog_collection = mongo_db["chat_logs"]

# para for length and time
MAX_HISTORY_LENGTH = 10
CONTEXT_TIMEOUT_MINUTES = 10

def get_system_prompt(custom_name):
    return f"""🌟 **YumBuddy's Core Protocol** 🌟
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
#redis keys generate,list
def get_history_key(user_id):
    return f"chat_history:{user_id}"
#redis keys generate,string
def get_last_active_key(user_id):
    return f"last_active:{user_id}"

# Only check timeout when loading history,lazy mode hahahha
def load_history_from_redis(user_id, custom_name):
    # Automatic cleanup logic
    # Determine whether it has timed out,CONTEXT_TIMEOUT_MINUTES = 10
    #GET Key
    last_active = redis_client.get(get_last_active_key(user_id))
    if last_active:
        last_time = datetime.fromisoformat(last_active).replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_time > timedelta(minutes=CONTEXT_TIMEOUT_MINUTES):
            # Clear the context
            redis_client.delete(get_history_key(user_id))
    else:
        # initial timestamp(new user)
        redis_client.set(get_last_active_key(user_id), datetime.now(timezone.utc).isoformat())

    # loading history context
    key = get_history_key(user_id)
    #LRANGE for list type
    history = redis_client.lrange(key, 0, -1)
    messages = [json.loads(msg) for msg in history]
    return [{"role": "system", "content": get_system_prompt(custom_name)}] + messages

def save_message_to_redis(user_id, role, content):
    key = get_history_key(user_id)
    #Add the new message to the end of the list(json format)
    redis_client.rpush(key, json.dumps({"role": role, "content": content}))
    #Keep last MAX_HISTORY_LENGTH=10 records
    redis_client.ltrim(key, -MAX_HISTORY_LENGTH, -1)
    #Each save updates the last activity time to the current UTC time
    redis_client.set(get_last_active_key(user_id), datetime.now(timezone.utc).isoformat())
    # Automatic expiration policy: 1 hour
    #Each save will refresh the expiration time
    # 🤔As long as the user continues to interact, the history record will not expire
    redis_client.expire(key, 3600)
    redis_client.expire(get_last_active_key(user_id), 3600)

#Long-term storage，used for long-term needs such as auditing and analysis balabala...
def save_chatlog_mongo(user_id, custom_name, user_message, assistant_reply):
    chatlog_collection.insert_one({
        "user_id": user_id,
        "custom_name": custom_name,
        "user_message": user_message,
        "assistant_reply": assistant_reply,
        "timestamp": datetime.now(timezone.utc)
    })

def submit(custom_name, message_text, user_id):
    try:
        # loading history
        history = load_history_from_redis(user_id, custom_name)
        history.append({"role": "user", "content": message_text})

        # call chatgpt
        url = f"{os.getenv('GPT_BASICURL')}/deployments/{os.getenv('GPT_MODELNAME')}/chat/completions?api-version={os.getenv('GPT_APIVERSION')}"
        headers = {"Content-Type": "application/json", "api-key": os.getenv("GPT_ACCESS_TOKEN")}

        response = requests.post(url, json={"messages": history}, headers=headers, timeout=15)
        response.raise_for_status()

        assistant_reply = response.json()['choices'][0]['message']['content']

        # saved in redis
        save_message_to_redis(user_id, "user", message_text)
        save_message_to_redis(user_id, "assistant", assistant_reply)

        # saved in mongodb
        save_chatlog_mongo(user_id, custom_name, message_text, assistant_reply)

        return assistant_reply
    except Exception as e:
        logging.error(f"ChatGPT API Error: {str(e)}")
        return "🫨Oops! Kitchen chaos... please wait a moment."

# Recipe API :SPOONACULAR
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
        ingredients_display = "、".join(ingredients[:5]) + (" more" if len(ingredients) > 5 else "")
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