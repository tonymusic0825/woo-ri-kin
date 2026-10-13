import discord
from discord import app_commands
from discord.ext import commands, tasks
from services import warframestat
from utils.formatting import discord_time, is_expired
from utils.utils import GoodFissures, get_fissure_thumbnail
from tests.fake_fissures import FAKE_FISSURES
from services import worldstate_raw
import os

EVERYONE = discord.AllowedMentions(everyone=True)
ANNOUNCE_CHANNEL_ID = 1559469960630243349
TEST_MODE = False  # True = no @everyone ping. Set to False when you're done testing.

RELIC_TIER = ["Lith", "Meso", "Neo", "Axi", "Requiem", "Omnia"]

GOOD_FISSURES = GoodFissures()

class Globalping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announced_fissures = set()
        self.announced_baro = None

    async def cog_load(self):
        self.check_worldstate.start()

    async def cog_unload(self):
        self.check_worldstate.cancel()

    @tasks.loop(minutes=1)
    async def check_worldstate(self):
        print("Checking if there are good fissures")
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            print("Announcement channel not found. Check ANNOUNCE_CHANNEL_ID.")
            return
        try:
            await self.check_fissures(channel)
        except Exception as e:
            print(f"Worldstate check crashed: {e}")

    @check_worldstate.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # -------------------------- TESTING --------------------------
    @app_commands.command(name="testfissures", description="Run the fissure check on fake data (testing)")
    @app_commands.default_permissions(administrator=True)
    async def test_fissures(self, interaction: discord.Interaction):
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message("Announcement channel not found. Check ANNOUNCE_CHANNEL_ID.", ephemeral=True)
            return

        await interaction.response.send_message(f"Posting fake fissures to {channel.mention}...", ephemeral=True)
        await self.check_fissures(channel, fissures=FAKE_FISSURES, announced=set())

    # -------------------------- FISSURES --------------------------
    async def check_fissures(self, channel, fissures=None, announced=None):
        if announced is None:
            announced = self.announced_fissures

        if fissures is None:
            try:
                fissures = await worldstate_raw.get_fissures()
            except Exception as e:
                print(f"Fissure check failed: {e}")
                return

        # Forget fissures that no longer exist
        current_ids = {f["id"] for f in fissures}
        announced &= current_ids

        for f in fissures:
            if is_expired(f["expiry"]) or f["id"] in announced:
                continue

            if not GOOD_FISSURES.is_good(f["isHard"], f["nodeKey"], f["missionTypeKey"]):
                continue

            try:
                await self.send_fissure(channel, f)
                announced.add(f["id"])
            except Exception as e:
                print(f"Failed to announce fissure {f['id']}: {e}")

    async def send_fissure(self, channel, f):
        kind = "Steel Path" if f["isHard"] else "Normal"

        node, planet = GOOD_FISSURES.parse_nodekey(f["nodeKey"])

        embed = discord.Embed(
            title=f"{node} Fissure ({kind})",
            description=(
                f"**Planet:** {planet}\n"
                f"**Mission Type:** {f['missionType']}\n"
                f"**Fissure Type:** {f['tier']}\n"
                f"**Expires:** {discord_time(f['expiry'])}"
            ),
            color=discord.Color.orange(),
        )

        files = []
        tier = f["tier"].lower()
        mission = f["missionTypeKey"]
        path = f"assets/{get_fissure_thumbnail(mission, planet, tier)}.png"

        if os.path.exists(path):
            filename = os.path.basename(path).replace(" ", "_")  # "omnia.png"
            files.append(discord.File(path, filename=filename))
            embed.set_thumbnail(url=f"attachment://{filename}")
        else:
            print(f"Thumbnail not found: {path}")

        await channel.send(content="@everyone", embed=embed, files=files, allowed_mentions=EVERYONE)

async def setup(bot):
    await bot.add_cog(Globalping(bot))