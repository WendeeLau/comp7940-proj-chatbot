# comp7940-proj-chatbot

# 🍴🤖🤗 YumBuddy Chatbot  
**Your Foodie Companion on Telegram**  
Chat about any food topic, discover recipes, and get cooking inspiration! Powered by ChatGPT (HKBU API) and Spoonacular API.

**ChatBot ID**: `@Yum_Bitebot`  
**Direct Link**: https://t.me/Yum_Bitebot  

## 🚀 Features  
• Food-themed conversations & recipe suggestions  
• Dietary preference support (vegetarian, keto, etc.)  
• Step-by-step cooking instructions  
• Ingredient substitution ideas  

## ⚙️ Deployment Options

### 1️⃣ Render Cloud Deployment  
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)  
1. Use provided `render.yaml`  
2. Set environment secrets:  
   • `TELEGRAM_TOKEN`  
   • `CHATGPT_API_KEY`  
   • `SPOONACULAR_API_KEY`  
3. Deploy!  

### 2️⃣ Local Docker Deployment  
```bash
# 1. Install Docker
# 2. Prepare environment
cp .env.example .env  # Fill your API keys
# 3. Start containers (includes Redis)
docker-compose -f chatbot-compose.yaml up -d --build
```

## 🤖 Auto-Deployment  
This repo uses GitHub Actions to:  
1. Auto-deploy to Render on `main` branch push  
2. Build Docker image to Docker Hub  
3. Send deployment status to monitoring chatbot  

**Requirements**:  
• Set GitHub Secrets:  
  `RENDER_API_KEY`, `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`  

## 📋 Environment Variables  
```env
TELEGRAM_TOKEN=your_bot_token
CHATGPT_API_KEY=hkbu_provided_key
SPOONACULAR_API_KEY=spoonacular_key
REDIS_URL=redis://redis:6379
```

## 🤝 Contributing  
1. Fork the repository  
2. Create feature branch: `git checkout -b feat/your-idea`  
3. Follow PEP8 style guide  
4. Submit PR with tests and documentation updates  

## 🌟 Acknowledgments  
• HKBU for ChatGPT API access  
• Spoonacular for recipe data  
• Telegram Bot Platform  
• render
• redis
• mongodb atlas


**Note for Developers**: Remember to set your own API keys in environment variables/secrets before deployment!
