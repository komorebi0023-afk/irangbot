import discord
from discord.ext import commands
import random
import json
import os

# 봇 권한 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 데이터 파일 이름
SCORE_FILE = 'scores.json'
CONFIG_FILE = 'config.json'

# --- 오버워치 전장 데이터 (최신 반영) ---
OW_MAPS = {
    "호위": ["66번 국도", "감시기지: 지브롤터", "도라도", "리알토", "샴발리 수도원", "서킷 로얄", "쓰레기촌", "하바나"],
    "혼합": ["눔바니", "미드타운", "블리자드 월드", "아이헨발데", "왕의 길", "파라이수", "할리우드"],
    "쟁탈": ["남극 반도", "네팔", "리장 타워", "사모아", "부산", "오아시스", "일리오스"],
    "밀기": ["뉴 퀸 스트리트", "루나사피", "이스페란사", "콜로세오"],
    "플래시포인트": ["뉴 정크 시티", "수라바사", "아틀리스"]
}

# --- 📸 1/2단계: 모드별 썸네일(작은) 이미지 링크 ---
MODE_IMAGES = {
    "전체": "https://cdn.discordapp.com/attachments/1508104373568274482/1508115279249543168/all.png?ex=6a145d4e&is=6a130bce&hm=49965cb1a19491d6534dcbb6961447bbb27d8c55925f45db0e359a56117abe04&",
    "호위": "https://cdn.discordapp.com/attachments/1508104373568274482/1508115373981962352/2026-05-24_232829.png?ex=6a145d64&is=6a130be4&hm=94ff9479b8b45ea5115c4e027f98a138313448ed5ab711b166c3e2a48fc7a5a0&",
    "혼합": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113692955377844/2026-05-24_232456.png?ex=6a145bd3&is=6a130a53&hm=07840c8ca8468e692c95f5326bbf3fdbe13e41ba91861c280f5120b2ddf4938c&",
    "쟁탈": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113692535816243/2026-05-24_232448.png?ex=6a145bd3&is=6a130a53&hm=8cd2a0e159ab37c1bca671369406d768e7f37075dd559bc5df27f0864b310113&",
    "밀기": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113693370617947/2026-05-24_232500.png?ex=6a145bd3&is=6a130a53&hm=8252787a0cd3ff362d9455915b3e670a3d5bb804ff48ebe2868e93f1b30de697&",
    "플래시포인트": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113693773398086/2026-05-24_232505.png?ex=6a145bd3&is=6a130a53&hm=458076f23beae0d09bb3bfe1593ac7eb811ff1dad65ed19d3f9b5e2337ee218e&"
}

