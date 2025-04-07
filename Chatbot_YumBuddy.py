import os
import logging
from pymongo import MongoClient
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove,Update, BotCommand
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, Dispatcher
from dotenv import load_dotenv
import ChatGPT_HKBU


load_dotenv()

# MongoDB conn
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["chatbot_mongodb"]
users_collection = db["users"]

# session state
ASKING_NAME = 1

# logs config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
        update.message.reply_text("😊 Hi! I'm your food assistant YumBuddy. What should I call you?")
        return ASKING_NAME
    else:
        custom_name = user_data.get("custom_name", user.first_name)
        update.message.reply_text(
            f"🤗 Welcome back, {custom_name}! I'm your food assistant YumBuddy.Use /update_name to change how I address you.")
        return ConversationHandler.END

def ask_name(update: Update, context: CallbackContext):
    user = update.effective_user
    custom_name = update.message.text.strip()

    users_collection.update_one(
        {"user_id": user.id},
        {
            "$set": {
                "user_id": user.id,
                "chat_id": update.effective_chat.id,
                "custom_name": custom_name,
                "first_name": user.first_name,
            }
        },
        upsert=True
    )

    #reply_markup = ReplyKeyboardMarkup(KEYBOARD_LAYOUT, resize_keyboard=True)
    update.message.reply_text(
        f"💾 Saved! I'll call you {custom_name}. Start chatting now!")
    return ConversationHandler.END

def update_name(update: Update, context: CallbackContext):
    update.message.reply_text("⌨️ Please enter your new name:")
    return ASKING_NAME

def recipe_command(update: Update, context: CallbackContext):
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text("🥘 Please specify the cuisine and ingredients, e.g. /recipe Chinese Chicken")
            return

        cuisine, ingredients = args[0], ' '.join(args[1:])
        update.message.reply_text(f"🔍 searching {cuisine} style {ingredients} recipe......")

        recipes = ChatGPT_HKBU.fetch_recipe_from_spoonacular(cuisine, ingredients)
        if recipes:
            response = f"found{len(recipes.split('🥢'))}recipes：\n\n{recipes}"
        else:
            response = "⚠️ No matching recipes found, try another combination? Available formats: /recipe Cuisine Ingredients"

        update.message.reply_text(response)

    except Exception as e:
        logging.error(f"Recipe cmd error: {str(e)}")
        update.message.reply_text("There was a little accident in the kitchen, please try again later🔥")

def handle_message(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
        update.message.reply_text("⚠️ Please /start to begin first.")
        return

    custom_name = user_data.get("custom_name", user.first_name)
    gpt_response = ChatGPT_HKBU.submit(custom_name, update.message.text,user.id)
    update.message.reply_text(gpt_response)



KEYBOARD_LAYOUT = [
    ["/start"],
    ["/update_name"],
    ["/recipe"],
    ["/cancel"]
]

def setup_commands(dp: Dispatcher) :
    commands = [
        BotCommand("start", "start the chatbot"),
        BotCommand("update_name", "update your name"),
        BotCommand("recipe", "search a recipe"),
        BotCommand("cancel", "cancle a command")
    ]
    dp.bot.set_my_commands(commands)

def cancel_cmd(update, context):
    # Sends a confirmation message and removes a possible temporary keyboard
    update.message.reply_text(
        "Operation Cancelled",
        reply_markup= ReplyKeyboardRemove()  # If there is a temporary keyboard, remove it
    )
    # clear user data
    context.user_data.clear()
    # stop session
    return ConversationHandler.END




def main():
    updater = Updater(os.getenv("TLG_ACCESS_TOKEN"))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('update_name', update_name),
            CommandHandler('recipe', recipe_command)
        ],
        states={
            ASKING_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_name)],
        },
        fallbacks=[CommandHandler('cancel', cancel_cmd)]
    )

    updater.dispatcher.add_handler(conv_handler)
    updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    setup_commands(updater.dispatcher)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()