from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services import warframestat

BARO_CHANNEL_ID = 1560292325278617690  # put your Baro channel ID here
EVERYONE = discord.AllowedMentions(everyone=True)
NO_PING = discord.AllowedMentions.none()

BARO_COLOR = discord.Color.from_rgb(32, 178, 170)  # Baro teal
DESC_LIMIT = 4000  # one embed description can hold 4096 chars; leave a little room


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def split_into_chunks(lines, limit):
    """Group lines into strings that each stay under `limit` characters."""
    chunks = []
    current = ""
    for line in lines:
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    return chunks


def build_baro_embeds(baro):
    expiry = parse_time(baro["expiry"])
    inventory = baro["inventory"]

    # Header info goes at the top of the first embed
    lines = [
        f"📍 **위치:** {baro['location']}",
        f"⏳ **떠나는 시간:** {discord.utils.format_dt(expiry, 'F')} ({discord.utils.format_dt(expiry, 'R')})",
        f"📦 **아이템 수:** {len(inventory)}",
        "",
    ]

    # One entry per item
    for item in inventory:
        lines.append(f"**{item['item']}**")
        lines.append(f"└ {item['ducats']} 듀캇 · {item['credits']:,} 크레딧")

    # Split the text into embed-sized pieces
    embeds = []
    for i, chunk in enumerate(split_into_chunks(lines, DESC_LIMIT)):
        embed = discord.Embed(description=chunk, color=BARO_COLOR)
        if i == 0:
            embed.title = "💰 바로 키티어 (Baro Ki'Teer) 도착!"
        embeds.append(embed)

    # Footer only on the last embed so the stack reads as one card
    embeds[-1].set_footer(text="떠나는 시간")
    embeds[-1].timestamp = expiry

    return embeds


def fake_baro(item_count):
    """Made-up Baro data for testing. Same keys as the real API."""
    expiry = datetime.now(timezone.utc) + timedelta(days=2)
    return {
        "active": True,
        "location": "Larunda Relay (Mercury)",
        "expiry": expiry.isoformat(),
        "inventory": [
            {"item": f"Test Item {i}", "ducats": 100 + i, "credits": 50000 + i * 1000}
            for i in range(1, item_count + 1)
        ],
    }


class WeeklyPing(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.next_baro_check = None

    async def cog_load(self):
        self.check_baro.start()

    async def cog_unload(self):
        self.check_baro.cancel()

    # -------------------------- BARO LOOP --------------------------
    @tasks.loop(minutes=1)
    async def check_baro(self):
        now = datetime.now(timezone.utc)

        if self.next_baro_check and now < self.next_baro_check:
            return

        try:
            baro = await warframestat.get_baro()
        except Exception as e:
            print(f"Baro check failed: {e}")
            return

        # Set baro timer if it's not already set
        if not baro["active"]:
            if baro.get("activation"):
                self.next_baro_check = parse_time(baro["activation"])
            return

        if not baro["inventory"]:
            return  # He's here but the item list isn't filled in yet, we'll retry next minute

        channel = self.bot.get_channel(BARO_CHANNEL_ID)
        if channel is None:
            print("Baro channel not found. Check BARO_CHANNEL_ID.")
            return

        if not await self.post_baro(channel, baro, ping=True):
            return  # first message failed, next_baro_check unchanged so we retry next minute

        self.next_baro_check = parse_time(baro["expiry"])  # Once posted do not post again until next visit

    @check_baro.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # -------------------------- POSTING --------------------------
    async def post_baro(self, channel, baro, ping):
        """Post Baro's embeds, one message per chunk. Returns True if the first message went out."""
        embeds = build_baro_embeds(baro)

        # First message: (optional) @everyone + first chunk
        try:
            if ping:
                await channel.send(content="@everyone", embed=embeds[0], allowed_mentions=EVERYONE)
            else:
                await channel.send(embed=embeds[0], allowed_mentions=NO_PING)
        except Exception as e:
            print(f"Failed to post Baro: {e}")
            return False

        # Any extra chunks: one message each, no ping
        for embed in embeds[1:]:
            try:
                await channel.send(embed=embed, allowed_mentions=NO_PING)
            except Exception as e:
                print(f"Failed to post a Baro follow-up message: {e}")

        return True

    # -------------------------- TESTING --------------------------
    @app_commands.command(name="testbaro", description="Baro 알림 테스트 (이 채널에 핑 없이 게시)")
    @app_commands.describe(fake_items="가짜 아이템 수. 0 = 실제 데이터 사용 (Baro가 없으면 가짜 5개)")
    @app_commands.default_permissions(administrator=True)
    async def test_baro(self, interaction: discord.Interaction, fake_items: app_commands.Range[int, 0, 300] = 0):
        # The API call can take a few seconds; Discord needs a reply within 3, so defer first
        await interaction.response.defer(ephemeral=True)

        note = ""
        if fake_items > 0:
            baro = fake_baro(fake_items)
            note = f"가짜 아이템 {fake_items}개 사용"
        else:
            try:
                baro = await warframestat.get_baro()
            except Exception as e:
                await interaction.followup.send(f"API 호출 실패: {e}", ephemeral=True)
                return
            if not baro["active"] or not baro["inventory"]:
                baro = fake_baro(5)
                note = "Baro가 없어서 가짜 아이템 5개 사용"
            else:
                note = "실제 데이터 사용"

        ok = await self.post_baro(interaction.channel, baro, ping=False)
        result = "게시 완료" if ok else "게시 실패 (콘솔 확인)"
        await interaction.followup.send(f"{result} — {note}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(WeeklyPing(bot))