# pip install slack_sdk

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Carrega as variáveis do .env (override=True força atualização)
from dotenv import load_dotenv
import os

load_dotenv(override=True)

# Coloque seu token aqui
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

client = WebClient(token=SLACK_BOT_TOKEN)

try:
    response = client.chat_postMessage(
        channel="#social",  # ou ID do canal tipo C12345678
        text="🚀 Olá! Essa mensagem foi enviada via Python!",
    )

    print("Mensagem enviada com sucesso!")
    print("Timestamp:", response["ts"])

except SlackApiError as e:
    print("Erro ao enviar mensagem:")
    print(e.response["error"])
