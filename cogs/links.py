import discord
from discord import app_commands
from discord.ext import commands

class Links(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="빌드", description="빌드 사이트 모음")
    async def builds(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="빌드 사이트 모음",
            description=(
                "워프레임 빌드를 찾을 때 유용한 사이트들입니다.\n"
                "━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.red(),
        )

        # 1. 종합 빌드 모음
        embed.add_field(
            name="📊 종합 빌드 시트",
            value=(
                "• [오디스 갤러리 빌드 모음](https://docs.google.com/spreadsheets/d/1kyA-h2bTLZ2JpOnUMgiB16EE-a9xNrGU0pUgukpPdsU/edit?pli=1&gid=2070403418#gid=2070403418)\n"
                "• [해외 메타 빌드 모음](https://docs.google.com/document/d/1m11trfxy8_DeRQn9FarkiW7Bki5PMdgCHvxkbJ9e5D8/edit?pli=1&tab=t.0)"
                "\n\u200b"
            ),
            inline=False,
        )

        # 2. 오버프레임 크리에이터
        embed.add_field(
            name="⭐ Overframe 추천 크리에이터",
            value=(
                "• [ninjase](https://overframe.gg/user/2890/ninjase/warframes/) \n"
                "• [THeMooN85](https://overframe.gg/user/191/themoon85/warframes/)\n"
                "• [ntrophy](https://overframe.gg/user/97820/ntrophy/warframes/) \n"
                "• [rainallon](https://overframe.gg/user/270000/rainollon/warframes/) "
                "\n\u200b"
            ),
            inline=False,
        )

        # 3. 보스 공략
        embed.add_field(
            name="🎯 레이드 공략",
            value=(
                "• [아이돌론 테랄리스트 공략 가이드](https://guide.idalon.com/)\n"
                "• [프로핏 테이커(오브의 어머니) 스피드런 공략](https://profit-taker.com/)\n"
                "━━━━━━━━━━━━━━━━━━━━"
            ),
            inline=False,
        )

        embed.set_footer(
            text="💡 추천하고 싶거나 수정이 필요한 사이트가 있다면 관리자에게 알려주세요!"
        )
        
        embed.set_footer(text="💡 추천하고 싶은 사이트가 있으면 알려주세요!")
        await interaction.response.send_message(embed=embed)

    # @app_commands.command(name="정보", description="워프레임 관한 일반 정보 링크")
    # async def builds(self, interaction: discord.Interaction):
    #     embed = discord.Embed(
    #         title="빌드 사이트 모음",
    #         description=(
    #             "워프레임 빌드를 찾을 때 유용한 사이트들입니다.\n"
    #             "━━━━━━━━━━━━━━━━━━━━"
    #         ),
    #         color=discord.Color.red(),
    #     )

    #     # 1. 종합 빌드 모음
    #     embed.add_field(
    #         name="📊 종합 빌드 시트",
    #         value=(
    #             "• [오디스 갤러리 빌드 모음](https://docs.google.com/spreadsheets/d/1kyA-h2bTLZ2JpOnUMgiB16EE-a9xNrGU0pUgukpPdsU/edit?pli=1&gid=2070403418#gid=2070403418)\n"
    #             "• [해외 메타 빌드 모음](https://docs.google.com/document/d/1m11trfxy8_DeRQn9FarkiW7Bki5PMdgCHvxkbJ9e5D8/edit?pli=1&tab=t.0)"
    #             "\n\u200b"
    #         ),
    #         inline=False,
    #     )


    #     embed.set_footer(
    #         text="💡 추천하고 싶거나 수정이 필요한 사이트가 있다면 관리자에게 알려주세요!"
    #     )
        
    #     embed.set_footer(text="💡 추천하고 싶은 사이트가 있으면 알려주세요!")
    #     await interaction.response.send_message(embed=embed)



async def setup(bot):
    await bot.add_cog(Links(bot))