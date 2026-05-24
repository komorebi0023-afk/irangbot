import discord
from discord.ext import commands
import random
import json
import os
import gspread
from google.oauth2.service_account import Credentials

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

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

# --- 데이터 관리 ---
def load_data(file_name):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(file_name, data):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def is_admin(ctx):
    if ctx.author.guild_permissions.administrator: return True
    config = load_data(CONFIG_FILE)
    if str(ctx.author.id) in config.get('admins', []): return True
    return False

@bot.event
async def on_ready():
    print(f'로그인 성공: {bot.user.name} | 구글 시트 연동 준비 완료!')

# --- 👑 구글 시트 동기화 (새로운 핵심 기능) ---
# --- 👑 구글 시트 동기화 (보안 패치 완료) ---
@bot.command(name='점수동기화')
async def sync_scores(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자만 사용할 수 있습니다.")
    
    if not os.path.exists('credentials.json'):
        return await ctx.send("❌ 서버에 `credentials.json` 열쇠 파일이 없습니다!")
    
    status_msg = await ctx.send("⏳ 구글 시트에서 최신 데이터를 불러오는 중입니다...")
    
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
        client = gspread.authorize(creds)
        
        # 💡 [보안 수정] 코드에 직접 적지 않고 환경변수나 sheet_key.txt 파일에서 키값을 가져옵니다.
        sheet_key = os.environ.get('SHEET_KEY')
        if not sheet_key and os.path.exists('sheet_key.txt'):
            with open('sheet_key.txt', 'r', encoding='utf-8') as f:
                sheet_key = f.read().strip()
                
        if not sheet_key:
            return await status_msg.edit(content="❌ 시트 키값을 찾을 수 없습니다. 서버에 `sheet_key.txt` 파일이 있는지 확인해 주세요.")
        
        spreadsheet = client.open_by_key(sheet_key)
        worksheet = spreadsheet.get_worksheet(0)
        rows = worksheet.get_all_values()
        
        synced_data = {}
        # 6번째 줄(index 5)부터 데이터 읽기
        for i in range(5, len(rows)):
            row = rows[i]
            if len(row) < 2 or not row[1].strip().isdigit(): continue # B열 ID 검증
            
            discord_id = str(row[1]).strip()
            
            # 각 열의 데이터 파싱 (비어있으면 "-" 처리)
            try: score = float(row[10]) if len(row) > 10 and row[10].strip() else 0.0
            except: score = 0.0
            
            synced_data[discord_id] = {
                "score": score,
                "battletag": row[3] if len(row) > 3 and row[3] else "-",
                "nickname": row[4] if len(row) > 4 and row[4] else "-",
                "main_pos": row[5] if len(row) > 5 and row[5] else "-",
                "sub_pos": row[6] if len(row) > 6 and row[6] else "-",
                "max_tier": row[7] if len(row) > 7 and row[7] else "-",
                "current_tier": row[8] if len(row) > 8 and row[8] else "-",
                "main_hero": row[9] if len(row) > 9 and row[9] else "-"
            }
            
        save_data(SCORE_FILE, synced_data)
        await status_msg.edit(content=f"✅ 구글 시트 동기화 완료! 총 **{len(synced_data)}명**의 최신 프로필을 저장했습니다.")
    except Exception as e:
        await status_msg.edit(content=f"❌ 동기화 실패! 에러 발생:\n```{e}```")
# --- 📊 프로필 확인 (업그레이드) ---
@bot.command(name='점수')
async def check_profile(ctx, member: discord.Member = None):
    target = member or ctx.author
    scores = load_data(SCORE_FILE)
    user_id = str(target.id)

    if user_id in scores:
        data = scores[user_id]
        embed = discord.Embed(title=f"📋 {target.display_name} 님의 내전 프로필", color=discord.Color.blue())
        
        embed.add_field(name="🎯 내전 점수", value=f"**{data['score']} 점**", inline=False)
        embed.add_field(name="오버워치 닉네임", value=data['nickname'], inline=True)
        embed.add_field(name="배틀태그", value=data['battletag'], inline=True)
        embed.add_field(name="주 영웅", value=data['main_hero'], inline=True)
        embed.add_field(name="주 포지션", value=data['main_pos'], inline=True)
        embed.add_field(name="보조 포지션", value=data['sub_pos'], inline=True)
        embed.add_field(name="최고 티어", value=data['max_tier'], inline=True)
        embed.add_field(name="현재 티어", value=data['current_tier'], inline=True)
        
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ **{target.display_name}** 님의 데이터가 구글 시트에 없거나 아직 동기화되지 않았습니다.")


# --- 기존 관리자/유틸 명령어들 ---
@bot.command(name='청소')
async def clear_messages(ctx, amount: int):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    await ctx.channel.purge(limit=amount + 1)

@bot.command(name='관리자추가')
async def add_admin(ctx, member: discord.Member):
    if not is_admin(ctx): return
    config = load_data(CONFIG_FILE)
    admins = config.get('admins', [])
    if str(member.id) not in admins:
        admins.append(str(member.id))
        config['admins'] = admins
        save_data(CONFIG_FILE, config)
    await ctx.send(f"✅ **{member.display_name}** 님이 봇 관리자로 등록되었습니다.")

@bot.command(name='명령어')
async def show_help(ctx):
    embed = discord.Embed(title="🤖 내전 마스터 봇 안내서", color=discord.Color.gold())
    embed.add_field(name="`!점수동기화` (관리자)", value="구글 시트의 정보를 실시간으로 봇에 덮어씌웁니다.", inline=False)
    embed.add_field(name="`!점수` / `!점수 @유저`", value="유저의 상세 내전 프로필과 점수를 확인합니다.", inline=False)
    embed.add_field(name="`!내전시작` (관리자)", value="팀 자동 분배 및 음성 채널 배치를 진행합니다.", inline=False)
    embed.add_field(name="`!맵`", value="내전 전장 선택 및 룰렛을 돌립니다.", inline=False)
    await ctx.send(embed=embed)

# 채널 설정 및 이동
@bot.command(name='대기실설정')
async def set_lobby(ctx):
    if not is_admin(ctx) or not ctx.author.voice: return
    config = load_data(CONFIG_FILE)
    config['lobby_id'] = ctx.author.voice.channel.id
    save_data(CONFIG_FILE, config)
    await ctx.send(f'📢 **{ctx.author.voice.channel.name}** 채널 [대기실] 등록 완료.')

@bot.command(name='팀채널설정')
async def set_team_channel(ctx, team_num: int):
    if not is_admin(ctx) or not ctx.author.voice: return
    config = load_data(CONFIG_FILE)
    if 'team_channels' not in config: config['team_channels'] = {}
    config['team_channels'][str(team_num)] = ctx.author.voice.channel.id
    save_data(CONFIG_FILE, config)
    await ctx.send(f'📢 **{ctx.author.voice.channel.name}** 채널 [{team_num}팀] 등록 완료.')


# --- 👥 팀 교환 / 내전 팀 나누기 시스템 ---
# (이전 코드와 동일한 맵 UI, 스왑 기능 축약 생략 없이 작성)
class SwapView(discord.ui.View):
    def __init__(self, teams, team_channels, team_count, members):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.team_count, self.members = teams, team_channels, team_count, members
        options = [discord.SelectOption(label=p.display_name, value=str(p.id)) for t in teams for p in t]
        
        self.s1 = discord.ui.Select(placeholder="🔄 바꿀 첫 번째 유저...", options=options, custom_id="swap_1")
        self.s2 = discord.ui.Select(placeholder="🔄 바꿀 두 번째 유저...", options=options, custom_id="swap_2")
        async def dummy(interaction): await interaction.response.defer()
        self.s1.callback = self.s2.callback = dummy
        self.add_item(self.s1); self.add_item(self.s2)

    @discord.ui.button(label="🔄 교환 실행", style=discord.ButtonStyle.green, row=2)
    async def execute_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.s1.values or not self.s2.values or self.s1.values[0] == self.s2.values[0]:
            return await interaction.response.send_message("❌ 서로 다른 두 명을 선택해 주세요!", ephemeral=True)
        
        u1_id, u2_id = self.s1.values[0], self.s2.values[0]
        u1_pos, u2_pos = None, None
        
        for t_idx, team in enumerate(self.teams):
            for p_idx, p in enumerate(team):
                if str(p.id) == u1_id: u1_pos = (t_idx, p_idx)
                if str(p.id) == u2_id: u2_pos = (t_idx, p_idx)
                
        p1, p2 = self.teams[u1_pos[0]][u1_pos[1]], self.teams[u2_pos[0]][u2_pos[1]]
        self.teams[u1_pos[0]][u1_pos[1]], self.teams[u2_pos[0]][u2_pos[1]] = p2, p1
        
        scores = load_data(SCORE_FILE)
        embed = discord.Embed(title="🎲 내전 팀 구성 결과 (수동 교체 완료!)", color=discord.Color.teal())
        team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        
        for i in range(self.team_count):
            t_score = sum(scores.get(str(p.id), {}).get("score", 0) for p in self.teams[i])
            avg = round(t_score / len(self.teams[i]), 1) if self.teams[i] else 0
            names = [p.display_name for p in self.teams[i]]
            embed.add_field(name=f"{team_colors[i]} (평균 {avg}점)", value=", ".join(names) if names else "없음", inline=False)
            
        await interaction.response.edit_message(content="✅ 교환 완료!", embed=embed, view=MoveConfirmView(self.teams, self.team_channels, self.team_count, self.members))

    @discord.ui.button(label="↩️ 취소", style=discord.ButtonStyle.gray, row=2)
    async def cancel_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="취소됨", view=MoveConfirmView(self.teams, self.team_channels, self.team_count, self.members))