# --- 📸 3단계: 개별 맵 확정 시 출력될 대형 이미지 링크 (뼈대) ---
# 나중에 우측의 "https://via.placeholder.com/..." 부분을 실제 맵 이미지 디스코드 링크로 변경하세요!
MAP_IMAGES = {
    # 호위
    "66번 국도": "https://i.namu.wiki/i/_Rl4J_Pb_DVu8DNUjSalyjmu1XBGoJJv58h6I9baBr61iho89873EzxAEiGek7wjX5LDiE5C85_hib1oVf38kGFKpunSFNpkBl272F-jHZ4eVoRXOt3T1-bbeuB7ae2yKKYa4-garvB6ydBsOBE6fg.webp",
    "감시기지: 지브롤터": "https://i.namu.wiki/i/CeJLvWIIbqgq0sQmEmPwNP-kmdVmARoOXzrIyQROyW22zF22r_m0R08e1FTXMbXahyb5qe2EFdZsmaKI1eKWBjbC_urgVGF2bFWlXdOtpsp2tetPMA1p9FZ_HbR50-gd1H0XDbMDNnjtAu7OlDA6Dg.webp",
    "도라도": "https://i.namu.wiki/i/juCs7PyBkB615iRB_ynZMkGv3xUyD-gJ_5CXqPog6oa6kNarBTYd4Ce0Ta8jEMGHDxyor4MrVU1GV0756vi6YmkuulPlJ3xYlkJyigIO11tOzm9Bpf7-i81P7KN2bj8ISq81vJM3Us6yExmJh9zY0Q.webp",
    "리알토": "https://i.namu.wiki/i/00-BfT-0qEtSFolM3P_rHgaY4p2uP0d17U3EOjzDFLAtwgGTN8sveP5vpHItjcsqc7AUM8IaHN3bhM5IIqrw2JsMb3GxfJUmfyg-Rc1WcVMRTy13Z7_uFoh1mDUYY_Wuam4hTbbxJ9M1349OHMsX7Q.webp",
    "샴발리 수도원": "https://i.namu.wiki/i/6y40vsaUS12YG7rOi1so_M9syhHpI2eHScCj67Npxol99BRKKrh_-TRtpadk9Uz699S87yNOiRepzV_VddVwxOutZ917HukCsw0jYG6szR0l06PkigFQX50ntc9fPBfjTYuDI92KBWr9F1_mWTkHDQ.webp",
    "서킷 로얄": "https://i.namu.wiki/i/-tPs3eCNkvqwWr9hGIB5VSmn74KWqf6PvjjsUyf_xU4IPRW1I7l5THngAG-_oZ5agAR8oeIvtKPJGDpD9pooHlv17GZ75FU0u-IlkeiYkvcXhLbsVx-E-DerH6tTmWY1wVfgYyUcHqNoIdwuIkXw4g.webp",
    "쓰레기촌": "https://i.namu.wiki/i/1X7j2MZfTl_imTYzom77Hlg9V_hReGTQblobM8_lfslOXGElduUwFoNW6fIB2A6dr1A1Pz1Ttqmbbxh_JgNJLk0iFfOeQFXd8E1X0z-t5R7-d01CuMCffftlfKpKmL1iutR7YuDmaUkMG9ZOEj4eBQ.webp",
    "하바나": "https://i.namu.wiki/i/7Nl8snlykffWm-piCROt95S1PPo7jpy0NTpsq_mpMPn7xd-oCqP33jQe4ldviWW59kDTymzdJrYGuR-o0S3TwynZxc409KgG3CZBuMxf33mDAMzPv1p5JjxWREJRdhrYUSw7nG6IMdfY-t3fPU07CA.webp",
    # 혼합
    "눔바니": "https://i.namu.wiki/i/KJXTz9hVqeoNgFjAn7ao1u5TXj6M9QIQbIT_FSSIMurigLbFjBJYIfqgvye4Uywt-J14WCHNOeZrs2MhY2OpWHgmlgO47oElIYUEK2qVEktSN8feUpSjNVgqfE5GYsJjPbUHUBtssnKpSgAaLnWxjQ.webp",
    "미드타운": "https://i.namu.wiki/i/fRD5ffXB1WpMXcrSe0l5LruHgkp4HKg-qUlQGVRDzlr_5VNxy_5Z5_mLMktclKs5TGXw41sPsN6YVoWHGiCJvJsOGej5mbCQTMEFhjyL5LkswpoNOVF8F_RAekapGj7rulIjg4aTn8jcqmopccaqhA.webp",
    "블리자드 월드": "https://i.namu.wiki/i/gdcisiONMZ_pZ8hyiMphyVegcsjEZx-jr_itPziBvByO3MB31FPAvSHnxV8DF-mhWSJEGFZtBBNx4F3KPDLetfIEqkz2-iGe7rVMVqenhkEVlH8UOZEMvSRTSok_MsVENGmU6nsV_Em7WVtIfM7z-A.webp",
    "아이헨발데": "https://i.namu.wiki/i/q-KHUGXWozoTmfAmTE87qnLwqmBhZdiuhb-bTq-IgGsg-i33kZ_iT5EFpnTxRCIvhrtNumWjcf2IPUhKF83Q2cbWLCA86je1DCceTbTtCAogVnr0EuOxipJQER9gSLBMwN4u_MWfSUg-XLln4DUkWA.webp",
    "왕의 길": "https://i.namu.wiki/i/_rk99NEG0EmFWfTjQHkI6vx6UyULYtoKIgFNunLcBwfa97OvOPMnFejA9_K1guPxoVY7GTw20adJrhnRKE8g3c3tOe5GHm293AA9cWoxJk8zZpaz2JHyOk0CjO1c106bOYN08NcIY7gUeYXdJHz7lg.webp",
    "파라이수": "https://i.namu.wiki/i/oIF1xdZwHvXd-XaHh14b8-bc3D8EYT_yQzgUbXRb5cr-aQaBTmEc5MD-E8MDNyfD6V3h9NPganEnor-stEL3M4Ed8x7nj6KVeg44RuSw2nSpRagcOVfYt6G_9Yxh2MNj1Tt-eXaPIXiPhQEhDOnd0Q.webp",
    "할리우드": "https://i.namu.wiki/i/kuJRIQOcveITJwj_XVFwuAynmlGrzRZziRkrA9E_FgZyxSouj-4KMYb8E7yVCEPXxnMa072KWvkm3ch-TqVixdqly_S2qOdVGz15rPyqresfBKqUiMKVyvNIRIs0gwFGoFwmIpsOXVney84ilse40Q.webp",
    # 쟁탈
    "남극 반도": "https://i.namu.wiki/i/2c1tx1KuIVkmAxFfXEaKueqIB8Kh3tEVZPa3F4pq48mWXhMjRxIi1T2i53tu7mQPxO5fDndfMPFibNv0cgHLKyXvqQI4G--0SwjBqV3V4USDDS6CytIQ56a6Z_qHR1tvVVZh_KzIsul6DUfAi24zRg.webp",
    "네팔": "https://i.namu.wiki/i/xEuoB4uY96l2rNqTYEgPmTKtSXY-wcdlpoPit7iPk-cz-Fl8YFeCnJsDh4XjChHREeERPDlhvdGlPLhDw9jHJY2rmN81unzaL9ZR99wGJf8f9kIpWNK_NBhKbzTwu8LAWk7R3HlrdgnlJBLLV49Z1w.webp",
    "리장 타워": "https://i.namu.wiki/i/XAmlHOtXXA0d1RQw4QKB9ZUBB8CmB3t_beevRIDAQpE9cwXDqQnC8qOoa48BiV9HwZWjEfSug3V5qp-U0y5ZVTwlZJOg45p4u1mi8y5OuomscJhHMkJ55BZ6m4XAc5I4y0WOhPH5digRjc-QV2IZkw.webp",
    "사모아": "https://i.namu.wiki/i/ePydQBMVTqxYAkONdKY90hXUp9hCSYtb6LxTH1_nyQ7lD-3_0EBI5bGogsMQL4AOYZgtnvktcGKTGTS8BnyylaK6GUy26OFN_-mR-2DC7U8NMVPNqqswDKkU1E6QkEtthjPE_k9rC14hXKmH2lQA-A.webp",
    "부산": "https://i.namu.wiki/i/om99tfzoD7sSXIvQ6TE03p199amjaruoyk4O7xXIiJUlg_qeDewjx4edm4pPzE1rQhpx8kbVH2uKvYabPEhU6oVL0tp1z9NNXhwOCKrwqn2CFiU3O84L8IF9iK990b2RwUNtvnOJRyXj-00yjVp0yQ.webp",
    "오아시스": "https://i.namu.wiki/i/h7xmQjn2zvwuhbgWdPIafvNCvKuyOP9tEgTSO2HI0eExLNgpH8Q9IZk9U0LTvCOXZT5xCMhJqEzysFGcv3Vui2Ns9k99l8qOeTQO6p9V7-WdJr94Kctt-Tn8atrmCKtb3qHiZMK3srbPciIiK4fwvA.webp",
    "일리오스": "https://i.namu.wiki/i/Rv3gIfyRYMxky-wT_uxwaak5x7AviG31oyhXa9Ezl5WetAdpPD3c1wyx-tLKIOoYewkqQN9TSz5zLPaRhnhVIYO-gLkejzEcY2NUMQhg2mmREdZeJPHc2JieOv059ebq8w-2IBC0mGMjmde1yo2vtg.webp",
    # 밀기
    "뉴 퀸 스트리트": "https://i.namu.wiki/i/36AF5oSwOVRINiZswx2vrHVlemXK4bDSZjXihmwC3oTCiKgHzyqVdtO-jeca12bZ3WkgccR5RDByxAezmcT4EnGWMtn7MP49cKx-qMNs9VpqCGnouYSHbYCEzQDXsc9PBEJBt8c2-teb0slgEBESxw.webp",
    "루나사피": "https://i.namu.wiki/i/iO3Xftn5jx_jnBZ9s7XVVaqlDtQXdtqce8PrDRi7me43E1YUqRYMRZRlkVlFgVZcR5Ured-8vwoV1TRNY5RN_nCaUCFwyrPddxPXECWywb0v-eWpkwhIPTnD3zgAqSoRdL0MXsTurE7BETaWE6sejw.webp",
    "이스페란사": "https://i.namu.wiki/i/e-4MRjAHc7XIzsYcck5bAqKqYLIgAvwtS1SCidEod40omK0l91ucQACk9oDJNxDbkKX--jW86U86EYqKp-t4dbA2MWAJmOLTyNNH27XUYqzyNOU1I7cksfZvbfeR8LYwgNnCMZODlthFQp_fSbQnmA.webp",
    "콜로세오": "https://i.namu.wiki/i/1f-2qwjXNmuqzVBSjEo-fTupa66jX9XAwX6wEnFBXiNF1cEyXJWE67ddB9UonAWnJmE1rJaBISt33Lqo1hVi-JV0wTrejCuydSRE2797BLTHiip0_s5Jt5PGfVQKC9bWRcXVevwH4ryGakpAL-CYag.webp",
    # 플래시포인트
    "뉴 정크 시티": "https://i.namu.wiki/i/ygXLOVLBuEuC-MOsPQ7KagChnc4pjkUAN4YBg3oh6jkQ9kGbr_vFPUg9TpKZJFaD4AcGFJX7KLWUTn9nts_v9GZGO9D96cecw7Ue_FR6WmBMutnmEIKf-V_ThWuCcM4Qnm0uwxio5Jq8TX-JN7kWJg.webp",
    "수라바사": "https://i.namu.wiki/i/00L5OoijkxUfWXH9chvw0PdxCTJ_KfmZ8KZ70QKfIQbw0wsWBqYggZA-JzbgGcfYymFZyLVOJXlJpf1rpUgDkoSU9X_wc51FpLLsZK6k3iH7E39iB7A-mzdAAt9Bd6-DKaSw2Yc0lp089p-UXHgE4A.webp",
    "아틀리스": "https://i.namu.wiki/i/xsyZB9oK5zQSZ7uVHgmHbwGZ1imbLIF2SHfO0q4YqKgfq1N2qlN_BlxetBAoLXLHHXuXZiHYYnkz5VefvBecRygQmQzz__1vS-fCLE31Yilv33DP7IMTdtaSwgSSZqpVTz40lvFApVYM-RpCzaOXpg.webp"
}

