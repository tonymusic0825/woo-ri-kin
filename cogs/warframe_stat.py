from datetime import datetime, timezone
import discord 
from discord import app_commands
from discord.ext import commands
from services import warframestat
from utils.formatting import discord_time, is_expired
import json

RELIC_TIER = ["Lith", "Meso", "Neo", "Axi", "Requiem", "Omnia"]

class Warframestat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="균열", description="현재 활성화된 보이드 균열")
    async def fissures(self, interaction: discord.Interaction):
        await interaction.response.defer() 
        try:
            data = await warframestat.get_fissures()
        except Exception as e:
            print(f"Fissure fetch failed {e}")
            await interaction.followup.send("균열 정보를 가져오지 못했습니다...")
            return

        # Success
        normal = []
        hard = []
        print(f"API returned {len(data)} fissures")
        for f in data:
            print(f["expiry"], f["isHard"], "expired =", is_expired(f["expiry"]))
            if is_expired(f["expiry"]):
                continue
            (hard if f["isHard"] else normal).append(f)


        normal.sort(key=lambda f: f["tierNum"])
        hard.sort(key=lambda f: f["tierNum"])
        # print("\n===========Normal===========\n")
        # print(normal)
        # print("\n===========Hard===========\n")
        # print(hard)

        # Formatting
        embed = discord.Embed(
            title="🌌 활성화된 보이드 균열 현황", 
            description="현재 우주에서 진행 중인 실시간 균열 목록입니다.",
            color=discord.Color.yellow()
        )

        # 1. Normal Fissures
        if normal:
            normal_lines = [
                f"• **{f['tier']}** | `{f['missionType']}` ({f['node']}) — {discord_time(f['expiry'])}"
                for f in normal
            ]
            embed.add_field(name="✨ 일반 균열", value="\n".join(normal_lines), inline=False)

        # 2. Steel Path Fissures Field
        if hard:
            hard_lines = [
                f"• **{f['tier']}** | `{f['missionType']}` ({f['node']}) — {discord_time(f['expiry'])}"
                for f in hard
            ]
            embed.add_field(name="💀 강철의 길 (Steel Path)", value="\n".join(hard_lines), inline=False)

        if not normal and not hard:
            embed.description = "현재 활성화된 균열이 없습니다."

        embed.set_footer(text="Warframe Worldstate • 실시간 동기화")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Warframestat(bot))