class MoveConfirmView(discord.ui.View):
    def __init__(self, teams, team_channels, team_count, members):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.team_count, self.members = teams, team_channels, team_count, members

    @discord.ui.button(label="🚀 유저 자동 이동", style=discord.ButtonStyle.green)
    async def confirm_move(self, interaction, button):
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content="⏳ 채널 이동 중...", view=self)
        for i, team in enumerate(self.teams):
            ch_id = self.team_channels.get(str(i + 1))
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if p.voice: 
                        try: await p.move_to(bot.get_channel(int(ch_id)))
                        except: pass
        await interaction.message.edit(content="✅ 이동 완료!")

    @discord.ui.button(label="🔄 다시 밸런스 짜기", style=discord.ButtonStyle.blurple)
    async def reroll_teams(self, interaction, button):
        scores = load_data(SCORE_FILE)
        p_data = []
        for m in self.members:
            if str(m.id) in scores:
                actual = scores[str(m.id)].get("score", 0)
                # 💡 최대 10점 체계에 맞춰 오차 범위를 ±1.0으로 수정했습니다!
                variation = random.uniform(-1.0, 1.0)
                p_data.append((m, actual, actual + variation))
                
        p_data.sort(key=lambda x: x[2], reverse=True)
        new_teams = [[] for _ in range(self.team_count)]
        t_scores = [0] * self.team_count
        
        for p, act, _ in p_data:
            idx = t_scores.index(min(t_scores))
            new_teams[idx].append(p)
            t_scores[idx] += act
            
        self.teams = new_teams
        embed = discord.Embed(title="🎲 내전 팀 구성 결과 (재배치!)", color=discord.Color.purple())
        colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        for i in range(self.team_count):
            avg = round(t_scores[i] / len(self.teams[i]), 1) if self.teams[i] else 0
            names = [p.display_name for p in self.teams[i]]
            embed.add_field(name=f"{colors[i]} (평균 {avg}점)", value=", ".join(names) if names else "없음", inline=False)
            
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="👥 수동 팀원 교체", style=discord.ButtonStyle.secondary)
    async def manual_swap(self, interaction, button):
        await interaction.response.edit_message(content="🔄 유저 맞교환을 진행합니다.", view=SwapView(self.teams, self.team_channels, self.team_count, self.members))

