import discord
from discord import app_commands
from discord.ext import commands
import random
import time
import traceback
from datetime import datetime, timezone, timedelta
from db_interface import (
    get_user_data, update_user_points, update_user_stats,
    get_server_config, update_server_config, db, delete_user_stats
)
import views

OW_MAPS = {
    "호위": ["66번 국도", "감시기지: 지브롤터", "도라도", "리알토", "샴발리 수도원", "서킷 로얄", "쓰레기촌", "하바나"],
    "혼합": ["눔바니", "미드타운", "블리자드 월드", "아이헨발데", "왕의 길", "파라이수", "할리우드"],
    "쟁탈": ["남극 반도", "네팔", "리장 타워", "사모아", "부산", "오아시스", "일리오스"],
    "밀기": ["뉴 퀸 스트리트", "루나사피", "이스페란사", "콜로세오"],
    "플래시포인트": ["뉴 정크 시티", "수라바사", "아틀리스"]
}

MAP_IMAGES = {
    "66번 국도": "https://i.namu.wiki/i/_Rl4J_Pb_DVu8DNUjSalyjmu1XBGoJJv58h6I9baBr61iho89873EzxAEiGek7wjX5LDiE5C85_hib1oVf38kGFKpunSFNpkBl272F-jHZ4eVoRXOt3T1-bbeuB7ae2yKKYa4-garvB6ydBsOBE6fg.webp",
    "감시기지: 지브롤터": "https://i.namu.wiki/i/CeJLvWIIbqgq0sQmEmPwNP-kmdVmARoOXzrIyQROyW22zF22r_m0R08e1FTXMbXahyb5qe2EFdZsmaKI1eKWBjbC_urgVGF2bFWlXdOtpsp2tetPMA1p9FZ_HbR50-gd1H0XDbMDNnjtAu7OlDA6Dg.webp",
    "도라도": "https://i.namu.wiki/i/juCs7PyBkB615iRB_ynZMkGv3xUyD-gJ_5CXqPog6oa6kNarBTYd4Ce0Ta8jEMGHDxyor4MrVU1GV0756vi6YmkuulPlJ3xYlkJyigIO11tOzm9Bpf7-i81P7KN2bj8ISq81vJM3Us6yExmJh9zY0Q.webp",
    "리알토": "https://i.namu.wiki/i/00-BfT-0qEtSFolM3P_rHgaY4p2uP0d17U3EOjzDFLAtwgGTN8sveP5vpHItjcsqc7AUM8IaHN3bhM5IIqrw2JsMb3GxfJUmfyg-Rc1WcVMRTy13Z7_uFoh1mDUYY_Wuam4hTbbxJ9M1349OHMsX7Q.webp",
    "샴발리 수도원": "https://i.namu.wiki/i/6y40vsaUS12YG7rOi1so_M9syhHpI2eHScCj67Npxol99BRKKrh_-TRtpadk9Uz699S87yNOiRepzV_VddVwxOutZ917HukCsw0jYG6szR0l06PkigFQX50ntc9fPBfjTYuDI92KBWr9F1_mWTkHDQ.webp",
    "서킷 로얄": "https://i.namu.wiki/i/-tPs3eCNkvqwWr9hGIB5VSmn74KWqf6PvjjsUyf_xU4IPRW1I7l5THngAG-_oZ5agAR8oeIvtKPJGDpD9pooHlv17GZ75FU0u-IlkeiYkvcXhLbsVx-E-DerH6tTmWY1wVfgYyUcHqNoIdwuIkXw4g.webp",
    "쓰레기촌": "https://i.namu.wiki/i/1X7j2MZfTl_imTYzom77Hlg9V_hReGTQblobM8_lfslOXGElduUwFoNW6fIB2A6dr1A1Pz1Ttqmbbxh_JgNJLk0iFfOeQFXd8E1X0z-t5R7-d01CuMCffftlfKpKmL1iutR7YuDmaUkMG9ZOEj4eBQ.webp",
    "하바나": "https://i.namu.wiki/i/7Nl8snlykffWm-piCROt95S1PPo7jpy0NTpsq_mpMPn7xd-oCqP33jQe4ldviWW59kDTymzdJrYGuR-o0S3TwynZxc409KgG3CZBuMxf33mDAMzPv1p5JjxWREJRdhrYUSw7nG6IMdfY-t3fPU07CA.webp",
    "눔바니": "https://i.namu.wiki/i/KJXTz9hVqeoNgFjAn7ao1u5TXj6M9QIQbIT_FSSIMurigLbFjBJYIfqgvye4Uywt-J14WCHNOeZrs2MhY2OpWHgmlgO47oElIYUEK2qVEktSN8feUpSjNVgqfE5GYsJjPbUHUBtssnKpSgAaLnWxjQ.webp",
    "미드타운": "https://i.namu.wiki/i/fRD5ffXB1WpMXcrSe0l5LruHgkp4HKg-qUlQGVRDzlr_5VNxy_5Z5_mLMktclKs5TGXw41sPsN6YVoWHGiCJvJsOGej5mbCQTMEFhjyL5LkswpoNOVF8F_RAekapGj7rulIjg4aTn8jcqmopccaqhA.webp",
    "블리자드 월드": "https://i.namu.wiki/i/gdcisiONMZ_pZ8hyiMphyVegcsjEZx-jr_itPziBvByO3MB31FPAvSHnxV8DF-mhWSJEGFZtBBNx4F3KPDLetfIEqkz2-iGe7rVMVqenhkEVlH8UOZEMvSRTSok_MsVENGmU6nsV_Em7WVtIfM7z-A.webp",
    "아이헨발데": "https://i.namu.wiki/i/q-KHUGXWozoTmfAmTE87qnLwqmBhZdiuhb-bTq-IgGsg-i33kZ_iT5EFpnTxRCIvhrtNumWjcf2IPUhKF83Q2cbWLCA86je1DCceTbTtCAogVnr0EuOxipJQER9gSLBMwN4u_MWfSUg-XLln4DUkWA.webp",
    "왕의 길": "https://i.namu.wiki/i/_rk99NEG0EmFWfTjQHkI6vx6UyULYtoKIgFNunLcBwfa97OvOPMnFejA9_K1guPxoVY7GTw20adJrhnRKE8g3c3tOe5GHm293AA9cWoxJk8zZpaz2JHyOk0CjO1c106bOYN08NcIY7gUeYXdJHz7lg.webp",
    "파라이수": "https://i.namu.wiki/i/oIF1xdZwHvXd-XaHh14b8-bc3D8EYT_yQzgUbXRb5cr-aQaBTmEc5MD-E8MDNyfD6V3h9NPganEnor-stEL3M4Ed8x7nj6KVeg44RuSw2nSpRagcOVfYt6G_9Yxh2MNj1Tt-eXaPIXiPhQEhDOnd0Q.webp",
    "할리우드": "https://i.namu.wiki/i/kuJRIQOcveITJwj_XVFwuAynmlGrzRZziRkrA9E_FgZyxSouj-4KMYb8E7yVCEPXxnMa072KWvkm3ch-TqVixdqly_S2qOdVGz15rPyqresfBKqUiMKVyvNIRIs0gwFGoFwmIpsOXVney84ilse40Q.webp",
    "남극 반도": "https://i.namu.wiki/i/2c1tx1KuIVkmAxFfXEaKueqIB8Kh3tEVZPa3F4pq48mWXhMjRxIi1T2i53tu7mQPxO5fDndfMPFibNv0cgHLKyXvqQI4G--0SwjBqV3V4USDDS6CytIQ56a6Z_qHR1tvVVZh_KzIsul6DUfAi24zRg.webp",
    "네팔": "https://i.namu.wiki/i/xEuoB4uY96l2rNqTYEgPmTKtSXY-wcdlpoPit7iPk-cz-Fl8YFeCnJsDh4XjChHREeERPDlhvdGlPLhDw9jHJY2rmN81unzaL9ZR99wGJf8f9kIpWNK_NBhKbzTwu8LAWk7R3HlrdgnlJBLLV49Z1w.webp",
    "리장 타워": "https://i.namu.wiki/i/XAmlHOtXXA0d1RQw4QKB9ZUBB8CmB3t_beevRIDAQpE9cwXDqQnC8qOoa48BiV9HwZWjEfSug3V5qp-U0y5ZVTwlZJOg45p4u1mi8y5OuomscJhHMkJ55BZ6m4XAc5I4y0WOhPH5digRjc-QV2IZkw.webp",
    "사모아": "https://i.namu.wiki/i/ePydQBMVTqxYAkONdKY90hXUp9hCSYtb6LxTH1_nyQ7lD-3_0EBI5bGogsMQL4AOYZgtnvktcGKTGTS8BnyylaK6GUy26OFN_-mR-2DC7U8NMVPNqqswDKkU1E6QkEtthjPE_k9rC14hXKmH2lQA-A.webp",
    "부산": "https://i.namu.wiki/i/om99tfzoD7sSXIvQ6TE03p199amjaruoyk4O7xXIiJUlg_qeDewjx4edm4pPzE1rQhpx8kbVH2uKvYabPEhU6oVL0tp1z9NNXhwOCKrwqn2CFiU3O84L8IF9iK990b2RwUNtvnOJRyXj-00yjVp0yQ.webp",
    "오아시스": "https://i.namu.wiki/i/h7xmQjn2zvwuhbgWdPIafvNCvKuyOP9tEgTSO2HI0eExLNgpH8Q9IZk9U0LTvCOXZT5xCMhJqEzysFGcv3Vui2Ns9k99l8qOeTQO6p9V7-WdJr94Kctt-Tn8atrmCKtb3qHiZMK3srbPciIiK4fwvA.webp",
    "일리오스": "https://i.namu.wiki/i/Rv3gIfyRYMxky-wT_uxwaak5x7AviG31oyhXa9Ezl5WetAdpPD3c1wyx-tLKIOoYewkqQN9TSz5zLPaRhnhVIYO-gLkejzEcY2NUMQhg2mmREdZeJPHc2JieOv059ebq8w-2IBC0mGMjmde1yo2vtg.webp",
    "뉴 퀸 스트리트": "https://i.namu.wiki/i/36AF5oSwOVRINiZswx2vrHVlemXK4bDSZjXihmwC3oTCiKgHzyqVdtO-jeca12bZ3WkgccR5RDByxAezmcT4EnGWMtn7MP49cKx-qMNs9VpqCGnouYSHbYCEzQDXsc9PBEJBt8c2-teb0slgEBESxw.webp",
    "루나사피": "https://i.namu.wiki/i/iO3Xftn5jx_jnBZ9s7XVVaqlDtQXdtqce8PrDRi7me43E1YUqRYMRZRlkVlFgVZcR5Ured-8vwoV1TRNY5RN_nCaUCFwyrPddxPXECWywb0v-eWpkwhIPTnD3zgAqSoRdL0MXsTurE7BETaWE6sejw.webp",
    "이스페란사": "https://i.namu.wiki/i/e-4MRjAHc7XIzsYcck5bAqKqYLIgAvwtS1SCidEod40omK0l91ucQACk9oDJNxDbkKX--jW86U86EYqKp-t4dbA2MWAJmOLTyNNH27XUYqzyNOU1I7cksfZvbfeR8LYwgNnCMZODlthFQp_fSbQnmA.webp",
    "콜로세오": "https://i.namu.wiki/i/1f-2qwjXNmuqzVBSjEo-fTupa66jX9XAwX6wEnFBXiNF1cEyXJWE67ddB9UonAWnJmE1rJaBISt33Lqo1hVi-JV0wTrejCuydSRE2797BLTHiip0_s5Jt5PGfVQKC9bWRcXVevwH4ryGakpAL-CYag.webp",
    "뉴 정크 시티": "https://i.namu.wiki/i/ygXLOVLBuEuC-MOsPQ7KagChnc4pjkUAN4YBg3oh6jkQ9kGbr_vFPUg9TpKZJFaD4AcGFJX7KLWUTn9nts_v9GZGO9D96cecw7Ue_FR6WmBMutnmEIKf-V_ThWuCcM4Qnm0uwxio5Jq8TX-JN7kWJg.webp",
    "수라바사": "https://i.namu.wiki/i/00L5OoijkxUfWXH9chvw0PdxCTJ_KfmZ8KZ70QKfIQbw0wsWBqYggZA-JzbgGcfYymFZyLVOJXlJpf1rpUgDkoSU9X_wc51FpLLsZK6k3iH7E39iB7A-mzdAAt9Bd6-DKaSw2Yc0lp089p-UXHgE4A.webp",
    "아틀리스": "https://i.namu.wiki/i/xsyZB9oK5zQSZ7uVHgmHbwGZ1imbLIF2SHfO0q4YqKgfq1N2qlN_BlxetBAoLXLHHXuXZiHYYnkz5VefvBecRygQmQzz__1vS-fCLE31Yilv33DP7IMTdtaSwgSSZqpVTz40lvFApVYM-RpCzaOXpg.webp"
}


