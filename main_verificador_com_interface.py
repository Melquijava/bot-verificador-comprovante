import os
import discord
import pytesseract
import re
import uuid

from PIL.ExifTags import TAGS
from PIL import Image
from discord.ext import commands
from dotenv import load_dotenv
from pdf2image import convert_from_path

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

# Garante que as pastas existem
os.makedirs("images", exist_ok=True)
os.makedirs("pdf_temp", exist_ok=True)

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
        await canal.send(f"{user.mention} Envie seu comprovante de pagamento (PDF ou imagem, sem prints).")
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
                    texto = pytesseract.image_to_string(img, lang="por")
                os.remove(path)

            elif filename.endswith(".pdf"):
                path = f"pdf_temp/{uid}_{filename}"
                await attachment.save(path)
                texto = ""

                try:
                    imagens = convert_from_path(path)  # Sem o poppler_path para funcionar no Railway
                    for i, img in enumerate(imagens):
                        temp_img = f"pdf_temp/{uid}_{i}.png"
                        img.save(temp_img, "PNG")
                        texto += pytesseract.image_to_string(Image.open(temp_img), lang="por")
                        os.remove(temp_img)
                except Exception as e:
                    await message.reply(f"❌ Erro ao processar PDF: {e}", delete_after=15)
                    os.remove(path)
                    return

                os.remove(path)

            else:
                await message.reply("⚠️ Formato não suportado. Envie uma imagem (.png, .jpg) ou PDF.", delete_after=10)
                return

            # DEBUG TEMPORÁRIO
            print("🧾 TEXTO EXTRAÍDO DO COMPROVANTE:")
            print(texto)

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
                await message.reply("❌ Valor não corresponde ao plano vitalício. Verifique o comprovante.", delete_after=15)
            else:
                await message.reply("❌ Não consegui identificar o valor no comprovante. Envie um comprovante legível.", delete_after=15)

bot.run(TOKEN)