# --- 💾 데이터 관리 및 관리자 확인 함수 ---
def load_data(file_name):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(file_name, data):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def is_admin(ctx):
    # 디스코드 자체 서버 관리자이거나, config.json에 등록된 봇 관리자인 경우 승인
    if ctx.author.guild_permissions.administrator:
        return True
    config = load_data(CONFIG_FILE)
    if str(ctx.author.id) in config.get('admins', []):
        return True
    return False

@bot.event
async def on_ready():
    print('=========================')
    print(f'로그인 성공: {bot.user.name}')
    print('오버워치 내전 마스터 봇 (관리자 통제형) 온라인!')
    print('=========================')

# --- 👑 관리자 권한 및 유틸리티 명령어 ---
@bot.command(name='관리자추가')
async def add_admin(ctx, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("❌ 관리자만 이 명령어를 사용할 수 있습니다.")
    
    config = load_data(CONFIG_FILE)
    admins = config.get('admins', [])
    if str(member.id) not in admins:
        admins.append(str(member.id))
        config['admins'] = admins
        save_data(CONFIG_FILE, config)
    await ctx.send(f"✅ **{member.display_name}** 님이 봇 관리자로 등록되었습니다.")

@bot.command(name='청소')
async def clear_messages(ctx, amount: int):
    if not is_admin(ctx):
        return await ctx.send("❌ 관리자 권한이 없습니다.")
    if amount < 1:
        return await ctx.send("❌ 1 이상의 숫자를 입력해 주세요.")
    
    # 명령어 본인 포함해서 삭제
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 최근 채팅 **{amount}개**를 깔끔하게 지웠습니다!")
    await msg.delete(delay=3)

@bot.command(name='명령어')
async def show_help(ctx):
    embed = discord.Embed(title="🤖 오버워치 내전 봇 안내서", color=discord.Color.gold())
    embed.add_field(name="`!내전시작` (관리자)", value="대기실 인원을 바탕으로 팀을 나누고 자동 이동을 돕습니다.", inline=False)
    embed.add_field(name="`!대기실복귀` (관리자)", value="팀 채널에 흩어진 유저들을 대기실로 일괄 소환합니다.", inline=False)
    embed.add_field(name="`!청소 [숫자]` (관리자)", value="입력한 숫자만큼 위의 채팅을 깔끔하게 삭제합니다.", inline=False)
    embed.add_field(name="`!맵` (누구나)", value="전장 모드 및 개별 맵을 선택하거나 룰렛을 돌립니다.", inline=False)
    embed.add_field(name="`!점수등록 @유저 점수` (관리자)", value="유저의 밸런스 점수를 세팅합니다.", inline=False)
    embed.add_field(name="`!내점수` (누구나)", value="본인의 등록된 점수를 확인합니다. (5초 뒤 삭제)", inline=False)
    embed.add_field(name="`!대기실설정` / `!팀채널설정 [1~4]` (관리자)", value="내전용 음성 채널들을 지정합니다.", inline=False)
    embed.add_field(name="`!관리자추가 @유저` (관리자)", value="해당 유저에게 봇 제어 권한을 줍니다.", inline=False)
    embed.add_field(name="`!귀여워` (누구나)", value="귀여운 이스터에그를 확인합니다.", inline=False)
    
    await ctx.send(embed=embed)

# --- 📊 점수 및 채널 설정 명령어 ---
@bot.command(name='점수등록')
async def register_score(ctx, member: discord.Member, score: int):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    scores = load_data(SCORE_FILE)
    scores[str(member.id)] = score
    save_data(SCORE_FILE, scores)
    await ctx.send(f'✅ **{member.display_name}** 님의 점수가 **{score}점**으로 등록되었습니다!')

@bot.command(name='내점수')
async def check_my_score(ctx):
    scores = load_data(SCORE_FILE)
    user_id = str(ctx.author.id)
    if user_id in scores:
        await ctx.send(f'📊 **{ctx.author.display_name}** 님의 점수는 **{scores[user_id]}점**입니다.', delete_after=5.0)
    else:
        await ctx.send(f'❌ **{ctx.author.display_name}** 님은 등록된 점수가 없습니다.', delete_after=5.0)
    try:
        await ctx.message.delete()
    except:
        pass

@bot.command(name='대기실설정')
async def set_lobby(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    if ctx.author.voice is None: return await ctx.send("❌ 먼저 음성 채널에 입장해 주세요.")
    config = load_data(CONFIG_FILE)
    config['lobby_id'] = ctx.author.voice.channel.id
    save_data(CONFIG_FILE, config)
    await ctx.send(f'📢 **{ctx.author.voice.channel.name}** 채널이 [대기실]로 등록되었습니다.')

@bot.command(name='팀채널설정')
async def set_team_channel(ctx, team_num: int):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    if ctx.author.voice is None: return await ctx.send("❌ 먼저 음성 채널에 입장해 주세요.")
    config = load_data(CONFIG_FILE)
    if 'team_channels' not in config: config['team_channels'] = {}
    config['team_channels'][str(team_num)] = ctx.author.voice.channel.id
    save_data(CONFIG_FILE, config)
    await ctx.send(f'📢 **{ctx.author.voice.channel.name}** 채널이 [{team_num}팀 채널]로 등록되었습니다.')

@bot.command(name='대기실복귀')
async def return_to_lobby(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    config = load_data(CONFIG_FILE)
    lobby_id = config.get('lobby_id')
    team_channels = config.get('team_channels', {})
    
    if not lobby_id: return await ctx.send("❌ 대기실이 설정되지 않았습니다.")
    lobby_channel = bot.get_channel(int(lobby_id))
    
    status_msg = await ctx.send("⏳ 흩어진 유저들을 대기실로 불러오는 중입니다...")
    move_success, move_fail = 0, 0

    for team_num, channel_id in team_channels.items():
        t_channel = bot.get_channel(int(channel_id))
        if t_channel:
            for member in t_channel.members:
                if not member.bot:
                    try:
                        await member.move_to(lobby_channel)
                        move_success += 1
                    except:
                        move_fail += 1

    await status_msg.edit(content=f"✅ 총 **{move_success}명** 대기실 복귀 완료! (실패: {move_fail}명)")


# --- 🗺️ 전장 룰렛 UI ---
class MapDetailSelect(discord.ui.Select):
    def __init__(self, mode):
        self.mode = mode
        options = [discord.SelectOption(label="🎲 해당 모드 내 무작위", value="랜덤")]
        for m in OW_MAPS[mode]:
            options.append(discord.SelectOption(label=m, value=m))
        super().__init__(placeholder=f"{mode} 전장을 고르거나 랜덤을 돌리세요...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "랜덤":
            result_map = random.choice(OW_MAPS[self.mode])
            embed = discord.Embed(title=f"🎲 [{self.mode}] 무작위 룰렛 결과!", description=f"이번 내전은 **{result_map}**에서 진행됩니다.", color=discord.Color.purple())
        else:
            result_map = selected
            embed = discord.Embed(title=f"✅ [{self.mode}] 전장 확정!", description=f"이번 내전은 **{result_map}**에서 진행됩니다.", color=discord.Color.green())
        
        if result_map in MAP_IMAGES:
            embed.set_image(url=MAP_IMAGES[result_map])
        await interaction.response.edit_message(embed=embed, view=None)

class MapModeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="호위", value="호위"), discord.SelectOption(label="혼합", value="혼합"),
            discord.SelectOption(label="쟁탈", value="쟁탈"), discord.SelectOption(label="밀기", value="밀기"),
            discord.SelectOption(label="플래시포인트", value="플래시포인트"), discord.SelectOption(label="🎲 전체 랜덤", value="전체랜덤")
        ]
        super().__init__(placeholder="플레이할 모드를 먼저 선택하세요...", options=options)

    async def callback(self, interaction: discord.Interaction):
        mode = self.values[0]
        if mode == "전체랜덤":
            all_maps = [m for maps in OW_MAPS.values() for m in maps]
            result_map = random.choice(all_maps)
            found_mode = [k for k, v in OW_MAPS.items() if result_map in v][0]
            
            embed = discord.Embed(title="🎲 전체 무작위 룰렛 결과!", description=f"**[{found_mode}]** 모드의 **{result_map}**에서 진행합니다.", color=discord.Color.gold())
            if result_map in MAP_IMAGES: embed.set_image(url=MAP_IMAGES[result_map])
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(title=f"🗺️ {mode} 전장 선택", description="아래 메뉴에서 전장을 골라주세요.", color=discord.Color.blue())
            if mode in MODE_IMAGES: embed.set_image(url=MODE_IMAGES[mode])
            view = discord.ui.View()
            view.add_item(MapDetailSelect(mode))
            await interaction.response.edit_message(embed=embed, view=view)

@bot.command(name='맵')
async def select_map(ctx):
    embed = discord.Embed(title="🗺️ 내전 전장 선택기", description="어떤 모드로 진행할지 아래 메뉴에서 골라주세요.", color=discord.Color.dark_gray())
    embed.set_image(url=MODE_IMAGES["전체"])
    view = discord.ui.View()
    view.add_item(MapModeSelect())
    await ctx.send(embed=embed, view=view)


# --- 👥 팀 교환 전용 뷰 (다중 선택 금지 적용) ---
class SwapView(discord.ui.View):
    def __init__(self, teams, team_channels, team_count, members):
        super().__init__(timeout=None)
        self.teams = teams
        self.team_channels = team_channels
        self.team_count = team_count
        self.members = members
        
        # 현재 모든 팀원 목록을 불러옵니다.
        options = []
        for team in self.teams:
            for p in team:
                options.append(discord.SelectOption(label=p.display_name, value=str(p.id)))
        
        # 다중 선택을 막기 위해 A유저, B유저 선택기를 2개로 분리했습니다.
        self.select_1 = discord.ui.Select(placeholder="🔄 바꿀 첫 번째 유저 선택...", options=options, custom_id="swap_1")
        self.select_2 = discord.ui.Select(placeholder="🔄 바꿀 두 번째 유저 선택...", options=options, custom_id="swap_2")
        
        # (선택만 하고 동작은 안 함, 버튼을 눌러야 실행)
        async def dummy_callback(interaction): await interaction.response.defer()
        self.select_1.callback = dummy_callback
        self.select_2.callback = dummy_callback

        self.add_item(self.select_1)
        self.add_item(self.select_2)

    @discord.ui.button(label="🔄 교환 실행", style=discord.ButtonStyle.green, row=2)
    async def execute_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.select_1.values or not self.select_2.values:
            return await interaction.response.send_message("❌ 두 명의 유저를 모두 선택해 주세요!", ephemeral=True)
        
        u1_id = self.select_1.values[0]
        u2_id = self.select_2.values[0]

        if u1_id == u2_id:
            return await interaction.response.send_message("❌ 서로 다른 두 명을 선택해 주세요!", ephemeral=True)
        
        # 유저들의 팀 인덱스 찾기
        u1_pos, u2_pos = None, None
        for t_idx, team in enumerate(self.teams):
            for p_idx, p in enumerate(team):
                if str(p.id) == u1_id: u1_pos = (t_idx, p_idx)
                if str(p.id) == u2_id: u2_pos = (t_idx, p_idx)
        
        # 맞교환 로직
        p1 = self.teams[u1_pos[0]][u1_pos[1]]
        p2 = self.teams[u2_pos[0]][u2_pos[1]]
        self.teams[u1_pos[0]][u1_pos[1]] = p2
        self.teams[u2_pos[0]][u2_pos[1]] = p1
        
        # 임베드 재계산 및 뷰 복귀
        scores = load_data(SCORE_FILE)
        result_embed = discord.Embed(title="🎲 내전 팀 구성 결과 (수동 교체 완료!)", color=discord.Color.teal())
        team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        
        for i in range(self.team_count):
            team_score = sum(scores.get(str(p.id), 0) for p in self.teams[i])
            avg_score = int(team_score / len(self.teams[i])) if self.teams[i] else 0
            names = [p.display_name for p in self.teams[i]]
            result_embed.add_field(name=f"{team_colors[i]} (평균 {avg_score}점)", value=", ".join(names) if names else "없음", inline=False)
        
        new_view = MoveConfirmView(self.teams, self.team_channels, self.team_count, self.members)
        await interaction.response.edit_message(content="✅ 유저 맞교환이 완료되었습니다!", embed=result_embed, view=new_view)

    @discord.ui.button(label="↩️ 취소 및 돌아가기", style=discord.ButtonStyle.gray, row=2)
    async def cancel_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        scores = load_data(SCORE_FILE)
        result_embed = discord.Embed(title="🎲 내전 팀 구성 결과", color=discord.Color.blue())
        team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        
        for i in range(self.team_count):
            team_score = sum(scores.get(str(p.id), 0) for p in self.teams[i])
            avg_score = int(team_score / len(self.teams[i])) if self.teams[i] else 0
            names = [p.display_name for p in self.teams[i]]
            result_embed.add_field(name=f"{team_colors[i]} (평균 {avg_score}점)", value=", ".join(names) if names else "없음", inline=False)

        new_view = MoveConfirmView(self.teams, self.team_channels, self.team_count, self.members)
        await interaction.response.edit_message(content="✅ 교환을 취소했습니다.", embed=result_embed, view=new_view)


# --- ⚖️ 팀 나누기 UI (이동 여부 및 교체 버튼 포함) ---
class MoveConfirmView(discord.ui.View):
    def __init__(self, teams, team_channels, team_count, members):
        super().__init__(timeout=None)
        self.teams = teams
        self.team_channels = team_channels
        self.team_count = team_count
        self.members = members

    @discord.ui.button(label="🚀 유저 자동 이동", style=discord.ButtonStyle.green)
    async def confirm_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content="⏳ 유저들을 각 팀 채널로 이동시키는 중입니다...", view=self)

        move_success, move_fail = 0, 0
        for i in range(len(self.teams)):
            target_channel_id = self.team_channels.get(str(i + 1))
            if target_channel_id:
                target_channel = bot.get_channel(int(target_channel_id))
                if target_channel:
                    for player in self.teams[i]:
                        if player.voice and player.voice.channel:
                            try:
                                await player.move_to(target_channel)
                                move_success += 1
                            except: move_fail += 1
                        else: move_fail += 1

        status_text = f"✅ 팀 구성 및 이동 완료! (성공: {move_success}명)"
        if move_fail > 0: status_text += f"\n⚠️ 이동 실패: {move_fail}명 (채널을 나갔거나 권한 부족)"
        await interaction.message.edit(content=status_text, view=self)

    @discord.ui.button(label="🔄 랜덤 다시 짜기", style=discord.ButtonStyle.blurple)
    async def reroll_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        scores = load_data(SCORE_FILE)
        player_data = []
        for m in self.members:
            if str(m.id) in scores:
                variation = random.randint(-150, 150)
                player_data.append((m, scores[str(m.id)], scores[str(m.id)] + variation))

        player_data.sort(key=lambda x: x[2], reverse=True)
        new_teams = [[] for _ in range(self.team_count)]
        team_scores = [0] * self.team_count

        for player, actual_score, _ in player_data:
            min_team_idx = team_scores.index(min(team_scores))
            new_teams[min_team_idx].append(player)
            team_scores[min_team_idx] += actual_score

        self.teams = new_teams
        result_embed = discord.Embed(title="🎲 내전 팀 구성 결과 (재배치 완료!)", color=discord.Color.purple())
        team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        
        for i in range(self.team_count):
            avg_score = int(team_scores[i] / len(self.teams[i])) if self.teams[i] else 0
            names = [p.display_name for p in self.teams[i]]
            result_embed.add_field(name=f"{team_colors[i]} (평균 {avg_score}점)", value=", ".join(names) if names else "없음", inline=False)

        await interaction.response.edit_message(content="🔄 팀을 다시 구성했습니다!", embed=result_embed, view=self)

    # 💡 3. 수동 팀원 교체 진입 버튼
    @discord.ui.button(label="👥 수동 팀원 교체", style=discord.ButtonStyle.secondary)
    async def manual_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        swap_view = SwapView(self.teams, self.team_channels, self.team_count, self.members)
        await interaction.response.edit_message(
            content="🔄 아래 두 개의 메뉴에서 맞바꿀 사람을 각각 한 명씩 선택한 뒤 [교환 실행]을 눌러주세요.", 
            view=swap_view
        )

    @discord.ui.button(label="❌ 이동 안 함", style=discord.ButtonStyle.gray)
    async def cancel_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content="✅ 채널 이동 없이 팀 구성만 마무리되었습니다.", view=self)