def check_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    cfg = get_server_config(interaction.guild.id)
    admin_role_id = cfg.get('admin_role_id')
    return bool(admin_role_id and any(role.id == int(admin_role_id) for role in interaction.user.roles))


class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        err_msg = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        print(f"❌ [에러 발생] {err_msg}")
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ 명령어 처리 중 오류가 발생했습니다.\n```py\n{error}\n```", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 명령어 처리 중 오류가 발생했습니다.\n```py\n{error}\n```", ephemeral=True)

    # ─────────────────────────────────────────────
    # [일반] 안내 및 정보
    # ─────────────────────────────────────────────

    @app_commands.command(name="명령어", description="봇의 전체 슬래시 명령어 목록과 설명을 확인합니다.")
    async def help_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(title="🤖 이랑 봇 명령어 안내", color=discord.Color.gold())
        embed.add_field(name="`/정보`, `/랭킹`", value="유저의 상세 정보와 서버 랭킹을 확인합니다.", inline=False)
        embed.add_field(name="`/정보수정`", value="본인의 내전 프로필(포지션, 티어, 배틀태그 등)을 수정합니다.", inline=False)
        embed.add_field(name="`/맵`", value="내전 전장 선택 및 무작위 룰렛을 돌립니다.", inline=False)
        embed.add_field(name="`/출석`, `/구제`", value="하루 1번 포인트를 얻거나, 파산 시 구제금을 받습니다.", inline=False)
        embed.add_field(name="`/서버세팅` (관리자)", value="채널 및 역할을 설정하는 통합 메뉴입니다.", inline=False)
        embed.add_field(name="`/내전시작` (관리자)", value="팀 분배, 밴픽, 배팅을 한 번에 엽니다.", inline=False)
        embed.add_field(name="`/경기취소` (관리자)", value="진행 중인 내전을 무효화하고 배팅을 환불합니다.", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="귀여워", description="🐾")
    async def cute_link(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send("🐾 https://www.instagram.com/i.rang0321/")

    # ─────────────────────────────────────────────
    # [일반] 맵 룰렛
    # ─────────────────────────────────────────────

    @app_commands.command(name="맵", description="내전 전장 룰렛을 돌리거나 맵을 뽑습니다.")
    @app_commands.choices(모드=[
        app_commands.Choice(name="전체 랜덤", value="전체"),
        app_commands.Choice(name="호위", value="호위"),
        app_commands.Choice(name="혼합", value="혼합"),
        app_commands.Choice(name="쟁탈", value="쟁탈"),
        app_commands.Choice(name="밀기", value="밀기"),
        app_commands.Choice(name="플래시포인트", value="플래시포인트")
    ])
    async def pick_map(self, interaction: discord.Interaction, 모드: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=False)
        selected_mode = 모드.value
        if selected_mode == "전체":
            all_maps = [m for maps in OW_MAPS.values() for m in maps]
            result_map = random.choice(all_maps)
            found_mode = next(k for k, v in OW_MAPS.items() if result_map in v)
        else:
            found_mode = selected_mode
            result_map = random.choice(OW_MAPS[found_mode])

        embed = discord.Embed(
            title=f"🎲 [{found_mode}] 전장 무작위 룰렛!",
            description=f"이번 내전은 **{result_map}**에서 진행됩니다.",
            color=discord.Color.purple()
        )
        if result_map in MAP_IMAGES:
            embed.set_image(url=MAP_IMAGES[result_map])
        await interaction.followup.send(embed=embed)

    # ─────────────────────────────────────────────
    # [일반] 출석 / 구제
    # ─────────────────────────────────────────────

    @app_commands.command(name="출석", description="하루에 한 번 10~100 포인트를 랜덤하게 받습니다.")
    async def daily_attendance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        guild_id, user_id = interaction.guild.id, interaction.user.id
        data = get_user_data(guild_id, user_id)

        KST = timezone(timedelta(hours=9))
        today_kst = datetime.now(KST).strftime('%Y-%m-%d')
        last_daily = data.get('last_daily', '')

        if last_daily == today_kst:
            return await interaction.followup.send("❌ 오늘 이미 출석했습니다. 자정이 지나면 다시 출석할 수 있습니다.")

        reward = random.randint(10, 100)
        update_user_points(guild_id, user_id, reward)
        update_user_stats(guild_id, user_id, {'last_daily': today_kst})
        await interaction.followup.send(f"🎉 출석 체크 완료! 랜덤으로 **{reward}P**를 획득했습니다.")

    @app_commands.command(name="구제", description="잔액이 100P 이하일 때 하루 1번 300P를 지원받습니다.")
    async def relief_fund(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        guild_id, user_id = interaction.guild.id, interaction.user.id
        data = get_user_data(guild_id, user_id)

        if data.get('points', 0) > 100:
            return await interaction.followup.send("❌ 잔액이 100P 이하일 때만 구제금을 받을 수 있습니다.")

        KST = timezone(timedelta(hours=9))
        today_kst = datetime.now(KST).strftime('%Y-%m-%d')
        last_relief = data.get('last_relief', '')

        if last_relief == today_kst:
            return await interaction.followup.send("❌ 오늘 이미 구제금을 받았습니다. 자정이 지나면 다시 받을 수 있습니다.")

        update_user_points(guild_id, user_id, 300)
        update_user_stats(guild_id, user_id, {'last_relief': today_kst})
        await interaction.followup.send("🪙 파산 구제금 **300P**가 지급되었습니다. 건투를 빕니다!")

    # ─────────────────────────────────────────────
    # [일반] 정보 / 랭킹 / 정보수정
    # ─────────────────────────────────────────────

    @app_commands.command(name="정보", description="자신 또는 다른 유저의 프로필, 전적, 포인트를 확인합니다.")
    async def user_info(self, interaction: discord.Interaction, 대상: discord.Member = None):
        await interaction.response.defer(ephemeral=False)
        target = 대상 or interaction.user
        data = get_user_data(interaction.guild.id, target.id)

        # 입장 미완료 유저 표기
        not_registered = (
            data.get('main_pos', '-') == '-' and
            data.get('battletag', '-') == '-'
        )
        if not_registered:
            return await interaction.followup.send(
                f"❌ **{target.display_name}** 님은 아직 입장 등록을 완료하지 않으셨습니다.\n"
                "입장 채널의 버튼을 눌러 등록해주세요."
            )

        embed = discord.Embed(
            title=f"📊 {data.get('nickname', target.display_name)}님의 정보",
            color=discord.Color.blue()
        )
        embed.add_field(name="배틀태그", value=data.get('battletag', '-'), inline=True)
        embed.add_field(name="티어", value=f"현재: {data.get('current_tier', '-')} / 최고: {data.get('max_tier', '-')}", inline=True)
        embed.add_field(name="포지션", value=f"주: {data.get('main_pos', '-')} / 부: {data.get('sub_pos', '-')}", inline=True)
        embed.add_field(name="모스트 영웅", value=data.get('main_hero', '-'), inline=False)

        wins = int(data.get('wins', 0))
        losses = int(data.get('losses', 0))
        winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        embed.add_field(name="전적", value=f"{wins}승 {losses}패 (승률 {winrate:.1f}%)", inline=True)
        embed.add_field(name="보유 포인트", value=f"{data.get('points', 0):,} P", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="랭킹", description="서버 내 유저들의 포인트 랭킹을 확인합니다.")
    async def show_ranking(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        users_ref = db.collection('servers').document(str(interaction.guild.id)).collection('users')
        users = [doc.to_dict() for doc in users_ref.get()]
        users.sort(key=lambda x: x.get('points', 0), reverse=True)

        top_points = users[:10]
        embed = discord.Embed(title="🏆 서버 포인트 랭킹 TOP 10", color=discord.Color.gold())

        point_text = ""
        for i, u in enumerate(top_points, 1):
            point_text += f"**{i}위** {u.get('nickname', '알수없음')} - {u.get('points', 0):,} P\n"

        embed.add_field(name="💰 포인트", value=point_text or "데이터 없음", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="정보수정", description="자신의 내전 프로필(배틀태그, 영웅 등)을 수정합니다.")
    async def edit_my_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        view = views.EditUserView(interaction.user, is_admin=False)
        await interaction.followup.send(
            f"🔧 **[{interaction.user.display_name}]** 님의 정보 수정 패널입니다. 수정할 항목을 선택하세요.",
            view=view,
            ephemeral=True
        )

    # ─────────────────────────────────────────────
    # [관리자] 유저 관리
    # ─────────────────────────────────────────────

    @app_commands.command(name="유저관리", description="[관리자] 특정 유저의 내전 데이터를 직접 수정합니다.")
    async def manage_user(self, interaction: discord.Interaction, 유저: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        view = views.EditUserView(유저, is_admin=True)
        await interaction.followup.send(
            f"🛠️ **[{유저.display_name}]** 유저 관리 패널입니다. 수정할 항목을 선택하세요.",
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="전적초기화", description="[관리자] 특정 유저의 승/패 기록만 0으로 리셋합니다.")
    async def reset_record(self, interaction: discord.Interaction, 유저: discord.Member):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        update_user_stats(interaction.guild.id, 유저.id, {'wins': 0, 'losses': 0})
        await interaction.followup.send(
            f"✅ {유저.display_name}님의 승패 기록을 0승 0패로 초기화했습니다.", ephemeral=True
        )

    @app_commands.command(name="서버초기화", description="[서버장 전용] 해당 서버의 봇 데이터를 모두 초기화합니다.")
    async def reset_server_data(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ 서버 소유자(최고 관리자)만 가능합니다.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        for sub_col in ['users', 'roles', 'config', 'active_match', 'match_history']:
            docs = db.collection('servers').document(guild_id).collection(sub_col).stream()
            batch = db.batch()
            for doc in docs:
                batch.delete(doc.reference)
            batch.commit()

        await interaction.followup.send("💥 서버의 모든 봇 데이터가 초기화되었습니다.", ephemeral=True)

    @app_commands.command(name="경기취소", description="[관리자] 진행 중인 내전을 취소하고 배팅을 환불합니다.")
    async def cancel_match(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        doc_ref = db.collection('servers').document(str(interaction.guild.id)).collection('active_match').document('main')
        doc = doc_ref.get()

        if doc.exists and doc.to_dict().get('bets'):
            match_data = doc.to_dict()
            bets = match_data.get('bets', {})
            refund_count = 0
            for team, bet_data in bets.items():
                for uid, amount in bet_data.items():
                    update_user_points(interaction.guild.id, int(uid), amount)
                    refund_count += 1
            doc_ref.delete()
            await interaction.followup.send(
                f"✅ 매치를 취소하고 {refund_count}명에게 배팅 금액을 환불했습니다.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "⚠️ 현재 환불할 수 있는 활성 매치(배팅 데이터)가 없습니다.", ephemeral=True
            )

    @app_commands.command(name="포인트", description="[관리자] 특정 유저의 포인트를 지급, 차감 또는 설정합니다.")
    @app_commands.describe(유저="대상 유저", 작업="조작 방식", 금액="포인트 양")
    @app_commands.choices(작업=[
        app_commands.Choice(name="지급 (+)", value="add"),
        app_commands.Choice(name="차감 (-)", value="sub"),
        app_commands.Choice(name="설정 (=)", value="set")
    ])
    async def manage_points(self, interaction: discord.Interaction, 유저: discord.Member, 작업: app_commands.Choice[str], 금액: int):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        guild_id, user_id = interaction.guild.id, 유저.id
        current_points = get_user_data(guild_id, user_id).get('points', 0)

        if 작업.value == "add":
            update_user_points(guild_id, user_id, 금액)
            msg = f"✅ {유저.mention}님에게 {금액}P를 지급했습니다. (현재 {current_points + 금액}P)"
        elif 작업.value == "sub":
            update_user_points(guild_id, user_id, -금액)
            msg = f"✅ {유저.mention}님의 {금액}P를 차감했습니다. (현재 {current_points - 금액}P)"
        else:
            update_user_stats(guild_id, user_id, {'points': 금액})
            msg = f"✅ {유저.mention}님의 포인트를 {금액}P로 설정했습니다."

        await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="청소", description="[관리자] 현재 채널의 채팅을 일정 수량만큼 일괄 삭제합니다.")
    async def clear_messages(self, interaction: discord.Interaction, 수량: int):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        deleted = await interaction.channel.purge(limit=수량)
        await interaction.followup.send(f"✅ {len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)

    # ─────────────────────────────────────────────
    # [관리자] 서버 세팅 그룹
    # ─────────────────────────────────────────────

    server_setup = app_commands.Group(name="서버세팅", description="서버의 채널 및 역할 통합 설정")

    @server_setup.command(name="채널", description="내전 대기실, 공지, 팀 음성채널을 설정합니다.")
    async def setup_channels(self, interaction: discord.Interaction, 대기실: discord.VoiceChannel = None, 공지: discord.TextChannel = None, 팀1: discord.VoiceChannel = None, 팀2: discord.VoiceChannel = None):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        gid = interaction.guild.id
        if 대기실: update_server_config(gid, 'lobby_id', str(대기실.id))
        if 공지: update_server_config(gid, 'announce_id', str(공지.id))
        if 팀1: update_server_config(gid, 't1_id', str(팀1.id))
        if 팀2: update_server_config(gid, 't2_id', str(팀2.id))
        await interaction.followup.send("✅ 채널 설정이 업데이트 되었습니다.", ephemeral=True)

    @server_setup.command(name="기본역할", description="관리자 역할 및 입장 시 부여/제거할 역할을 설정합니다.")
    async def setup_basic_roles(self, interaction: discord.Interaction, 관리자: discord.Role = None, 입장시부여: discord.Role = None, 입장시제거: discord.Role = None):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        gid = interaction.guild.id
        if 관리자: update_server_config(gid, 'admin_role_id', str(관리자.id))
        if 입장시부여:
            db.collection('servers').document(str(gid)).collection('roles').document('entry_give').set({'role_id': str(입장시부여.id)})
        if 입장시제거:
            db.collection('servers').document(str(gid)).collection('roles').document('entry_remove').set({'role_id': str(입장시제거.id)})
        await interaction.followup.send("✅ 기본 역할 설정이 업데이트 되었습니다.", ephemeral=True)

    @server_setup.command(name="포지션역할", description="포지션에 맞게 지급될 디스코드 역할을 설정합니다.")
    async def setup_pos_roles(self, interaction: discord.Interaction, 돌격: discord.Role = None, 공격: discord.Role = None, 지원: discord.Role = None, 올라운더: discord.Role = None):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        roles_ref = db.collection('servers').document(str(interaction.guild.id)).collection('roles')
        if 돌격: roles_ref.document('pos_돌격').set({'role_id': str(돌격.id)})
        if 공격: roles_ref.document('pos_공격').set({'role_id': str(공격.id)})
        if 지원: roles_ref.document('pos_지원').set({'role_id': str(지원.id)})
        if 올라운더: roles_ref.document('pos_올라운더').set({'role_id': str(올라운더.id)})
        await interaction.followup.send("✅ 포지션 역할이 매핑되었습니다.", ephemeral=True)

    @server_setup.command(name="티어역할", description="티어에 맞게 지급될 디스코드 역할을 설정합니다.")
    async def setup_tier_roles(self, interaction: discord.Interaction, 브론즈: discord.Role = None, 실버: discord.Role = None, 골드: discord.Role = None, 플래티넘: discord.Role = None, 다이아몬드: discord.Role = None, 마스터: discord.Role = None):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        roles_ref = db.collection('servers').document(str(interaction.guild.id)).collection('roles')
        if 브론즈: roles_ref.document('tier_브론즈').set({'role_id': str(브론즈.id)})
        if 실버: roles_ref.document('tier_실버').set({'role_id': str(실버.id)})
        if 골드: roles_ref.document('tier_골드').set({'role_id': str(골드.id)})
        if 플래티넘: roles_ref.document('tier_플래티넘').set({'role_id': str(플래티넘.id)})
        if 다이아몬드: roles_ref.document('tier_다이아몬드').set({'role_id': str(다이아몬드.id)})
        if 마스터: roles_ref.document('tier_마스터').set({'role_id': str(마스터.id)})
        await interaction.followup.send("✅ 티어 역할이 매핑되었습니다.", ephemeral=True)

    @app_commands.command(name="입장채널세팅", description="[관리자] 현재 채널에 내전 입장 영구 버튼을 생성합니다.")
    async def setup_entry_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        embed = discord.Embed(
            title="🎮 내전 프로필 등록",
            description="아래 버튼을 눌러 본인의 포지션과 티어, 배틀태그를 등록해야 내전에 참여할 수 있습니다.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed, view=views.EntryButtonView())
        await interaction.followup.send("✅ 입장 버튼 세팅이 완료되었습니다.", ephemeral=True)

    @app_commands.command(name="관리자역할설정", description="[서버장 전용] 봇 관리자 명령어를 사용할 역할을 지정합니다.")
    async def set_admin_role(self, interaction: discord.Interaction, 역할: discord.Role):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ 디스코드 서버 관리자(서버장) 권한이 필요합니다.", ephemeral=True)

        update_server_config(interaction.guild.id, 'admin_role_id', str(역할.id))
        await interaction.followup.send(
            f"✅ {역할.mention} 역할을 가진 유저는 봇 관리자 기능을 사용할 수 있습니다.", ephemeral=True
        )

    # ─────────────────────────────────────────────
    # [관리자] 내전 시작
    # ─────────────────────────────────────────────

    @app_commands.command(name="내전시작", description="[관리자] 대기실 인원을 바탕으로 내전 매칭, 밴픽, 배팅을 엽니다.")
    async def start_civil_war(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        cfg = get_server_config(interaction.guild.id)
        lobby_id = cfg.get('lobby_id')
        if not lobby_id:
            return await interaction.followup.send("❌ `/서버세팅 채널`에서 대기실을 먼저 설정하세요.")

        lobby = interaction.guild.get_channel(int(lobby_id))
        if not lobby or not isinstance(lobby, discord.VoiceChannel):
            return await interaction.followup.send("❌ 유효한 대기실 음성 채널이 아닙니다.")

        members = [m for m in lobby.members if not m.bot]
        if len(members) < 2:
            return await interaction.followup.send(f"❌ 인원이 부족합니다. (현재 {len(members)}명)")

        random.shuffle(members)
        mid = len(members) // 2
        t1_members, t2_members = members[:mid], members[mid:]
        t1_cap, t2_cap = t1_members[0], t2_members[0]

        embed = discord.Embed(
            title="🔥 내전 매칭 완료!",
            description="팀 분배가 완료되었습니다. 밴픽 및 배팅을 시작합니다.",
            color=discord.Color.red()
        )
        embed.add_field(name="🛡️ 1팀", value="\n".join([m.mention for m in t1_members]), inline=True)
        embed.add_field(name="⚔️ 2팀", value="\n".join([m.mention for m in t2_members]), inline=True)

        bp_view = views.BanPickView(t1_cap, t2_cap, t1_members, t2_members)
        await interaction.followup.send(embed=embed, view=bp_view)

        match_id = f"{interaction.guild.id}_{int(time.time())}"
        db.collection('servers').document(str(interaction.guild.id)).collection('active_match').document('main').set(
            {'match_id': match_id, 'bets': {},
             't1_members': [str(m.id) for m in t1_members],
             't2_members': [str(m.id) for m in t2_members]}
        )

        bet_embed = discord.Embed(title="🪙 승부 예측", description="승리할 팀에 배팅하세요!", color=discord.Color.gold())
        bet_view = views.BettingView(match_id, "1팀", "2팀")
        await interaction.channel.send(embed=bet_embed, view=bet_view)

        admin_embed = discord.Embed(
            title="⚙️ 정산 패널",
            description="경기가 종료되면 승리한 팀을 눌러 전적을 정산하세요.",
            color=discord.Color.dark_gray()
        )
        await interaction.channel.send(
            embed=admin_embed,
            view=views.AdminControlPanel(match_id, bet_view, t1_members, t2_members)
        )


async def setup(bot):
    await bot.add_cog(GameCommands(bot))
    bot.add_view(views.EntryButtonView())