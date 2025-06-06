import os
import discord
import re
import uuid
import json
import hashlib
import asyncio
import fitz  # PyMuPDF

from PIL.ExifTags import TAGS
from PIL import Image
from discord.ext import commands
from dotenv import load_dotenv

# === CONFIGURAÇÕES ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN não foi definido. Configure no Railway.")

CARGO_MAPEAMENTO = {
    "37,90": "Acesso Vitalício"
}
VALOR_REGEX = r"R\$\s?([0-9]+,[0-9]{2})"
CATEGORIA_NOME = "⇓━━━━━━━━  Atendimento ━━━━━━━━⇓"
CANAL_INICIAL = "📥│envio-comprovante"
ARQUIVO_HASH = "usados.json"

os.makedirs("images", exist_ok=True)
os.makedirs("pdf_temp", exist_ok=True)
if not os.path.exists(ARQUIVO_HASH):
    with open(ARQUIVO_HASH, "w") as f:
        json.dump({"hashes": []}, f)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def is_screenshot(path):
    try:
        image = Image.open(path)
        exif_data = image.getexif()
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "Software" and "screenshot" in str(value).lower():
                return True
        return False
    except Exception:
        return False

def validar_texto(texto):
    texto = texto.lower().replace("\n", " ").replace("  ", " ").strip()
    valor_ok = "r$ 37,90" in texto
    nomes_aceitos = [
        "leandro de deus chaves",
        "leandro  de  deus chaves",
        "leandro de  deus  chaves",
        "leandro chaves",
        "leandro d chaves",
        "leandro de d chaves"
    ]
    nome_ok = any(n in texto for n in nomes_aceitos) or ("leandro" in texto and "chaves" in texto)
    return valor_ok and nome_ok

def verificar_duplicado(texto):
    hash_texto = hashlib.sha256(texto.encode()).hexdigest()
    with open(ARQUIVO_HASH, "r") as f:
        dados = json.load(f)
    if hash_texto in dados["hashes"]:
        return True
    dados["hashes"].append(hash_texto)
    with open(ARQUIVO_HASH, "w") as f:
        json.dump(dados, f, indent=4)
    return False

def extrair_texto_pdf(path):
    texto = ""
    try:
        with fitz.open(path) as doc:
            for pagina in doc:
                texto += pagina.get_text()
    except Exception as e:
        print(f"Erro ao extrair texto PDF: {e}")
    return texto.lower()

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    canal = None
    for guild in bot.guilds:
        canal = discord.utils.get(guild.text_channels, name=CANAL_INICIAL)
        if canal:
            embed = discord.Embed(
                title="🧾 Verificação de Acesso",
                description="Escolha uma das opções abaixo:",
                color=discord.Color.dark_blue()
            )
            embed.set_image(url="https://i.imgur.com/J4xCUqe.png")

            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Verificar Comprovante", style=discord.ButtonStyle.primary, custom_id="verificar"))
            view.add_item(discord.ui.Button(label="Suporte", style=discord.ButtonStyle.secondary, custom_id="suporte"))

            await canal.send(embed=embed, view=view)
            break

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.type == discord.InteractionType.component:
        return

    custom_id = interaction.data["custom_id"]
    user = interaction.user
    guild = interaction.guild
    categoria = discord.utils.get(guild.categories, name=CATEGORIA_NOME)

    if not categoria:
        await interaction.response.send_message("❌ Categoria de atendimento não encontrada.", ephemeral=True)
        return

    nome = f"{'🔐│verificacao' if custom_id == 'verificar' else '❓│suporte'}-{user.name}".replace(" ", "-").lower()
    canal_existente = discord.utils.get(guild.text_channels, name=nome)

    if canal_existente:
        await interaction.response.send_message("⚠️ Você já possui um canal aberto.", ephemeral=True)
        return

    canal = await criar_canal_privado(guild, nome, user, categoria)

    if custom_id == "verificar":
        await canal.send(f"{user.mention} Envie seu comprovante de pagamento em PDF ou imagem original (sem prints), preferencialmente o arquivo gerado pelo aplicativo do banco.")
        await interaction.response.send_message("✅ Canal de verificação criado!", ephemeral=True)
    elif custom_id == "suporte":
        await canal.send(f"{user.mention} 👋 Como podemos te ajudar? Envie sua dúvida.")
        await interaction.response.send_message("✅ Canal de suporte criado!", ephemeral=True)

async def criar_canal_privado(guild, nome_canal, user, categoria):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }
    return await guild.create_text_channel(nome_canal, overwrites=overwrites, category=categoria)

@bot.event
async def on_message(message):
    if message.author == bot.user or message.channel.category is None:
        return

    if message.channel.category.name != CATEGORIA_NOME:
        return

    if message.attachments:
        await message.reply("🔎 Verificando seu comprovante, aguarde alguns segundos...", delete_after=5)
        await asyncio.sleep(5)

        for attachment in message.attachments:
            filename = attachment.filename.lower()
            uid = str(uuid.uuid4())

            if any(x in filename for x in ["screenshot", "print", "captura", "snippingtool"]):
                await message.reply("❌ Comprovante recusado. Capturas de tela não são aceitas.", delete_after=15)
                return

            if filename.endswith((".png", ".jpg", ".jpeg")):
                path = f"images/{uid}_{filename}"
                await attachment.save(path)
                with Image.open(path) as img:
                    width, height = img.size
                    if width <= 1920 and height <= 1080:
                        await message.reply("❌ Imagem parece ser um print. Envie o comprovante original (PDF ou imagem exportada).", delete_after=15)
                        os.remove(path)
                        return
                    texto = pytesseract.image_to_string(img)
                os.remove(path)

            elif filename.endswith(".pdf"):
                path = f"pdf_temp/{uid}_{filename}"
                await attachment.save(path)
                texto = extrair_texto_pdf(path)
                os.remove(path)

            else:
                await message.reply("⚠️ Formato não suportado. Envie uma imagem (.png, .jpg) ou PDF.", delete_after=10)
                return

            if not validar_texto(texto):
                await message.reply("❌ Comprovante inválido. Deve conter valor, nome e dados da transação.", delete_after=20)
                return

            if verificar_duplicado(texto):
                await message.reply("❌ Este comprovante já foi utilizado.", delete_after=20)
                return

            encontrados = re.findall(VALOR_REGEX, texto)
            if encontrados:
                for valor in encontrados:
                    valor = valor.replace(" ", "")
                    if valor in CARGO_MAPEAMENTO:
                        nome_cargo = CARGO_MAPEAMENTO[valor]
                        cargo = discord.utils.get(message.guild.roles, name=nome_cargo)
                        if cargo:
                            await message.author.add_roles(cargo)
                            await message.reply(f"✅ Comprovante verificado! Cargo **{nome_cargo}** atribuído.", delete_after=20)
                        else:
                            await message.reply(f"⚠️ Cargo **{nome_cargo}** não foi encontrado.", delete_after=20)
                        return
            await message.reply("❌ Não consegui identificar o valor no comprovante. Envie um comprovante legível.", delete_after=15)

bot.run(TOKEN)
