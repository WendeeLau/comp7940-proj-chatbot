FROM python:3.12
LABEL org.opencontainers.image.authors="WendeeLau"
LABEL org.opencontainers.image.description="This is the backend of the chatbot for comp7940."
WORKDIR /comp7940-proj-chatbot
COPY requirements.txt .
COPY Chatbot_YumBuddy.py ChatGPT_HKBU.py .
RUN pip install update
RUN pip install -r requirements.txt

CMD ["python", "Chatbot_YumBuddy.py"]
