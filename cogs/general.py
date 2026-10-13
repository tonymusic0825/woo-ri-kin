import discord
from discord import app_commands
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="핑", description="봇 생존신고")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("살아있습니다!")

async def setup(bot):
    await bot.add_cog(General(bot))