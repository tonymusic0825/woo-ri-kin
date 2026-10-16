import os

import discord
from discord import app_commands
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime, timezone

# Load secrets from the .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
TEST_GUILD = discord.Object(id=GUILD_ID)

class Woorikin(commands.Bot):

    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    async def setup_hook(self):
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.links")
        await self.load_extension("cogs.warframe_stat")
        await self.load_extension("cogs.global_pings")
        await self.load_extension("cogs.baro")
        self.tree.copy_global_to(guild=TEST_GUILD)
        await self.tree.sync(guild=TEST_GUILD)

    async def on_message(self, message):
        print(f"Message from {message.author}: {message.content}")

# Run bot 
client = Woorikin()
client.run(TOKEN)
