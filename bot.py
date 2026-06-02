import discord
from discord.ext import commands
import random
import json
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

SCORE_FILE = 'scores.json'
CONFIG_FILE = 'config.json'
MATCH_FILE = 'latest_match.json'

# --- 🗺️ 전장 및 영웅 데이터 ---
OW_MAPS = {
    "호위": ["66번 국도", "감시기지: 지브롤터", "도라도", "리알토", "샴발리 수도원", "서킷 로얄", "쓰레기촌", "하바나"],
    "혼합": ["눔바니", "미드타운", "블리자드 월드", "아이헨발데", "왕의 길", "파라이수", "할리우드"],
    "쟁탈": ["남극 반도", "네팔", "리장 타워", "사모아", "부산", "오아시스", "일리오스"],
    "밀기": ["뉴 퀸 스트리트", "루나사피", "이스페란사", "콜로세오"],
    "플래시포인트": ["뉴 정크 시티", "수라바사", "아틀리스"]
}

OW_HEROES = {
    "돌격": ["D.Va", "둠피스트", "라마트라", "라인하르트", "레킹볼", "로드호그", "마우가", "시그마", "오리사", "자리야", "정커퀸", "윈스턴"],
    "공격": ["겐지", "리퍼", "메이", "바스티온", "벤처", "소전", "솔저: 76", "솜브라", "시메트라", "애쉬", "에코", "위도우메이커", "정크랫", "캐서디", "토르비욘", "트레이서", "파라", "한조"],
    "지원": ["라이프위버", "루시우", "메르시", "모이라", "바티스트", "브리기테", "아나", "일리아리", "젠야타", "주노", "키리코"]
}

MODE_IMAGES = {
    "전체": "https://cdn.discordapp.com/attachments/1508104373568274482/1508115279249543168/all.png?ex=6a145d4e&is=6a130bce&hm=49965cb1a19491d6534dcbb6961447bbb27d8c55925f45db0e359a56117abe04&",
    "호위": "https://cdn.discordapp.com/attachments/1508104373568274482/1508115373981962352/2026-05-24_232829.png?ex=6a145d64&is=6a130be4&hm=94ff9479b8b45ea5115c4e027f98a138313448ed5ab711b166c3e2a48fc7a5a0&",
    "혼합": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113692955377844/2026-05-24_232456.png?ex=6a145bd3&is=6a130a53&hm=07840c8ca8468e692c95f5326bbf3fdbe13e41ba91861c280f5120b2ddf4938c&",
    "쟁탈": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113692535816243/2026-05-24_232448.png?ex=6a145bd3&is=6a130a53&hm=8cd2a0e159ab37c1bca671369406d768e7f37075dd559bc5df27f0864b310113&",
    "밀기": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113693370617947/2026-05-24_232500.png?ex=6a145bd3&is=6a130a53&hm=8252787a0cd3ff362d9455915b3e670a3d5bb804ff48ebe2868e93f1b30de697&",
    "플래시포인트": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113693773398086/2026-05-24_232505.png?ex=6a145bd3&is=6a130a53&hm=458076f23beae0d09bb3bfe1593ac7eb811ff1dad65ed19d3f9b5e2337ee218e&"
}

# (임시 뼈대) 추후 방장님이 실제 개별 전장 링크로 교체하세요.
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

