import os
import pytesseract
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import File
from pdf2image import convert_from_path
from PIL import Image
import re
import uuid

# Configurações iniciais
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Caminho Tesseract
os.environ["TESSDATA_PREFIX"] = os.path.join(os.getcwd(), "tessdata")
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\melqu\OneDrive\Desktop\pix_verificador_bot\tesseract.exe"

# Caminho Poppler
poppler_path = r"./poppler/Library/bin"

# Canal permitido
ALLOWED_CHANNEL_ID = 1369159901582200842

# Cargos disponíveis
CARGOS = {
    "27,90": "Acesso Mensal",
    "95,90": "Acesso Vitalicio"
}

# Regex para capturar valor no texto
VALOR_REGEX = r"R\$\s?([0-9]+,[0-9]{2})"

# Bot com permissões adequadas
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # ⛔ Ignora mensagens fora do canal permitido
    if message.channel.id != ALLOWED_CHANNEL_ID:
        return

    if message.attachments:
        for attachment in message.attachments:
            filename = attachment.filename.lower()
            uid = str(uuid.uuid4())

            # PROCESSA IMAGEM
            if filename.endswith((".png", ".jpg", ".jpeg")):
                path = f"images/{uid}_{filename}"
                await attachment.save(path)
                texto_extraido = pytesseract.image_to_string(Image.open(path), lang="por")
                os.remove(path)

            # PROCESSA PDF
            elif filename.endswith(".pdf"):
                path = f"pdf_temp/{uid}_{filename}"
                await attachment.save(path)
                imagens = convert_from_path(path, poppler_path=poppler_path)
                texto_extraido = ""
                for i, img in enumerate(imagens):
                    temp_img_path = f"pdf_temp/{uid}_page_{i}.png"
                    img.save(temp_img_path, "PNG")
                    texto_extraido += pytesseract.image_to_string(Image.open(temp_img_path), lang="por")
                    os.remove(temp_img_path)
                os.remove(path)

            else:
                await message.reply("⚠️ Formato não suportado. Envie uma imagem (.png, .jpg) ou PDF.", delete_after=10)
                return

            # VERIFICA VALOR
            encontrados = re.findall(VALOR_REGEX, texto_extraido)
            if encontrados:
                for valor in encontrados:
                    valor = valor.replace(" ", "")
                    if valor in CARGOS:
                        cargo_nome = CARGOS[valor]
                        cargo = discord.utils.get(message.guild.roles, name=cargo_nome)
                        if cargo:
                            await message.author.add_roles(cargo)
                            await message.reply(f"✅ Comprovante verificado! Cargo **{cargo_nome}** atribuído com sucesso.", delete_after=15)
                        else:
                            await message.reply(f"⚠️ Cargo **{cargo_nome}** não foi encontrado no servidor.", delete_after=15)
                        return
                await message.reply("❌ Valor não corresponde a nenhum plano. Verifique o comprovante.", delete_after=15)
            else:
                await message.reply("❌ Não consegui identificar o valor no comprovante. Envie um comprovante legível.", delete_after=15)

bot.run(TOKEN)