class TeamDivideButton(discord.ui.Button):
    def __init__(self, t_count, members):
        super().__init__(label="🎲 팀 나누기 실행", style=discord.ButtonStyle.primary)
        self.t_count, self.members = t_count, members

    async def callback(self, interaction):
        scores = load_data(SCORE_FILE)
        chans = load_data(CONFIG_FILE).get('team_channels', {})
        p_data, unreg = [], []
        
        for m in self.members:
            # 💡 바뀐 json 구조에 맞게 수정됨
            if str(m.id) in scores and "score" in scores[str(m.id)]:
                p_data.append((m, scores[str(m.id)]["score"]))
            else: unreg.append(m.display_name)
            
        if unreg: return await interaction.response.send_message(f"❌ 정보 미등록 유저: {', '.join(unreg)}\n관리자에게 `!점수동기화`를 요청하세요.", ephemeral=True)
        
        p_data.sort(key=lambda x: x[1], reverse=True)
        teams = [[] for _ in range(self.t_count)]
        t_scores = [0] * self.t_count
        
        for p, sc in p_data:
            idx = t_scores.index(min(t_scores))
            teams[idx].append(p)
            t_scores[idx] += sc
            
        embed = discord.Embed(title="🎲 내전 팀 결과", color=discord.Color.blue())
        colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        for i in range(self.t_count):
            avg = round(t_scores[i] / len(teams[i]), 1) if teams[i] else 0
            names = [p.display_name for p in teams[i]]
            embed.add_field(name=f"{colors[i]} (평균 {avg}점)", value=", ".join(names) if names else "없음", inline=False)
            
        await interaction.response.edit_message(embed=embed, view=MoveConfirmView(teams, chans, self.t_count, self.members))

class TeamCountSelect(discord.ui.Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=f"{i}개 팀으로 나누기", value=str(i)) for i in range(2, 5)]
        super().__init__(placeholder="팀 개수 선택...", options=options)
        self.members = members

    async def callback(self, interaction):
        view = discord.ui.View()
        view.add_item(TeamDivideButton(int(self.values[0]), self.members))
        await interaction.response.edit_message(content=f"👥 {self.values[0]}개 팀 선택됨.", view=view)

@bot.command(name='내전시작')
async def start_civil_war(ctx):
    if not is_admin(ctx): return
    cfg = load_data(CONFIG_FILE)
    if 'lobby_id' not in cfg: return await ctx.send("❌ 대기실 설정 필요")
    lobby = bot.get_channel(int(cfg['lobby_id']))
    mems = [m for m in lobby.members if not m.bot]
    if not mems: return await ctx.send("❌ 대기실 인원 없음")
    
    view = discord.ui.View()
    view.add_item(TeamCountSelect(mems))
    await ctx.send(f"📋 대기실 {len(mems)}명", view=view)


# --- 봇 실행 (토큰 안전 처리) ---
token = os.environ.get('BOT_TOKEN')
if not token and os.path.exists('token.txt'):
    with open('token.txt', 'r', encoding='utf-8') as f:
        token = f.read().strip()
        
if token: bot.run(token)
else: print("❌ 토큰을 찾을 수 없습니다.")