# --- 💾 데이터 관리 ---
def load_data(file_name):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_data(file_name, data):
    with open(file_name, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

def is_admin(ctx):
    if ctx.author.guild_permissions.administrator: return True
    config = load_data(CONFIG_FILE)
    if str(ctx.author.id) in config.get('admins', []): return True
    return False

def get_google_client():
    if not os.path.exists('credentials.json'): return None, None
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    client = gspread.authorize(creds)
    sheet_key = os.environ.get('SHEET_KEY')
    if not sheet_key and os.path.exists('sheet_key.txt'):
        with open('sheet_key.txt', 'r', encoding='utf-8') as f: sheet_key = f.read().strip()
    return client, sheet_key

@bot.event
async def on_ready():
    print(f'로그인 성공: {bot.user.name} | 모든 기능 통합 버전 가동!')

# --- 👑 1. 구글 시트 연동 및 전적 기록 ---
@bot.command(name='점수동기화')
async def sync_scores(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자만 사용할 수 있습니다.")
    client, sheet_key = get_google_client()
    if not client or not sheet_key: return await ctx.send("❌ 구글 시트 키값 또는 인증 파일이 없습니다.")
    
    status_msg = await ctx.send("⏳ 구글 시트에서 최신 데이터를 불러오는 중입니다...")
    try:
        spreadsheet = client.open_by_key(sheet_key)
        worksheet = spreadsheet.get_worksheet(0)
        rows = worksheet.get_all_values()
        
        synced_data = {}
        for i in range(5, len(rows)):
            row = rows[i]
            if len(row) < 2 or not row[1].strip().isdigit(): continue
            discord_id = str(row[1]).strip()
            
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
                "main_hero": row[9] if len(row) > 9 and row[9] else "-",
                "wins": row[11] if len(row) > 11 and row[11].isdigit() else "0",
                "losses": row[12] if len(row) > 12 and row[12].isdigit() else "0"
            }
        save_data(SCORE_FILE, synced_data)
        await status_msg.edit(content=f"✅ 구글 시트 동기화 완료! 총 **{len(synced_data)}명** 업데이트 완료.")
    except Exception as e:
        await status_msg.edit(content=f"❌ 동기화 실패:\n```{e}```")

@bot.command(name='내전종료')
async def end_civil_war(ctx, winner: str = None):
    if not is_admin(ctx): return
    if winner not in ["1팀", "2팀", "3팀", "4팀"]: return await ctx.send("❌ 올바른 승리 팀을 입력하세요. (예: `!내전종료 1팀`)")
        
    match_data = load_data(MATCH_FILE)
    if not match_data: return await ctx.send("❌ 최근 진행된 내전 기록이 없습니다. 먼저 `!내전시작`을 진행하세요.")
        
    client, sheet_key = get_google_client()
    if not client or not sheet_key: return await ctx.send("❌ 구글 시트 연동 오류.")
    
    status_msg = await ctx.send("⏳ 구글 시트 [전적] 탭에 결과를 기록하고 있습니다...")
    try:
        spreadsheet = client.open_by_key(sheet_key)
        try: record_sheet = spreadsheet.worksheet("전적")
        except: return await status_msg.edit(content="❌ 시트에 `전적`이라는 이름의 탭이 없습니다! 탭을 만들어 주세요.")
        
        kst_time = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        team1_names = ", ".join(match_data.get('team1_nicks', []))
        team2_names = ", ".join(match_data.get('team2_nicks', []))
        
        # A: 날짜 / B: 승리팀 / C: 1팀 멤버 / D: 2팀 멤버
        row_data = [kst_time, f"{winner} 승리", team1_names, team2_names]
        record_sheet.append_row(row_data)
        
        save_data(MATCH_FILE, {}) # 기록 후 초기화
        await status_msg.edit(content=f"🎉 **내전 결과 기록 완료!**\n> 🏆 **{winner}**의 승리로 전적 시트에 자동 저장되었습니다.")
    except Exception as e:
        await status_msg.edit(content=f"❌ 기록 실패:\n```{e}```")

# --- 🎯 2. 기본 유틸 및 명령어 (복구 완료) ---
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
        
        if data.get('wins') != "0" or data.get('losses') != "0":
            embed.add_field(name="🏆 누적 전적", value=f"{data.get('wins')}승 {data.get('losses')}패", inline=True)
            
        embed.add_field(name="주/보조 포지션", value=f"{data['main_pos']} / {data['sub_pos']}", inline=True)
        embed.add_field(name="티어 (최고/현재)", value=f"{data['max_tier']} / {data['current_tier']}", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ **{target.display_name}** 님의 데이터가 구글 시트에 없거나 동기화되지 않았습니다.")

@bot.command(name='귀여워')
async def show_cute_instagram(ctx):
    await ctx.send("🐾 https://www.instagram.com/i.rang0321/")

@bot.command(name='청소')
async def clear_messages(ctx, amount: int):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 최근 채팅 **{amount}개**를 지웠습니다!")
    await msg.delete(delay=3)

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
    embed.add_field(name="`!점수` / `!점수 @유저`", value="유저의 상세 내전 프로필과 전적, 점수를 확인합니다.", inline=False)
    embed.add_field(name="`!맵`", value="내전 전장 선택 및 무작위 룰렛을 돌립니다.", inline=False)
    embed.add_field(name="`!점수동기화` (관리자)", value="구글 시트의 정보를 실시간으로 봇에 덮어씌웁니다.", inline=False)
    embed.add_field(name="`!내전시작` (관리자)", value="인원 제외, 팀 분배, 밴픽, 워크샵 생성을 한 번에 진행합니다.", inline=False)
    embed.add_field(name="`!내전종료 1팀` (관리자)", value="구글 시트 '전적' 탭에 내전 결과를 자동으로 기록합니다.", inline=False)
    embed.add_field(name="`!대기실복귀` (관리자)", value="팀 채널에 흩어진 유저들을 대기실로 불러옵니다.", inline=False)
    embed.add_field(name="`!대기실설정` / `!팀채널설정 [1~4]` (관리자)", value="내전용 음성 채널들을 지정합니다.", inline=False)
    embed.add_field(name="`!청소 숫자`", value="입력한 숫자만큼 메시지를 삭제합니다.", inline=False)
    embed.add_field(name="`!관리자추가 @유저` (관리자)", value="해당 유저에게 봇 제어 권한을 줍니다.", inline=False)
    embed.add_field(name="`!귀여워`", value="비밀 이스터에그 🐾", inline=False)
    await ctx.send(embed=embed)

# --- 🔊 3. 채널 설정 및 이동 ---
@bot.command(name='공지채널설정')
async def set_announce(ctx):
    if not is_admin(ctx): return
    config = load_data(CONFIG_FILE)
    config['announce_id'] = ctx.channel.id
    save_data(CONFIG_FILE, config)
    await ctx.send(f'📢 **{ctx.channel.name}** 채널이 [최종 공지 채널]로 등록되었습니다.')

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
    
@bot.command(name='대기실복귀')
async def return_to_lobby(ctx):
    if not is_admin(ctx): return
    config = load_data(CONFIG_FILE)
    lobby_id = config.get('lobby_id')
    team_channels = config.get('team_channels', {})
    if not lobby_id: return await ctx.send("❌ 대기실이 설정되지 않았습니다.")
    lobby_channel = bot.get_channel(int(lobby_id))
    
    status_msg = await ctx.send("⏳ 유저들을 대기실로 불러오는 중입니다...")
    move_success, move_fail = 0, 0
    for team_num, channel_id in team_channels.items():
        t_channel = bot.get_channel(int(channel_id))
        if t_channel:
            for member in t_channel.members:
                if not member.bot:
                    try: await member.move_to(lobby_channel); move_success += 1
                    except: move_fail += 1
    await status_msg.edit(content=f"✅ 총 **{move_success}명** 대기실 복귀 완료! (실패: {move_fail}명)")

# --- 🗺️ 4. 전장 룰렛 UI (복구 완료) ---
class MapDetailSelect(discord.ui.Select):
    def __init__(self, mode):
        self.mode = mode
        options = [discord.SelectOption(label="🎲 해당 모드 내 무작위", value="랜덤")]
        for m in OW_MAPS[mode]: options.append(discord.SelectOption(label=m, value=m))
        super().__init__(placeholder=f"{mode} 전장을 고르거나 랜덤을 돌리세요...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "랜덤":
            result_map = random.choice(OW_MAPS[self.mode])
            embed = discord.Embed(title=f"🎲 [{self.mode}] 무작위 룰렛 결과!", description=f"이번 내전은 **{result_map}**에서 진행됩니다.", color=discord.Color.purple())
        else:
            result_map = selected
            embed = discord.Embed(title=f"✅ [{self.mode}] 전장 확정!", description=f"이번 내전은 **{result_map}**에서 진행됩니다.", color=discord.Color.green())
        if result_map in MAP_IMAGES: embed.set_image(url=MAP_IMAGES[result_map])
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


# --- 🛠️ 5. 유틸리티 함수 (가로형 표 및 워크샵 생성) ---
def build_horizontal_embed(teams, team_count, title="🎲 내전 팀 구성 결과"):
    scores = load_data(SCORE_FILE)
    team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
    embed = discord.Embed(title=title, color=discord.Color.gold())
    
    headers = []
    for i in range(team_count):
        t_score = sum(scores.get(str(p.id), {}).get("score", 0) for p in teams[i])
        avg = round(t_score / len(teams[i]), 1) if teams[i] else 0
        headers.append(f"{team_colors[i]} (평균 {avg})")
        
    max_len = max(len(t) for t in teams) if teams else 0
    desc = "**" + "\u2003\u2003\u2003".join(headers) + "**\n\n"
    
    for row_idx in range(max_len):
        row_str = ""
        for t_idx in range(team_count):
            if row_idx < len(teams[t_idx]): row_str += f"{teams[t_idx][row_idx].mention}\u2003\u2003"
            else: row_str += "-\u2003\u2003"
        desc += row_str + "\n"
        
    embed.description = desc
    return embed

def generate_workshop_code(teams, banned_heroes):
    scores = load_data(SCORE_FILE)
    ws_text = "```javascript\n// 워크샵 스크립트 (복사해서 붙여넣기)\n"
    ws_text += "variables {\n  global:\n    0: Team1_Names\n    1: Team2_Names\n    2: Team3_Names\n    3: Team4_Names\n    4: Banned_Heroes\n}\n\n"
    
    def get_ingame_names(team_members):
        names = []
        for p in team_members:
            btag = scores.get(str(p.id), {}).get("battletag", "알수없음")
            ingame = btag.split('#')[0] if '#' in btag else btag
            names.append(f'Custom String("{ingame}")')
        return ", ".join(names)

    ws_text += 'rule("내전 시스템: 기초 설정") {\n  event { Ongoing - Global; }\n  actions {\n'
    if len(teams) > 0: ws_text += f'    Global.Team1_Names = Array({get_ingame_names(teams[0])});\n'
    if len(teams) > 1: ws_text += f'    Global.Team2_Names = Array({get_ingame_names(teams[1])});\n'
    if len(teams) > 2: ws_text += f'    Global.Team3_Names = Array({get_ingame_names(teams[2])});\n'
    if len(teams) > 3: ws_text += f'    Global.Team4_Names = Array({get_ingame_names(teams[3])});\n'
    
    ban_strings = ", ".join([f'Hero({h})' for h in banned_heroes]) if banned_heroes else "Empty Array"
    ws_text += f'    Global.Banned_Heroes = Array({ban_strings});\n  }\n}\n\n'
    
    ws_text += 'rule("내전 시스템: 자동 팀 분배 및 관전자 강퇴") {\n  event { Ongoing - Each Player; All; All; }\n  actions {\n'
    ws_text += '    If(Array Contains(Global.Team1_Names, Custom String("{0}", Event Player)));\n      Move Player to Team(Event Player, Team 1);\n'
    ws_text += '    Else If(Array Contains(Global.Team2_Names, Custom String("{0}", Event Player)));\n      Move Player to Team(Event Player, Team 2);\n'
    ws_text += '    Else();\n      Move Player to Team(Event Player, Spectator);\n    End;\n  }\n}\n\n'
    
    ws_text += 'rule("내전 시스템: 영웅 밴픽 제한") {\n  event { Ongoing - Each Player; All; All; }\n  conditions { Has Spawned(Event Player) == True; }\n  actions {\n'
    ws_text += '    Set Player Allowed Heroes(Event Player, Remove From Array(Allowed Heroes(Event Player), Global.Banned_Heroes));\n  }\n}\n
```'
    return ws_text


# --- 🚫 6. 밴픽 시스템 ---
class BanPickView(discord.ui.View):
    def __init__(self, captains, teams, team_channels, ban_count):
        super().__init__(timeout=None)
        self.captains = captains
        self.teams, self.team_channels = teams, team_channels
        self.ban_count = ban_count
        self.banned_heroes = []
        
        self.simultaneous_picks = {}
        self.current_turn = 0
        self.order = []
        
        if ban_count > 1:
            for _ in range(ban_count):
                self.order.extend(captains)

        for role, heroes in OW_HEROES.items():
            options = [discord.SelectOption(label=h, value=h) for h in heroes]
            select = discord.ui.Select(placeholder=f"🚫 [{role}] 영웅 밴 선택...", options=options, custom_id=f"ban_{role}")
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        user = interaction.user
        selected_hero = interaction.data['values'][0]
        
        if self.ban_count == 1:
            if user not in self.captains: return await interaction.response.send_message("❌ 주장만 선택할 수 있습니다!", ephemeral=True)
            self.simultaneous_picks[user.id] = selected_hero
            await interaction.response.send_message(f"✅ 선택 완료! 다른 팀 주장의 밴을 기다립니다.", ephemeral=True)
            
            if len(self.simultaneous_picks) == len(self.captains):
                self.banned_heroes = list(set(self.simultaneous_picks.values()))
                await self.execute_final(interaction)
        else:
            current_captain = self.order[self.current_turn]
            if user.id != current_captain.id: return await interaction.response.send_message(f"❌ 지금은 {current_captain.display_name} 주장의 턴입니다!", ephemeral=True)
            if selected_hero in self.banned_heroes: return await interaction.response.send_message("❌ 이미 밴 된 영웅입니다!", ephemeral=True)
                
            self.banned_heroes.append(selected_hero)
            self.current_turn += 1
            
            if self.current_turn >= len(self.order):
                await self.execute_final(interaction)
            else:
                next_captain = self.order[self.current_turn]
                await interaction.response.edit_message(content=f"🚫 **교차 밴픽 진행 중**\n현재 밴 목록: {', '.join(self.banned_heroes)}\n👉 다음 밴: {next_captain.mention} 님 선택해 주세요!")

    async def execute_final(self, interaction):
        for child in self.children: child.disabled = True
        
        team1_nicks = [p.display_name for p in self.teams[0]] if len(self.teams) > 0 else []
        team2_nicks = [p.display_name for p in self.teams[1]] if len(self.teams) > 1 else []
        save_data(MATCH_FILE, {"team1_nicks": team1_nicks, "team2_nicks": team2_nicks})
        
        config = load_data(CONFIG_FILE)
        announce_id = config.get('announce_id')
        
        move_success = 0
        for i, team in enumerate(self.teams):
            ch_id = self.team_channels.get(str(i + 1))
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if p.voice:
                        try: await p.move_to(bot.get_channel(int(ch_id))); move_success += 1
                        except: pass

        if announce_id:
            ann_channel = bot.get_channel(int(announce_id))
            if ann_channel:
                embed = build_horizontal_embed(self.teams, len(self.teams), "🏆 [내전 매칭 성사] 최종 라인업!")
                embed.add_field(name="🚫 금지 영웅 (밴픽)", value=", ".join(self.banned_heroes) if self.banned_heroes else "없음", inline=False)
                ws_code = generate_workshop_code(self.teams, self.banned_heroes)
                await ann_channel.send(content="🔔 **내전 매칭 및 밴픽이 확정되었습니다!**", embed=embed)
                await ann_channel.send(content=f"🛠️ **방장용 워크샵 자동 연동 코드**\n{ws_code}")
                
        await interaction.response.edit_message(content=f"✅ 밴픽 종료 및 공지 전송 완료! (이동 성공 {move_success}명)", view=None)

class BanCountSelectView(discord.ui.View):
    def __init__(self, teams, team_channels):
        super().__init__(timeout=None)
        self.teams, self.team_channels = teams, team_channels
        
    @discord.ui.button(label="🚫 밴픽 진행하기", style=discord.ButtonStyle.danger)
    async def start_banpick(self, interaction: discord.Interaction, button: discord.ui.Button):
        scores = load_data(SCORE_FILE)
        
        captains = []
        for team in self.teams:
            if team: captains.append(max(team, key=lambda p: scores.get(str(p.id), {}).get("score", 0)))
            
        if len(captains) < len(self.teams): return await interaction.response.send_message("❌ 주장을 선정할 수 없습니다. (데이터 부족)", ephemeral=True)

        class SelectBanCount(discord.ui.Select):
            def __init__(self, captains, teams, channels):
                self.captains, self.teams, self.channels = captains, teams, channels
                options = [
                    discord.SelectOption(label="팀당 1개 (비공개 동시 선택)", value="1"),
                    discord.SelectOption(label="팀당 2개 (교차 밴)", value="2"),
                    discord.SelectOption(label="팀당 3개 (교차 밴)", value="3")
                ]
                super().__init__(placeholder="팀당 몇 명의 영웅을 밴할까요?", options=options)
                
            async def callback(self, inter):
                count = int(self.values[0])
                msg = "👑 **각 팀 주장:** " + " / ".join([c.mention for c in self.captains]) + "\n"
                msg += "🚨 주장들은 서로 상의 없이 아래 메뉴에서 밴할 영웅을 선택해 주세요!" if count == 1 else f"🚨 **{self.captains[0].mention}** 주장부터 교차 밴을 시작합니다!"
                await inter.response.edit_message(content=msg, view=BanPickView(self.captains, self.teams, self.channels, count))

        view = discord.ui.View()
        view.add_item(SelectBanCount(captains, self.teams, self.team_channels))
        await interaction.response.edit_message(content="⚖️ 영웅 밴픽 모드 설정 중...", view=view)


# --- 👥 7. 팀 분배 및 수동 교환 UI ---
class SwapView(discord.ui.View):
    def __init__(self, teams, team_channels, members):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.members = teams, team_channels, members
        options = [discord.SelectOption(label=p.display_name, value=str(p.id)) for t in teams for p in t]
        self.s1 = discord.ui.Select(placeholder="🔄 첫 번째 유저...", options=options, custom_id="swap_1")
        self.s2 = discord.ui.Select(placeholder="🔄 두 번째 유저...", options=options, custom_id="swap_2")
        async def dummy(interaction): await interaction.response.defer()
        self.s1.callback = self.s2.callback = dummy
        self.add_item(self.s1)
        self.add_item(self.s2)

    @discord.ui.button(label="🔄 교환 실행", style=discord.ButtonStyle.green, row=2)
    async def execute_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.s1.values or not self.s2.values or self.s1.values[0] == self.s2.values[0]: return await interaction.response.send_message("❌ 서로 다른 두 명을 선택하세요!", ephemeral=True)
        u1_id, u2_id = self.s1.values[0], self.s2.values[0]
        u1_pos, u2_pos = None, None
        for t_idx, team in enumerate(self.teams):
            for p_idx, p in enumerate(team):
                if str(p.id) == u1_id: u1_pos = (t_idx, p_idx)
                if str(p.id) == u2_id: u2_pos = (t_idx, p_idx)
        p1, p2 = self.teams[u1_pos[0]][u1_pos[1]], self.teams[u2_pos[0]][u2_pos[1]]
        self.teams[u1_pos[0]][u1_pos[1]], self.teams[u2_pos[0]][u2_pos[1]] = p2, p1
        
        embed = build_horizontal_embed(self.teams, len(self.teams), "⚖️ 내전 밸런스 조정 중 (수동 교체됨)")
        await interaction.response.edit_message(content="✅ 교환 완료!", embed=embed, view=MoveConfirmView(self.teams, self.team_channels, self.members))

class MoveConfirmView(discord.ui.View):
    def __init__(self, teams, team_channels, members):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.members = teams, team_channels, members

    @discord.ui.button(label="🔄 랜덤 다시 짜기", style=discord.ButtonStyle.blurple)
    async def reroll_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        scores = load_data(SCORE_FILE)
        p_data = [(m, scores[str(m.id)].get("score", 0), scores[str(m.id)].get("score", 0) + random.uniform(-1.0, 1.0)) for m in self.members if str(m.id) in scores]
        p_data.sort(key=lambda x: x[2], reverse=True)
        new_teams = [[] for _ in range(len(self.teams))]
        t_scores = [0] * len(self.teams)
        for p, act, _ in p_data:
            idx = t_scores.index(min(t_scores))
            new_teams[idx].append(p)
            t_scores[idx] += act
        self.teams = new_teams
        embed = build_horizontal_embed(self.teams, len(self.teams), "⚖️ 내전 밸런스 (재배치됨)")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="👥 수동 팀원 교체", style=discord.ButtonStyle.secondary)
    async def manual_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🔄 맞교환할 인원을 선택하세요.", view=SwapView(self.teams, self.team_channels, self.members))
        
    @discord.ui.button(label="🚀 [최종 확정] 밴픽 넘어가기", style=discord.ButtonStyle.green, row=1)
    async def finalize_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = load_data(CONFIG_FILE)
        if 'announce_id' not in cfg: return await interaction.response.send_message("❌ `!공지채널설정`이 되어 있지 않습니다!", ephemeral=True)
        await interaction.response.edit_message(content="✅ 팀 편성이 완료되었습니다. 밴픽을 진행합니다!", embed=None, view=BanCountSelectView(self.teams, self.team_channels))


# --- 👥 8. 내전 시작 및 인원 제외 UI ---
class TeamDivideButton(discord.ui.Button):
    def __init__(self, t_count, members):
        super().__init__(label="🎲 팀 나누기 실행", style=discord.ButtonStyle.primary)
        self.t_count, self.members = t_count, members

    async def callback(self, interaction: discord.Interaction):
        scores = load_data(SCORE_FILE)
        chans = load_data(CONFIG_FILE).get('team_channels', {})
        p_data, unreg = [], []
        
        for m in self.members:
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
            
        embed = build_horizontal_embed(teams, self.t_count, "⚖️ 내전 밸런스 1차 편성")
        await interaction.response.edit_message(embed=embed, view=MoveConfirmView(teams, chans, self.members))

class TeamCountSelect(discord.ui.Select):
    def __init__(self, members):
        options = [discord.SelectOption(label=f"{i}개 팀으로 나누기", value=str(i)) for i in range(2, 5)]
        super().__init__(placeholder="팀 개수 선택...", options=options)
        self.members = members

    async def callback(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(TeamDivideButton(int(self.values[0]), self.members))
        await interaction.response.edit_message(content=f"👥 {self.values[0]}개 팀 선택됨.", view=view)

class ExcludeSelectView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=None)
        self.members = members
        self.excluded_ids = []
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        self.select = discord.ui.Select(placeholder="제외할 유저 다중 선택", min_values=1, max_values=min(len(options), 25), options=options[:25])
        async def cb(interaction):
            self.excluded_ids = self.select.values
            await interaction.response.defer()
        self.select.callback = cb
        self.add_item(self.select)

    @discord.ui.button(label="✅ 제외하고 시작", style=discord.ButtonStyle.primary, row=1)
    async def confirm_exclude(self, interaction, button):
        if not self.excluded_ids: return await interaction.response.send_message("❌ 유저를 선택하세요.", ephemeral=True)
        filtered = [m for m in self.members if str(m.id) not in self.excluded_ids]
        if len(filtered) < 2: return await interaction.response.send_message("❌ 인원 부족!", ephemeral=True)
        view = discord.ui.View()
        view.add_item(TeamCountSelect(filtered))
        await interaction.response.edit_message(content=f"📋 참여 인원: **{len(filtered)}명**", view=view)

    @discord.ui.button(label="🚀 전원 포함 시작", style=discord.ButtonStyle.green, row=1)
    async def skip_exclude(self, interaction, button):
        view = discord.ui.View()
        view.add_item(TeamCountSelect(self.members))
        await interaction.response.edit_message(content=f"📋 참여 인원: **{len(self.members)}명**", view=view)

@bot.command(name='내전시작')
async def start_civil_war(ctx):
    if not is_admin(ctx): return
    cfg = load_data(CONFIG_FILE)
    if 'lobby_id' not in cfg: return await ctx.send("❌ 대기실 설정 필요 (`!대기실설정`)")
    lobby = bot.get_channel(int(cfg['lobby_id']))
    mems = [m for m in lobby.members if not m.bot]
    if len(mems) < 2: return await ctx.send("❌ 대기실 인원 부족!")
    await ctx.send(f"📋 **현재 대기실 인원:** {len(mems)}명", view=ExcludeSelectView(mems))


# --- 🚀 봇 실행 ---
token = os.environ.get('BOT_TOKEN')
if not token and os.path.exists('token.txt'):
    with open('token.txt', 'r', encoding='utf-8') as f: token = f.read().strip()
if token: bot.run(token)
else: print("❌ 토큰 오류")
