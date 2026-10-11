import os

import discord
from discord import app_commands
from dotenv import load_dotenv

# Load secrets from the .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")


class WarframeBot(discord.Client):
    def __init__(self):
        # Default intents are all we need for slash commands
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        # The command tree holds all of our slash commands
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Runs once at startup: register (sync) slash commands with Discord.
        # Syncing to one server is instant; syncing globally can take a while.
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        print(f"Synced {len(synced)} command(s)")


bot = WarframeBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {latency_ms}ms")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Check your .env file.")
    bot.run(TOKEN)