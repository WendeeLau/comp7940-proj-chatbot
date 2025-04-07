import os
import logging
from flask import Flask, request
import time
from pymongo import MongoClient
from telegram import Update, BotCommand, ReplyKeyboardRemove,Bot
from telegram.ext import (
    Dispatcher, CommandHandler, MessageHandler,
    Filters, ConversationHandler, CallbackContext
)
from dotenv import load_dotenv
import ChatGPT_HKBU
from concurrent.futures import ThreadPoolExecutor




# Load environment variables
load_dotenv()

# MongoDB
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["chatbot_mongodb"]
users_collection = db["users"]

# Telegram setup
bot = Bot(token=os.getenv("TLG_ACCESS_TOKEN"))
# TOKEN = os.getenv("TLG_ACCESS_TOKEN")
# bot = ChatGPT_HKBU.bot if hasattr(ChatGPT_HKBU, "bot") else None
# if not bot:
#
#     bot = Bot(token=TOKEN)

# Flask app
app = Flask(__name__)

executor = ThreadPoolExecutor(max_workers=5)

# State
ASKING_NAME = 1

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Dispatcher
dispatcher = Dispatcher(bot=bot, update_queue=None, use_context=True)

# Handlers

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = users_collection.find_one({"user_id": user.id})

    if not user_data:
        update.message.reply_text("😊 Hi! I'm your food assistant YumBuddy. What should I call you?")
        return ASKING_NAME
    else:
        custom_name = user_data.get("custom_name", user.first_name)
        update.message.reply_text(
            f"🤗 Welcome back, {custom_name}! I'm your food assistant YumBuddy. Use /update_name to change how I address you."
        )
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

    update.message.reply_text(f"💾 Saved! I'll call you {custom_name}. Start chatting now!")
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
            response = f"found {len(recipes.split('🥢'))} recipes：\n\n{recipes}"
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
    gpt_response = ChatGPT_HKBU.submit(custom_name, update.message.text, user.id)
    update.message.reply_text(gpt_response)

def cancel_cmd(update: Update, context: CallbackContext):
    update.message.reply_text("Operation Cancelled", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

def setup_commands():
    commands = [
        BotCommand("start", "start the chatbot"),
        BotCommand("update_name", "update your name"),
        BotCommand("recipe", "search a recipe"),
        BotCommand("cancel", "cancel a command")
    ]
    bot.set_my_commands(commands)

# Conversation Handler
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

# Register Handlers
dispatcher.add_handler(conv_handler)
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
setup_commands()


# for render healthcheck
@app.route(f"/healthcheck",methods=["GET", "HEAD"])
def healthcheck():
    return "OK", 200

# Webhook endpoint
@app.route(f"/", methods=["POST"])
def webhook():
    # update = Update.de_json(request.get_json(force=True), bot)
    # dispatcher.process_update(update)
    # return "ok", 200
    try:
        json_data = request.get_json()
        logging.info(f"📩 收到消息: {json_data}")

        # 提交到异步线程池处理
        executor.submit(process_message_async, json_data)

        # 立即返回响应避免超时
        return "ok", 200

    except Exception as e:
        logging.error(f"❌ 请求解析失败: {str(e)}")
        return "error", 500


def process_message_async(json_data):
    try:
        update = Update.de_json(json_data, bot)
        # 手动创建上下文
        context = CallbackContext.from_update(update, dispatcher)
        dispatcher.process_update(update, context)
    except Exception as e:
        logging.error(f"❌ 异步处理失败: {str(e)}")


# Set Webhook on startup
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # set  webhook
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/"
    #webhook_url = f"https://8806-119-236-243-192.ngrok-free.app/"#local test ngrok
    for retry in range(3):
        try:
            bot.delete_webhook()
            bot.set_webhook(
                url=webhook_url,
                connect_timeout=10,
                read_timeout=30
            )
            logging.info(f"✅ Webhook 配置成功: {webhook_url}")
            break
        except Exception as e:
            logging.error(f"❌ Webhook 配置失败（第 {retry + 1} 次重试）: {str(e)}")
            time.sleep(5)


    app.run(host="0.0.0.0", port=port)


    # bot.delete_webhook()
    # bot.set_webhook(url=webhook_url)
    # logging.info(f"✅ Webhook set to: {webhook_url}")
    #
    # # start Flask
    # app.run(host="0.0.0.0", port=port)



