from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services import worldstate_raw

BARO_CHANNEL_ID = 1560292325278617690  # put your Baro channel ID here
EVERYONE = discord.AllowedMentions(everyone=True)
NO_PING = discord.AllowedMentions.none()

BARO_COLOR = discord.Color.from_rgb(32, 178, 170)  # Baro teal
AWAY_COLOR = discord.Color.dark_grey()
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


# -------------------------- EMBEDS --------------------------
def build_baro_embeds(baro):
    """Baro is here: location, departure time, and his full inventory."""
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


def build_away_embed(activation, location):
    """Baro is away and we know when he's coming."""
    embed = discord.Embed(
        title="🚫 바로 키티어는 지금 없습니다",
        description=(
            f"**도착 예정:** {discord.utils.format_dt(activation, 'F')} ({discord.utils.format_dt(activation, 'R')})\n"
            f"**도착 위치:** {location}"
        ),
        color=AWAY_COLOR,
    )
    embed.set_footer(text="업데이트")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def build_unknown_embed():
    """Baro is away and DE hasn't announced his next visit yet."""
    embed = discord.Embed(
        title="🚫 바로 키티어는 지금 없습니다",
        description="다음 방문 일정이 아직 발표되지 않았습니다.",
        color=AWAY_COLOR,
    )
    embed.set_footer(text="업데이트")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


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


class BaroPing(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.next_baro_check = None
        self.posted_state = None  # what the Baro channel currently shows, e.g. ("here", "<activation>")

    async def cog_load(self):
        self.check_baro.start()

    async def cog_unload(self):
        self.check_baro.cancel()

    # -------------------------- BARO LOOP --------------------------
    @tasks.loop(minutes=1)
    async def check_baro(self):
        print("Checking baro!")
        now = datetime.now(timezone.utc)

        if self.next_baro_check and now < self.next_baro_check:
            return

        try:
            baro = await worldstate_raw.get_baro()
        except Exception as e:
            print(f"Baro check failed: {e}")
            return

        activation = parse_time(baro["activation"]) if baro.get("activation") else None

        # Work out what the channel SHOULD show right now
        if baro["active"]:
            if not baro["inventory"]:
                return  # He's here but the item list isn't filled in yet, we'll retry next minute
            state = ("here", baro["activation"])
            embeds = build_baro_embeds(baro)
            next_check = parse_time(baro["expiry"])  # nothing changes until he leaves
        elif activation and activation > now:
            state = ("away", baro["activation"])
            embeds = [build_away_embed(activation, baro.get("location", "?"))]
            next_check = activation  # nothing changes until he arrives
        else:
            state = ("unknown", None)
            embeds = [build_unknown_embed()]
            next_check = None  # keep checking every minute until DE announces the next visit

        # Only touch the channel if what it shows is out of date
        if state != self.posted_state:
            channel = self.bot.get_channel(BARO_CHANNEL_ID)
            if channel is None:
                print("Baro channel not found. Check BARO_CHANNEL_ID.")
                return

            # Ping only when we SEE him arrive (not when the bot just started up)
            ping = state[0] == "here" and self.posted_state is not None

            if not await self.replace_channel_post(channel, embeds, ping):
                return  # posting failed, state unchanged so we retry next minute
            self.posted_state = state

        self.next_baro_check = next_check

    @check_baro.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # -------------------------- POSTING --------------------------
    async def post_embeds(self, channel, embeds, ping):
        """Post embeds, one message per embed. Returns the first message, or None if it failed."""
        try:
            if ping:
                first = await channel.send(content="@everyone", embed=embeds[0], allowed_mentions=EVERYONE)
            else:
                first = await channel.send(embed=embeds[0], allowed_mentions=NO_PING)
        except Exception as e:
            print(f"Failed to post Baro: {e}")
            return None

        # Any extra chunks: one message each, no ping
        for embed in embeds[1:]:
            try:
                await channel.send(embed=embed, allowed_mentions=NO_PING)
            except Exception as e:
                print(f"Failed to post a Baro follow-up message: {e}")

        return first

    async def replace_channel_post(self, channel, embeds, ping):
        """Post the new message(s) FIRST, then delete everything older.
        If posting fails, the old post stays up instead of leaving the channel empty."""
        first = await self.post_embeds(channel, embeds, ping)
        if first is None:
            return False

        try:
            await channel.purge(limit=100, before=first)  # delete everything older than the new post
        except Exception as e:
            print(f"Couldn't clean up old Baro messages: {e}")
        return True

    # -------------------------- /키티어 --------------------------
    @app_commands.command(name="키티어", description="바로 키티어가 지금 와 있는지 확인합니다")
    async def kiteer(self, interaction: discord.Interaction):
        await interaction.response.defer()  # API call can take a few seconds

        try:
            baro = await worldstate_raw.get_baro()
        except Exception as e:
            print(f"/키티어 failed: {e}")
            await interaction.followup.send("지금은 바로 키티어 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.")
            return

        now = datetime.now(timezone.utc)
        activation = parse_time(baro["activation"]) if baro.get("activation") else None

        if baro["active"]:
            # He's here: where, when he leaves, and where the item list is
            expiry = parse_time(baro["expiry"])
            embed = discord.Embed(
                title="💰 바로 키티어가 와 있습니다!",
                description=(
                    f"📍 **위치:** {baro.get('location', '?')}\n"
                    f"**떠나는 시간:** {discord.utils.format_dt(expiry, 'F')} ({discord.utils.format_dt(expiry, 'R')})\n\n"
                    f"판매 목록은 <#{BARO_CHANNEL_ID}> 채널에서 확인하세요!"
                ),
                color=BARO_COLOR,
            )
        elif activation and activation > now:
            embed = build_away_embed(activation, baro.get("location", "?"))
        else:
            embed = build_unknown_embed()

        await interaction.followup.send(embed=embed)

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
                baro = await worldstate_raw.get_baro()
            except Exception as e:
                await interaction.followup.send(f"API 호출 실패: {e}", ephemeral=True)
                return
            if not baro["active"] or not baro["inventory"]:
                baro = fake_baro(5)
                note = "Baro가 없어서 가짜 아이템 5개 사용"
            else:
                note = "실제 데이터 사용"

        # Posts in THIS channel without deleting anything
        first = await self.post_embeds(interaction.channel, build_baro_embeds(baro), ping=False)
        result = "게시 완료" if first else "게시 실패 (콘솔 확인)"
        await interaction.followup.send(f"{result} — {note}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BaroPing(bot))