class TeamDivideButton(discord.ui.Button):
    def __init__(self, team_count, members):
        super().__init__(label="🎲 팀 나누기 결과 보기", style=discord.ButtonStyle.primary)
        self.team_count = team_count
        self.members = members

    async def callback(self, interaction: discord.Interaction):
        scores = load_data(SCORE_FILE)
        config = load_data(CONFIG_FILE)
        team_channels = config.get('team_channels', {})
        
        player_data, unregistered = [], []
        for m in self.members:
            if str(m.id) in scores: player_data.append((m, scores[str(m.id)]))
            else: unregistered.append(m.display_name)

        if unregistered:
            return await interaction.response.send_message(f"❌ 점수 미등록자가 있습니다: {', '.join(unregistered)}", ephemeral=True)

        player_data.sort(key=lambda x: x[1], reverse=True)
        teams = [[] for _ in range(self.team_count)]
        team_scores = [0] * self.team_count

        for player, score in player_data:
            min_team_idx = team_scores.index(min(team_scores))
            teams[min_team_idx].append(player)
            team_scores[min_team_idx] += score

        result_embed = discord.Embed(title="🎲 내전 팀 구성 결과", color=discord.Color.blue())
        team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        
        for i in range(self.team_count):
            avg_score = int(team_scores[i] / len(teams[i])) if teams[i] else 0
            names = [p.display_name for p in teams[i]]
            result_embed.add_field(name=f"{team_colors[i]} (평균 {avg_score}점)", value=", ".join(names) if names else "없음", inline=False)

        move_view = MoveConfirmView(teams, team_channels, self.team_count, self.members)
        await interaction.response.edit_message(content="✅ 팀 구성이 완료되었습니다!", embed=result_embed, view=move_view)

