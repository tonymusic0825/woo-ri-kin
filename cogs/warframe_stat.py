from datetime import datetime, timezone
import discord 
from discord import app_commands
from discord.ext import commands
from services import warframestat
from utils.formatting import discord_time, is_expired
from services import worldstate_raw

import json

RELIC_TIER = ["Lith", "Meso", "Neo", "Axi", "Requiem", "Omnia"]

class Warframestat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="균열", description="현재 활성화된 보이드 균열")
    async def fissures(self, interaction: discord.Interaction):
        await interaction.response.defer() 
        try:
            data = await worldstate_raw.get_fissures()
        except Exception as e:
            print(f"Fissure fetch failed {e}")
            await interaction.followup.send("균열 정보를 가져오지 못했습니다...")
            return

        # Success
        normal = []
        hard = []
        print(f"API returned {len(data)} fissures")
        for f in data:
            if is_expired(f["expiry"]) or f["isStorm"]:
                continue
            (hard if f["isHard"] else normal).append(f)


        normal.sort(key=lambda f: f["tierNum"])
        hard.sort(key=lambda f: f["tierNum"])
        # print("\n===========Normal===========\n")
        # print(normal)
        # print("\n===========Hard===========\n")
        # print(hard)

        embeds_list = []

        if normal:
            normal_embed = discord.Embed(
                title="✨ 일반 보이드 균열 현황", 
                color=discord.Color.blue()
            )
            normal_lines = [
                f"• **{f['tier']}** | `{f['missionType']}` ({f['node']}) — {discord_time(f['expiry'])}"
                for f in normal
            ]
            normal_embed.description = "\n".join(normal_lines)
            embeds_list.append(normal_embed)

        if hard:
            hard_embed = discord.Embed(
                title="💀 강철의 길 (Steel Path) 보이드 균열 현황", 
                color=discord.Color.red()
            )
            hard_lines = [
                f"• **{f['tier']}** | `{f['missionType']}` ({f['node']}) — {discord_time(f['expiry'])}"
                for f in hard
            ]
            hard_embed.description = "\n".join(hard_lines)
            embeds_list.append(hard_embed)

        if embeds_list:
            # Discord allows up to 10 embeds in a single message list
            await interaction.followup.send(embeds=embeds_list)
        else:
            await interaction.followup.send("현재 활성화된 균열이 없습니다.")

async def setup(bot):
    await bot.add_cog(Warframestat(bot))