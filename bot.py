import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import database

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class AsistenciaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await database.init_db()
        await self.load_extension("cogs.miembros")
        await self.load_extension("cogs.alertas")
        synced = await self.tree.sync()
        print(f"Sincronizados {len(synced)} comandos slash")

    async def on_ready(self):
        print(f"Bot conectado: {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="las asistencias del clan",
            )
        )


bot = AsistenciaBot()
bot.run(TOKEN)