class TeamCountSelect(discord.ui.Select):
    def __init__(self, members):
        options = [
            discord.SelectOption(label="2개 팀으로 나누기", value="2"),
            discord.SelectOption(label="3개 팀으로 나누기", value="3"),
            discord.SelectOption(label="4개 팀으로 나누기", value="4"),
        ]
        super().__init__(placeholder="몇 개 팀으로 나눌지 선택하세요...", options=options)
        self.members = members

    async def callback(self, interaction: discord.Interaction):
        team_count = int(self.values[0])
        view = discord.ui.View()
        view.add_item(TeamDivideButton(team_count, self.members))
        await interaction.response.edit_message(content=f"👥 **선택된 팀 개수:** {team_count}개 팀\n[팀 나누기 결과 보기]를 눌러주세요.", view=view)

@bot.command(name='내전시작')
async def start_civil_war(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    config = load_data(CONFIG_FILE)
    lobby_id = config.get('lobby_id')
    
    if not lobby_id: return await ctx.send("❌ 대기실 채널이 설정되지 않았습니다.")
    lobby_channel = bot.get_channel(int(lobby_id))
    
    members = [m for m in lobby_channel.members if not m.bot]
    if len(members) == 0: return await ctx.send("❌ 대기실에 접속해 있는 유저가 없습니다!")

    view = discord.ui.View()
    view.add_item(TeamCountSelect(members))
    await ctx.send(f"📋 **현재 대기실 인원:** {len(members)}명\n아래 메뉴에서 팀 개수를 골라주세요.", view=view)

# --- 귀여운 이스터에그 명령어 ---
@bot.command(name='귀여워')
async def show_cute_instagram(ctx):
    await ctx.send("🐾 https://www.instagram.com/i.rang0321/")

token = os.environ.get('BOT_TOKEN')

if not token and os.path.exists('token.txt'):
    with open('token.txt', 'r', encoding='utf-8') as f:
        token = f.read().strip()

if token:
    bot.run(token)
else:
    print("❌ 토큰을 찾을 수 없습니다. token.txt 파일이 제대로 있는지 확인해 주세요.")
