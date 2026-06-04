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
BETTING_FILE = 'betting.json'
DAILY_FILE = 'daily.json'
chat_cooldowns = {} # 채팅 30초 쿨타임을 기억하는 메모리 장부

from discord.ext import tasks
import random
import time

def get_daily_data():
    return load_data(DAILY_FILE)

def save_daily_data(data):
    save_data(DAILY_FILE, data)

# 💡 [신규] 10분마다 음성 채널 유저에게 5P 지급 (루프)
@tasks.loop(minutes=10)
async def voice_reward_loop():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot and not member.voice.afk and not member.voice.self_deaf:
                    add_points(member.id, 5)
                    
import asyncio
import re

class BettingState:
    def __init__(self):
        self.active = False
        self.bets = {"1팀": {}, "2팀": {}}
        self.ann_msg = None

global_betting = BettingState()

def get_points(user_id):
    data = load_data(BETTING_FILE)
    uid = str(user_id)
    if uid not in data:
        data[uid] = 1000
        save_data(BETTING_FILE, data)
    return data[uid]

def add_points(user_id, amount):
    data = load_data(BETTING_FILE)
    uid = str(user_id)
    data[uid] = data.get(uid, 1000) + int(amount)
    save_data(BETTING_FILE, data)

# --- 🗺️ 전장 및 영웅 데이터 ---
OW_MAPS = {
    "호위": ["66번 국도", "감시기지: 지브롤터", "도라도", "리알토", "샴발리 수도원", "서킷 로얄", "쓰레기촌", "하바나"],
    "혼합": ["눔바니", "미드타운", "블리자드 월드", "아이헨발데", "왕의 길", "파라이수", "할리우드"],
    "쟁탈": ["남극 반도", "네팔", "리장 타워", "사모아", "부산", "오아시스", "일리오스"],
    "밀기": ["뉴 퀸 스트리트", "루나사피", "이스페란사", "콜로세오"],
    "플래시포인트": ["뉴 정크 시티", "수라바사", "아틀리스"]
}

OW_HEROES = {
    "돌격": ["D.Va", "둠피스트", "레킹볼", "윈스턴", "해저드", "로드호그", "마우가", "오리사", "자리야", "도미나", "라마트라", "라인하르트", "시그마", "정커퀸"],
    "공격": ["메이", "바스티온", "솔저: 76", "시메트라", "엠레", "정크랫", "토르비욘", "솜브라", "시에라", "에코", "파라", "프레야", "겐지", "리퍼", "벤데타", "벤처", "안란", "트레이서", "소전", "애쉬", "위도우메이커", "캐서디", "한조"],
    "지원": ["루시우", "바티스트", "아나", "제트팩 캣", "젠야타", "라이프위버", "메르시", "모이라", "키리코", "미즈키", "브리기테", "우양", "일리아리", "주노"]
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

def is_admin(obj):
    # Context와 Interaction 모두 유저 객체를 안전하게 가져오도록 분기 처리
    author = obj.author if hasattr(obj, 'author') else obj.user
    if author.guild_permissions.administrator: return True
    config = load_data(CONFIG_FILE)
    if str(author.id) in config.get('admins', []): return True
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
async def auto_sync_scores():
    client, sheet_key = get_google_client()
    if not client or not sheet_key: return False
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
                "wins": row[11].strip() if len(row) > 11 else "-",
                "losses": row[12].strip() if len(row) > 12 else "-"
            }
        save_data(SCORE_FILE, synced_data)
        return len(synced_data)
    except Exception as e:
        print(f"동기화 에러: {e}")
        return False

@bot.command(name='점수동기화')
async def sync_scores(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자만 사용할 수 있습니다.")
    status_msg = await ctx.send("⏳ 구글 시트에서 최신 데이터를 불러오는 중입니다...")
    result = await auto_sync_scores()
    if result is False: await status_msg.edit(content="❌ 동기화 실패: 구글 시트 연결 오류")
    else: await status_msg.edit(content=f"✅ 구글 시트 동기화 완료! 총 **{result}명** 업데이트 완료.")

@bot.command(name='내전종료')
async def end_civil_war(ctx, winner: str = None):
    if not is_admin(ctx): return
    if winner not in ["1팀", "2팀"]: return await ctx.send("❌ 올바른 승리 팀을 입력하세요. (예: `!내전종료 1팀`)")
        
    match_data = load_data(MATCH_FILE)
    if not match_data: return await ctx.send("❌ 최근 진행된 내전 기록이 없거나 이미 종료되었습니다.")
        
    client, sheet_key = get_google_client()
    if not client or not sheet_key: return await ctx.send("❌ 구글 시트 연동 오류.")
    
    status_msg = await ctx.send("⏳ 구글 시트 [전적] 탭에 상세 데이터를 기록하고 있습니다...")
    try:
        spreadsheet = client.open_by_key(sheet_key)
        record_sheet = spreadsheet.worksheet("전적")
        
        kst_time = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        
        # 💡 각 열칸을 따로따로 완전히 분리하여 기록 구조화
        row_data = [
            kst_time, 
            f"{winner} 승리", 
            ", ".join(match_data.get('t1_nicks', [])),
            ", ".join(match_data.get('t1_ids', [])),
            ", ".join(match_data.get('t1_btags', [])),
            ", ".join(match_data.get('t2_nicks', [])),
            ", ".join(match_data.get('t2_ids', [])),
            ", ".join(match_data.get('t2_btags', []))
        ]
        record_sheet.append_row(row_data)
        save_data(MATCH_FILE, {}) # 전적 기록 완료 후 초기화
        await status_msg.edit(content=f"🎉 **내전 결과 기록 완료!**\n> 🏆 데이터 분리 저장이 완료되어 시트 수식에 즉시 반영됩니다.")
    except Exception as e:
        await status_msg.edit(content=f"❌ 전적 기록 실패:\n```{e}```")

@bot.command(name='출석')
async def daily_attendance(ctx):
    uid = str(ctx.author.id)
    data = get_daily_data()
    import datetime as dt
    today = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    
    if data.get(uid, {}).get("attendance") == today:
        return await ctx.send(f"❌ **{ctx.author.display_name}**님, 오늘은 이미 출석하셨습니다! 내일 다시 와주세요.")
        
    reward = random.randint(10, 100)
    add_points(uid, reward)
    
    if uid not in data: data[uid] = {}
    data[uid]["attendance"] = today
    save_daily_data(data)
    await ctx.send(f"✅ **{ctx.author.display_name}**님 출석 완료! 랜덤 포인트 **{reward} P**가 지급되었습니다. (현재 잔액: {get_points(uid):,} P)")

# 💡 [신규] 파산 구제금 명령어 (100P 이하일 때 300P 지급)
@bot.command(name='구제')
async def relief_funds(ctx):
    uid = str(ctx.author.id)
    bal = get_points(uid)
    if bal > 100:
        return await ctx.send(f"❌ 잔액이 100 P 이하일 때만 구제금을 받을 수 있습니다. (현재 잔액: {bal:,} P)")
        
    data = get_daily_data()
    import datetime as dt
    today = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    
    if data.get(uid, {}).get("relief") == today:
        return await ctx.send("❌ 파산 구제금은 하루에 한 번만 받을 수 있습니다.")
        
    add_points(uid, 300)
    
    if uid not in data: data[uid] = {}
    data[uid]["relief"] = today
    save_daily_data(data)
    await ctx.send(f"🚑 **{ctx.author.display_name}**님에게 파산 구제금 **300 P**가 지급되었습니다! (현재 잔액: {get_points(uid):,} P)")

@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료!")
    if not voice_reward_loop.is_running():
        voice_reward_loop.start() # 봇 켜지면 10분마다 5P 주는 루프 시작

        
# --- 🎯 2. 기본 유틸 및 명령어 (복구 완료) ---
@bot.command(name='점수')
async def check_profile(ctx, member: discord.Member = None):
    target = member or ctx.author
    scores = load_data(SCORE_FILE)
    user_id = str(target.id)

    if user_id in scores:
        data = scores[user_id]
        pt = get_points(user_id) # 1000포인트 자동 지급/조회
        
        embed = discord.Embed(title=f"📋 {target.display_name} 님의 내전 프로필", color=discord.Color.blue())
        embed.add_field(name="🎯 내전 점수", value=f"**{data.get('score', 0)} 점**", inline=True)
        embed.add_field(name="💰 내전 포인트", value=f"**{pt:,} P**", inline=True)
        embed.add_field(name="오버워치 닉네임", value=data.get('nickname', '-'), inline=False)
        embed.add_field(name="배틀태그", value=data.get('battletag', '-'), inline=True)
        embed.add_field(name="주 영웅", value=data.get('main_hero', '-'), inline=True)
        
        win_rate, record_text = data.get('wins', '-'), data.get('losses', '-') 
        embed.add_field(name="🏆 누적 전적", value=f"{record_text} (승률: {win_rate})", inline=False)
        embed.add_field(name="주/보조 포지션", value=f"{data.get('main_pos', '-')} / {data.get('sub_pos', '-')}", inline=True)
        embed.add_field(name="티어 (최고/현재)", value=f"{data.get('max_tier', '-')} / {data.get('current_tier', '-')}", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ **{target.display_name}** 님의 데이터가 구글 시트에 없습니다.")

@bot.command(name='포인트')
async def manage_points(ctx, member: discord.Member, op: str):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 전용 명령어입니다.")
    uid = str(member.id)
    current = get_points(uid)
    
    try:
        if op.startswith('+'):
            val = int(op[1:])
            add_points(uid, val)
        elif op.startswith('-'):
            val = int(op[1:])
            add_points(uid, -val)
        elif op.startswith('='):
            val = int(op[1:])
            data = load_data(BETTING_FILE)
            data[uid] = val
            save_data(BETTING_FILE, data)
        else:
            return await ctx.send("❌ 올바른 형식을 사용하세요. 예: `!포인트 @유저 +500` 또는 `=1000`")
        
        new_pt = get_points(uid)
        await ctx.send(f"✅ **{member.display_name}**님의 포인트가 변경되었습니다: `{current:,} P` ➡️ `{new_pt:,} P`")
    except ValueError:
        await ctx.send("❌ 숫자 형식이 잘못되었습니다.")

@bot.command(name='랭킹')
async def show_ranking(ctx):
    scores = load_data(SCORE_FILE)
    points_data = load_data(BETTING_FILE)

    rate_list = []
    for uid, data in scores.items():
        record_str = str(data.get('losses', '0'))
        nums = re.findall(r'\d+', record_str)
        wins, losses = (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (0, 0)
        
        if (wins + losses) >= 3:
            rate = (wins / (wins + losses)) * 100
            rate_list.append((uid, data.get('nickname', '알수없음'), rate, wins, losses))
    
    rate_list.sort(key=lambda x: x[2], reverse=True)
    
    pt_list = []
    for uid, pt in points_data.items():
        nickname = scores.get(uid, {}).get('nickname', '알수없음')
        pt_list.append((uid, nickname, int(pt)))
    pt_list.sort(key=lambda x: x[2], reverse=True)

    embed = discord.Embed(title="🏆 내전 서버 통합 랭킹", color=discord.Color.gold())
    
    rate_text = ""
    for i, (uid, nick, rate, w, l) in enumerate(rate_list[:10]):
        rate_text += f"**{i+1}위.** {nick} - {rate:.1f}% ({w}승 {l}패)\n"
    if not rate_text: rate_text = "조건(최소 3판)을 달성한 유저가 없습니다."
    embed.add_field(name="⚔️ 승률 랭킹 (TOP 10)", value=rate_text, inline=False)

    pt_text = ""
    for i, (uid, nick, pt) in enumerate(pt_list[:10]):
        pt_text += f"**{i+1}위.** {nick} - {pt:,} P\n"
    if not pt_text: pt_text = "아직 배팅 기록이 없습니다."
    embed.add_field(name="💰 포인트 랭킹 (TOP 10)", value=pt_text, inline=False)

    await ctx.send(embed=embed)

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

@bot.command(name='비밀초대')
async def secret_invite(ctx):
    # 💡 이 명령어는 서버가 아닌 봇과의 DM(개인 메시지)에서만 작동합니다.
    if ctx.guild is not None:
        return 
        
    if not bot.guilds:
        return await ctx.send("❌ 봇이 현재 어떤 서버에도 소속되어 있지 않습니다.")
        
    # 봇이 속해 있는 첫 번째 서버를 타겟으로 잡습니다.
    guild = bot.guilds[0]
    
    # 초대장을 만들 수 있는 텍스트 채널을 찾아서 초대 코드를 생성합니다.
    for channel in guild.text_channels:
        try:
            # max_age=300 (5분 뒤 만료), max_uses=1 (1번 쓰면 사라짐)
            invite = await channel.create_invite(max_age=300, max_uses=1, unique=True, reason="비밀 초대")
            return await ctx.send(f"🎟️ 비밀 초대 링크가 생성되었습니다 (5분 후 만료, 1회용):\n{invite.url}")
        except:
            continue # 이 채널에 권한이 없으면 다음 채널로 시도
            
    await ctx.send("❌ 서버 내에 봇이 초대장을 생성할 권한이 있는 채널이 없습니다.")


@bot.event
async def on_message(message):
    # 💡 [핵심] 시스템에서 보낸 '누군가 입장했습니다' 메시지인지 확인하고 즉시 삭제!
    if message.type == discord.MessageType.new_member:
        try:
            await message.delete()
            return # 시스템 메시지는 아래 로직을 탈 필요가 없으므로 여기서 종료
        except:
            pass # 봇에게 메시지 삭제 권한(Manage Messages)이 없으면 무시

    if message.author.bot: return
    await bot.process_commands(message) # 명령어 씹힘 방지 (필수)



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
# [새로 추가] 연전 진행 시 사용되는 독립된 밴픽 개수 선택 드롭다운 클래스

# [새로 추가] 통합 관리 컨트롤 패널 및 다전제 확인 뷰

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


# 🔊 공지 및 세팅이 다 끝난 후 최종 이동만 수행하는 독립된 버튼 뷰
class FinalVoiceMoveView(discord.ui.View):
    def __init__(self, teams, team_channels):
        super().__init__(timeout=None)
        self.teams, self.team_channels = teams, team_channels

    @discord.ui.button(label="🔊 팀원 음성 채널 자동 이동 실행", style=discord.ButtonStyle.success)
    async def move_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(content="⏳ 음성 채널로 유저들을 이동시키는 중...", view=self)
        move_success = 0
        for i, team in enumerate(self.teams):
            ch_id = self.team_channels.get(str(i + 1))
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if hasattr(p, 'voice') and p.voice:
                        try: await p.move_to(bot.get_channel(int(ch_id))); move_success += 1
                        except: pass
        await interaction.message.edit(content=f"✅ 모든 팀원 배치 완료! (이동 성공: {move_success}명)")


# --- 👑 특수 조건 밸런싱 알고리즘 ---
def divide_teams_with_conditions(members, t_count, scores, conditions):
    # 1. 듀오 그룹화 (Union-Find)
    parent = {m.id: m.id for m in members}
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i])
        return parent[i]
    def union(i, j):
        root_i, root_j = find(i), find(j)
        if root_i != root_j: parent[root_i] = root_j

    for u1, u2 in conditions['duos']:
        if u1 in parent and u2 in parent: union(u1, u2)

    super_nodes = {}
    for m in members:
        root = find(m.id)
        if root not in super_nodes: super_nodes[root] = []
        super_nodes[root].append(m)
    sn_list = list(super_nodes.values())

    # 2. 라이벌 제약 조건 맵핑
    rival_graph = {i: set() for i in range(len(sn_list))}
    for u1, u2 in conditions['rivals']:
        if u1 in parent and u2 in parent:
            r1, r2 = find(u1), find(u2)
            if r1 == r2: return None, f"❌ 모순된 조건: <@{u1}>님과 <@{u2}>님은 같은 듀오 그룹인데 라이벌로도 설정되었습니다!"
            idx1, idx2 = list(super_nodes.keys()).index(r1), list(super_nodes.keys()).index(r2)
            rival_graph[idx1].add(idx2)
            rival_graph[idx2].add(idx1)

    # 3. DFS 백트래킹으로 모든 조건 탐색 및 최적 밸런스 찾기
    best_teams = None
    best_cost = float('inf')
    teams_sn = [[] for _ in range(t_count)]
    team_scores = [0] * t_count
    team_sizes = [0] * t_count

    def dfs(node_idx):
        nonlocal best_teams, best_cost
        if node_idx == len(sn_list):
            avg_score = sum(team_scores) / t_count
            variance = sum((s - avg_score)**2 for s in team_scores)
            size_penalty = sum(abs(sz - len(members)/t_count) for sz in team_sizes) * 10000 
            total_cost = variance + size_penalty 
            
            if total_cost < best_cost:
                best_cost = total_cost
                real_teams = [[] for _ in range(t_count)]
                for t_i in range(t_count):
                    for sn_i in teams_sn[t_i]: real_teams[t_i].extend(sn_list[sn_i])
                best_teams = real_teams
            return

        sn = sn_list[node_idx]
        sn_size = len(sn)
        sn_score = sum(float(scores.get(str(m.id), {}).get("score", 0)) for m in sn)

        for t_idx in range(t_count):
            conflict = any(existing in rival_graph[node_idx] for existing in teams_sn[t_idx])
            if conflict: continue

            teams_sn[t_idx].append(node_idx)
            team_scores[t_idx] += sn_score
            team_sizes[t_idx] += sn_size
            dfs(node_idx + 1)
            teams_sn[t_idx].pop()
            team_scores[t_idx] -= sn_score
            team_sizes[t_idx] -= sn_size

    dfs(0)
    if not best_teams: return None, "❌ 현재 설정된 듀오/라이벌 조건을 모두 만족하며 팀을 나눌 방법이 없습니다! 조건을 완화해 주세요."
    return best_teams, None


# --- 👥 팀 설정 UI 흐름 ---
class TeamDivideButton(discord.ui.Button):
    def __init__(self, t_count, members, conditions):
        super().__init__(label="🎲 밸런스 매칭 실행", style=discord.ButtonStyle.primary)
        self.t_count, self.members, self.conditions = t_count, members, conditions

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        scores = load_data(SCORE_FILE)
        chans = load_data(CONFIG_FILE).get('team_channels', {})
        unreg = [m.display_name for m in self.members if str(m.id) not in scores]
        if unreg: return await interaction.followup.send(f"❌ 정보 미등록 유저: {', '.join(unreg)}\n`!점수동기화`를 확인하세요.", ephemeral=True)
        
        teams, error_msg = divide_teams_with_conditions(self.members, self.t_count, scores, self.conditions)
        if error_msg: return await interaction.followup.send(error_msg, ephemeral=True)
            
        embed = build_horizontal_embed(teams, self.t_count, "⚖️ 내전 밸런스 1차 편성")
        await interaction.message.edit(embed=embed, view=MoveConfirmView(teams, chans, self.members, self.conditions))

class TeamCountSelect(discord.ui.Select):
    def __init__(self, members, conditions):
        options = [discord.SelectOption(label=f"{i}개 팀으로 나누기", value=str(i)) for i in range(2, 5)]
        super().__init__(placeholder="팀 개수 선택...", options=options)
        self.members, self.conditions = members, conditions

    async def callback(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(TeamDivideButton(int(self.values[0]), self.members, self.conditions))
        await interaction.response.edit_message(content=f"👥 {self.values[0]}개 팀 선택됨.", view=view)

class ConditionSettingView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=None)
        self.members = members
        self.conditions = {'duos': [], 'rivals': []}
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        
        self.s1 = discord.ui.Select(placeholder="유저 A 선택...", options=options[:25], custom_id="cond_1")
        self.s2 = discord.ui.Select(placeholder="유저 B 선택...", options=options[:25], custom_id="cond_2")
        
        async def dummy(interaction): await interaction.response.defer()
        self.s1.callback = self.s2.callback = dummy
        self.add_item(self.s1)
        self.add_item(self.s2)

    def get_status_text(self):
        txt = "👯 **[특수 조건 설정]**\n"
        if self.conditions['duos']:
            txt += "🤝 **듀오:** " + ", ".join([f"<@{a}>+<@{b}>" for a,b in self.conditions['duos']]) + "\n"
        if self.conditions['rivals']:
            txt += "⚔️ **라이벌:** " + ", ".join([f"<@{a}>vs<@{b}>" for a,b in self.conditions['rivals']]) + "\n"
        if not self.conditions['duos'] and not self.conditions['rivals']:
            txt += "설정된 조건 없음 (완전 밸런스 매칭)"
        return txt

    @discord.ui.button(label="🤝 듀오(같은 팀) 추가", style=discord.ButtonStyle.success, row=2)
    async def add_duo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.s1.values or not self.s2.values or self.s1.values[0] == self.s2.values[0]: 
            return await interaction.response.send_message("❌ 서로 다른 두 명을 선택하세요!", ephemeral=True)
        self.conditions['duos'].append((int(self.s1.values[0]), int(self.s2.values[0])))
        await interaction.response.edit_message(content=self.get_status_text(), view=self)

    @discord.ui.button(label="⚔️ 라이벌(다른 팀) 추가", style=discord.ButtonStyle.danger, row=2)
    async def add_rival(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.s1.values or not self.s2.values or self.s1.values[0] == self.s2.values[0]: 
            return await interaction.response.send_message("❌ 서로 다른 두 명을 선택하세요!", ephemeral=True)
        self.conditions['rivals'].append((int(self.s1.values[0]), int(self.s2.values[0])))
        await interaction.response.edit_message(content=self.get_status_text(), view=self)

    @discord.ui.button(label="🗑️ 조건 초기화", style=discord.ButtonStyle.secondary, row=3)
    async def reset_cond(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.conditions = {'duos': [], 'rivals': []}
        await interaction.response.edit_message(content=self.get_status_text(), view=self)

    @discord.ui.button(label="✅ 이 조건으로 팀 개수 설정", style=discord.ButtonStyle.primary, row=3)
    async def done_cond(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(TeamCountSelect(self.members, self.conditions))
        await interaction.response.edit_message(content="⚖️ 팀 개수를 골라주세요.", view=view)


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

    async def go_to_conditions(self, interaction, filtered_members):
        view = ConditionSettingView(filtered_members)
        await interaction.response.edit_message(content=view.get_status_text(), view=view)

    @discord.ui.button(label="✅ 제외 적용", style=discord.ButtonStyle.primary, row=1)
    async def confirm_exclude(self, interaction, button):
        if not self.excluded_ids: return await interaction.response.send_message("❌ 제외할 유저를 선택하세요.", ephemeral=True)
        filtered = [m for m in self.members if str(m.id) not in self.excluded_ids]
        if len(filtered) < 2: return await interaction.response.send_message("❌ 인원 부족!", ephemeral=True)
        await self.go_to_conditions(interaction, filtered)

    @discord.ui.button(label="🚀 전원 포함 진행", style=discord.ButtonStyle.green, row=1)
    async def skip_exclude(self, interaction, button):
        await self.go_to_conditions(interaction, self.members)


# --- 🛠️ 5. 유틸리티 함수 (가로형 표 및 워크샵 생성) ---
def build_horizontal_embed(teams, team_count, title="🎲 내전 팀 구성 결과"):
    scores = load_data(SCORE_FILE)
    team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
    embed = discord.Embed(title=title, color=discord.Color.gold())
    
    for i in range(team_count):
        if i >= len(teams): break
        team = teams[i]
        
        t_score = sum(float(scores.get(str(p.id), {}).get("score", 0)) for p in team)
        avg = round(t_score / len(team), 1) if team else 0
        
        # 💡 [A안 적용] 멤버 멘션 옆에 내전 점수를 예쁘게 괄호로 표기합니다.
        members_text_list = []
        for p in team:
            score_val = float(scores.get(str(p.id), {}).get("score", 0))
            score_str = f"{score_val:g}" # 불필요한 소수점(.0) 자동 제거
            members_text_list.append(f"{p.mention} ({score_str}점)")
            
        members_text = "\n".join(members_text_list) if members_text_list else "없음"
        embed.add_field(name=f"{team_colors[i]} (평균 {avg})", value=members_text, inline=True)
        
    return embed

def generate_workshop_code(teams, banned_heroes):
    scores = load_data(SCORE_FILE)
    ws_text = "```javascript\n// 워크샵 스크립트 (복사해서 붙여넣기)\n"
    ws_text += "variables {\n  global:\n    0: Team1_Names\n    1: Team2_Names\n    2: Team3_Names\n    3: Team4_Names\n    4: Banned_Heroes\n}\n\n"
    
    def get_ingame_names(team_members):
        names = []
        for p in team_members:
            btag = scores.get(str(p.id), {}).get("battletag", "알수없음")
            ingame = btag.split('#')[0].strip() if '#' in btag else btag.strip()
            names.append(f'Custom String("{ingame}")')
        return ", ".join(names)

    ws_text += 'rule("내전 시스템: 기초 설정") {\n  event { Ongoing - Global; }\n  action {\n'
    if len(teams) > 0: ws_text += f'    Global.Team1_Names = Array({get_ingame_names(teams[0])});\n'
    if len(teams) > 1: ws_text += f'    Global.Team2_Names = Array({get_ingame_names(teams[1])});\n'
    if len(teams) > 2: ws_text += f'    Global.Team3_Names = Array({get_ingame_names(teams[2])});\n'
    if len(teams) > 3: ws_text += f'    Global.Team4_Names = Array({get_ingame_names(teams[3])});\n'
    
    ban_strings = ", ".join([f'Hero({h})' for h in banned_heroes]) if banned_heroes else "Empty Array"
    ws_text += f'    Global.Banned_Heroes = Array({ban_strings});\n  }}\n}}\n\n'
    
    ws_text += 'rule("내전 시스템: 자동 팀 분배") {\n  event { Ongoing - Each Player; All; All; }\n  action {\n'
    ws_text += '    If(Array Contains(Global.Team1_Names, Custom String("{0}", Event Player)));\n      Move Player to Team(Event Player, Team 1, -1);\n'
    ws_text += '    Else If(Array Contains(Global.Team2_Names, Custom String("{0}", Event Player)));\n      Move Player to Team(Event Player, Team 2, -1);\n'
    ws_text += '    End;\n  }\n}\n\n'
    
    ws_text += 'rule("내전 시스템: 영웅 밴픽 제한") {\n  event { Ongoing - Each Player; All; All; }\n  condition { Has Spawned(Event Player) == True; }\n  action {\n'
    ws_text += '    Set Player Allowed Heroes(Event Player, Remove From Array(Allowed Heroes(Event Player), Global.Banned_Heroes));\n  }\n}\n```'
    return ws_text

def pack_match_data(teams):
    scores = load_data(SCORE_FILE)
    def get_fields(team):
        return (
            [p.display_name for p in team],
            [str(p.id) for p in team],
            [scores.get(str(p.id), {}).get('battletag', '-') for p in team]
        )
    t1_n, t1_i, t1_b = get_fields(teams[0]) if len(teams) > 0 else ([], [], [])
    t2_n, t2_i, t2_b = get_fields(teams[1]) if len(teams) > 1 else ([], [], [])
    return {"t1_nicks": t1_n, "t1_ids": t1_i, "t1_btags": t1_b, "t2_nicks": t2_n, "t2_ids": t2_i, "t2_btags": t2_b}


class BettingView(discord.ui.View):
    def __init__(self, msg, teams, embed): # 💡 임베드를 인자로 직접 받음
        super().__init__(timeout=None)
        self.msg = msg
        self.teams = teams
        self.embed = embed 
        global_betting.active = True
        global_betting.bets = {"1팀": {}, "2팀": {}}
        global_betting.ann_msg = msg
        bot.loop.create_task(self.timer_task())

    async def timer_task(self):
        await asyncio.sleep(300)
        if global_betting.active:
            global_betting.active = False
            for child in self.children: child.disabled = True
            try:
                p1 = sum(global_betting.bets["1팀"].values())
                p2 = sum(global_betting.bets["2팀"].values())
                self.embed.set_footer(text=f"⏳ 배팅 마감! 최종 배팅 풀 | 🔴 1팀: {p1:,} P | 🔵 2팀: {p2:,} P")
                await global_betting.ann_msg.edit(embed=self.embed, view=self)
            except: pass

    async def update_msg(self):
        p1 = sum(global_betting.bets["1팀"].values())
        p2 = sum(global_betting.bets["2팀"].values())
        try:
            self.embed.set_footer(text=f"💰 실시간 배팅 풀 | 🔴 1팀: {p1:,} P | 🔵 2팀: {p2:,} P | (5분 후 마감)")
            await global_betting.ann_msg.edit(embed=self.embed)
        except: pass

    @discord.ui.button(label="🔴 1팀 배팅", style=discord.ButtonStyle.danger)
    async def bet_t1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal("1팀", self))

    @discord.ui.button(label="🔵 2팀 배팅", style=discord.ButtonStyle.primary)
    async def bet_t2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal("2팀", self))


# (중간에 있는 WinButton 등 다른 클래스는 그대로 둡니다.)

class NextSetConfirmView(discord.ui.View):
    def __init__(self, teams, team_channels, captains, set_count=1, ws_code=None, ann_msg_obj=None):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.captains, self.set_count = teams, team_channels, captains, set_count
        self.ws_code = ws_code
        self.ann_msg_obj = ann_msg_obj
        
    # (next_set_ban 부분은 기존과 동일하므로 생략 없이 원래 코드를 유지하세요)

    @discord.ui.button(label="⏩ 다음 세트 밴픽 건너뛰기", style=discord.ButtonStyle.secondary, row=0)
    async def next_set_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_set = self.set_count + 1
        cfg = load_data(CONFIG_FILE)
        ann_ch = bot.get_channel(int(cfg.get('announce_id'))) if cfg.get('announce_id') else interaction.channel
        
        import datetime as dt
        kst_time = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        ann_title = f"⚔️ [{next_set}세트] 공식 라인업 확정 ({kst_time})"
        ann_msg = f"📢 **제 {next_set}세트 매치가 곧 시작됩니다. 5분간 배팅이 진행됩니다!**\n━━━━━━━━━━━━━━━━━━━━━━━━━"
        embed = build_horizontal_embed(self.teams, len(self.teams), ann_title)
        
        ann_msg_obj = await ann_ch.send(content=ann_msg, embed=embed)
        bet_view = BettingView(ann_msg_obj, self.teams, embed) # 💡 완성된 embed를 직접 전달 
        await ann_msg_obj.edit(view=bet_view)
        await bet_view.update_msg()
        
        ws_code = generate_workshop_code(self.teams, [])
        await interaction.response.edit_message(content=f"⚙️ **[방장 컨트롤 패널 - {next_set}세트]** 다음 세트 관리를 시작합니다.", view=AdminControlPanel(self.teams, self.team_channels, ws_code, self.captains, next_set, ann_msg_obj))
        
    # (end_match, return_lobby, undo_match 부분도 기존과 동일하게 유지하시면 됩니다.)

# (중간 클래스 유지)

class BanPickView(discord.ui.View):
    def __init__(self, captains, teams, team_channels, ban_count, admin_channel, set_count=1):
        super().__init__(timeout=None)
        self.captains, self.teams, self.team_channels, self.admin_channel, self.set_count = captains, teams, team_channels, admin_channel, set_count
        self.max_bans = ban_count * len(teams)
        self.banned_heroes = []
        self.update_selects()

    def update_selects(self):
        self.clear_items()
        for role, heroes in OW_HEROES.items():
            available = [h for h in heroes if h not in self.banned_heroes]
            if available: self.add_item(BanRoleSelect(role, available, self))

    async def execute_final(self, interaction):
        save_data(MATCH_FILE, pack_match_data(self.teams))
        import datetime as dt
        kst_time = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        ann_title = f"⚔️ [{self.set_count}세트] 공식 라인업 확정 ({kst_time})"
        ann_msg = f"📢 **제 {self.set_count}세트 매치가 곧 시작됩니다. 5분간 배팅이 진행됩니다!**\n━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # 💡 버그 수정: 완성된 embed를 미리 만들어두고 메시지를 보냄
        embed = build_horizontal_embed(self.teams, len(self.teams), ann_title)
        embed.add_field(name="🚫 금지 영웅 (밴픽 완료)", value=", ".join(self.banned_heroes) if self.banned_heroes else "없음", inline=False)
        await interaction.response.edit_message(content=ann_msg, embed=embed, view=None)
        
        # 최신 상태의 메시지 객체를 정확히 다시 긁어옴
        ann_msg_obj = await interaction.original_response() 
        bet_view = BettingView(ann_msg_obj, self.teams, embed) # 💡 embed를 통째로 넘겨서 짤림 방지
        await ann_msg_obj.edit(view=bet_view)
        await bet_view.update_msg()
        
        ws_code = generate_workshop_code(self.teams, self.banned_heroes)
        await self.admin_channel.send(content=f"⚙️ **[방장 컨트롤 패널 - {self.set_count}세트]** 내전 관리를 시작합니다.", view=AdminControlPanel(self.teams, self.team_channels, ws_code, self.captains, self.set_count, ann_msg_obj))

# --- 🔗 통합 UI 및 밴픽, 컨트롤 패널 클래스 ---
# 💡 [새로 추가됨] 팀 개수에 맞춰 동적으로 생성되는 승리 버튼 클래스
class WinButton(discord.ui.Button):
    def __init__(self, team_idx, panel):
        styles = [discord.ButtonStyle.danger, discord.ButtonStyle.primary, discord.ButtonStyle.success, discord.ButtonStyle.secondary]
        emojis = ["🔴", "🔵", "🟢", "🟡"]
        super().__init__(label=f"{team_idx+1}팀 승리", style=styles[team_idx], emoji=emojis[team_idx], row=0)
        self.team_idx = team_idx
        self.panel = panel
        
    async def callback(self, interaction: discord.Interaction):
        await self.panel.record_result(interaction, f"{self.team_idx+1}팀", self.team_idx)

# 💡 [업데이트됨] 배팅 모달 및 타이머 뷰 (선수 배팅 차단 로직 추가)
class BetModal(discord.ui.Modal, title="💰 포인트 배팅"):
    amount_input = discord.ui.TextInput(label="배팅할 금액 (10 포인트 이상) (숫자 또는 '올인')", placeholder="예: 500, 올인")

    def __init__(self, team_name, view):
        super().__init__()
        self.team_name = team_name
        self.b_view = view

    async def on_submit(self, interaction: discord.Interaction):
        if not global_betting.active: return await interaction.response.send_message("❌ 이미 배팅이 마감되었습니다.", ephemeral=True)
        uid = str(interaction.user.id)
        
        is_player, my_team_name = False, None
        for i, team in enumerate(self.b_view.teams):
            if any(uid == str(p.id) for p in team):
                is_player, my_team_name = True, f"{i+1}팀"
                break

        if is_player and self.team_name != my_team_name:
            return await interaction.response.send_message(f"❌ 선수는 자신이 속한 **{my_team_name}**에만 배팅할 수 있습니다! (낭만 배팅)", ephemeral=True)

        opp_team = "2팀" if self.team_name == "1팀" else "1팀"
        if uid in global_betting.bets[opp_team]:
            return await interaction.response.send_message("❌ 이미 반대 팀에 배팅하셨습니다! 양방향 배팅은 불가능합니다.", ephemeral=True)

        bal = get_points(uid)
        val = self.amount_input.value.strip()
        
        if val == "올인": bet_amt = bal
        elif val.isdigit(): bet_amt = int(val)
        else: return await interaction.response.send_message("❌ 올바른 숫자를 입력하세요.", ephemeral=True)

        if bet_amt <= 9: return await interaction.response.send_message("❌ 10 포인트 이상 배팅하세요.", ephemeral=True)
        if bet_amt > bal: return await interaction.response.send_message(f"❌ 잔액이 부족합니다. (현재 잔액: {bal:,} P)", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        add_points(uid, -bet_amt)
        global_betting.bets[self.team_name][uid] = global_betting.bets[self.team_name].get(uid, 0) + bet_amt

        await self.b_view.update_msg()
        await interaction.followup.send(f"✅ **{self.team_name}**에 **{bet_amt:,} P**를 배팅했습니다! (남은 잔액: {bal - bet_amt:,} P)", ephemeral=True)

class WinButton(discord.ui.Button):
    def __init__(self, team_idx, panel):
        styles = [discord.ButtonStyle.danger, discord.ButtonStyle.primary, discord.ButtonStyle.success, discord.ButtonStyle.secondary]
        emojis = ["🔴", "🔵", "🟢", "🟡"]
        super().__init__(label=f"{team_idx+1}팀 승리", style=styles[team_idx], emoji=emojis[team_idx], row=0)
        self.team_idx = team_idx
        self.panel = panel
        
    async def callback(self, interaction: discord.Interaction):
        await self.panel.record_result(interaction, f"{self.team_idx+1}팀", self.team_idx)

# 💡 [새로 추가됨] 밴픽 진행 중 작전 회의를 위한 임시 방장 패널
class BanPickAdminPanel(discord.ui.View):
    def __init__(self, teams, team_channels):
        super().__init__(timeout=None)
        self.teams = teams
        self.team_channels = team_channels

    @discord.ui.button(label="🔊 팀원 음성 채널 분배", style=discord.ButtonStyle.secondary, row=0)
    async def move_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        move_success = 0
        for i, team in enumerate(self.teams):
            ch_id = self.team_channels.get(str(i + 1))
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if hasattr(p, 'voice') and p.voice:
                        try: await p.move_to(bot.get_channel(int(ch_id))); move_success += 1
                        except: pass
        await interaction.followup.send(f"✅ 팀원 음성 분배 완료! ({move_success}명)", ephemeral=True)

    @discord.ui.button(label="↩️ 대기실 복귀", style=discord.ButtonStyle.danger, row=0)
    async def return_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏳ 고정 메인 대기실로 복귀시킵니다...", ephemeral=True)
        cfg = load_data(CONFIG_FILE)
        lobby_id = cfg.get('lobby_id')
        main_lobby = bot.get_channel(int(lobby_id)) if lobby_id else None
        if not main_lobby: return await interaction.edit_original_response(content="❌ 고정 메인 대기실 채널을 찾을 수 없습니다.")
        move_success = 0
        for team in self.teams:
            for p in team:
                if hasattr(p, 'voice') and p.voice:
                    try: await p.move_to(main_lobby); move_success += 1
                    except: pass
        await interaction.edit_original_response(content=f"✅ {move_success}명을 대기실로 이동시켰습니다!")

# 💡 [업데이트됨] 밴픽 개수 선택 후 임시 패널을 관리자 채널에 전송
class DirectSelectBanCount(discord.ui.Select):
    def __init__(self, caps, tms, chans, admin_ch, set_count=1):
        self.caps, self.tms, self.chans, self.admin_ch, self.set_count = caps, tms, chans, admin_ch, set_count
        super().__init__(placeholder=f"[{set_count}세트] 팀당 몇 명을 밴할까요?", options=[
            discord.SelectOption(label="팀당 1개 밴", value="1"),
            discord.SelectOption(label="팀당 2개 밴", value="2"),
            discord.SelectOption(label="팀당 3개 밴", value="3")
        ])
        
    async def callback(self, interaction: discord.Interaction):
        count = int(self.values[0])
        cfg = load_data(CONFIG_FILE)
        ann_ch = bot.get_channel(int(cfg.get('announce_id'))) if cfg.get('announce_id') else interaction.channel
        
        bp_view = BanPickView(self.caps, self.tms, self.chans, count, self.admin_ch, self.set_count)
        msg = f"👑 **[{self.set_count}세트 밴픽 진행]** 각 팀 주장: " + " / ".join([c.mention for c in self.caps]) + "\n🚨 주장들은 공지 채널의 역할군별 메뉴에서 밴할 영웅을 선택해 주세요!"
        
        embed = build_horizontal_embed(self.tms, len(self.tms), f"🏆 [{self.set_count}세트] 밴픽 진행 중")
        await ann_ch.send(content=msg, embed=embed, view=bp_view)
        
        # 관리자 채널(방장 화면)에 밴픽용 임시 패널 전송
        admin_msg = f"⚙️ **[밴픽 대기 중 - 임시 방장 패널]**\n주장들이 밴픽을 완료하기 전까지 이 패널을 사용해 팀원들을 음성 채널로 분배하여 작전 회의를 진행할 수 있습니다."
        await self.admin_ch.send(content=admin_msg, view=BanPickAdminPanel(self.tms, self.chans))
        
        await interaction.response.edit_message(content=f"✅ 공지 채널에 {self.set_count}세트 밴픽 화면을 띄웠습니다!", view=None)

class AdminControlPanel(discord.ui.View):
    def __init__(self, teams, team_channels, ws_code, captains, set_count=1, ann_msg_obj=None):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.ws_code = teams, team_channels, ws_code
        self.captains, self.set_count, self.ann_msg_obj = captains, set_count, ann_msg_obj

        for i in range(len(teams)):
            self.add_item(WinButton(i, self))

    async def record_result(self, interaction: discord.Interaction, winner: str, team_idx: int):
        await interaction.response.defer()
        status_msg = await interaction.followup.send(f"⏳ 구글 시트 전적 기록 및 배팅 정산 중...", ephemeral=True)
        
        if global_betting.active: global_betting.active = False
        
        global_betting.last_transactions = {}
        def give_pts(u_id, amt):
            add_points(u_id, amt)
            global_betting.last_transactions[str(u_id)] = global_betting.last_transactions.get(str(u_id), 0) + amt

        for i, team in enumerate(self.teams):
            reward = 300 if (i == team_idx) else 100
            for p in team: give_pts(p.id, reward)

        p_win = sum(global_betting.bets[winner].values())
        opp_team = "1팀" if winner == "2팀" else "2팀"
        p_lose = sum(global_betting.bets[opp_team].values())

        bet_results_text = ""
        if p_win > 0:
            if p_lose == 0:
                bet_results_text = f"\n💸 상대 팀에 걸린 포인트가 없어 원금만 반환되었습니다."
                for uid, amt in global_betting.bets[winner].items(): give_pts(uid, amt)
            else:
                ratio = p_lose / p_win
                bet_results_text = f"\n📈 **적중 배당률:** 1.0 + {ratio:.2f}배 터짐!"
                for uid, amt in global_betting.bets[winner].items():
                    profit = int(amt * ratio)
                    give_pts(uid, amt + profit)
                    
        if self.ann_msg_obj:
            try:
                embed = self.ann_msg_obj.embeds[0]
                colors = [discord.Color.red(), discord.Color.blue(), discord.Color.green(), discord.Color.gold()]
                embed.color = colors[team_idx]
                embed.title = f"🏆 [{self.set_count}세트 최종 결과] {winner} 승리!"
                embed.set_footer(text="✅ 경기가 종료되어 배팅이 정산되었습니다.")
                await self.ann_msg_obj.edit(content=f"🎉 **{winner}이(가) 승리했습니다!**" + bet_results_text, embed=embed, view=None)
            except: pass

        match_data = pack_match_data(self.teams)
        client, sheet_key = get_google_client()
        if client and sheet_key:
            try:
                record_sheet = client.open_by_key(sheet_key).worksheet("전적")
                import datetime as dt
                kst_time = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
                row_data = [
                    kst_time, f"{winner} 승리", 
                    ", ".join(match_data.get('t1_nicks', [])), ", ".join(match_data.get('t1_ids', [])), ", ".join(match_data.get('t1_btags', [])),
                    ", ".join(match_data.get('t2_nicks', [])), ", ".join(match_data.get('t2_ids', [])), ", ".join(match_data.get('t2_btags', []))
                ]
                record_sheet.append_row(row_data) 
                
                await status_msg.edit(content="⏳ 시트 수식 계산 대기 및 동기화 중... (약 4초 대기)")
                await asyncio.sleep(4)
                await auto_sync_scores()
                
                for child in self.children: child.disabled = True
                await interaction.message.edit(content=f"✅ **[{self.set_count}세트 {winner} 승리 기록 완료]** 동일한 멤버로 다음 세트를 진행하시겠습니까?", view=NextSetConfirmView(self.teams, self.team_channels, self.captains, self.set_count, self.ws_code, self.ann_msg_obj))
                await status_msg.edit(content=f"✅ 배팅 정산 및 구글 시트 최신 전적 동기화가 완벽하게 처리되었습니다!")
            except Exception as e:
                await status_msg.edit(content=f"❌ 기록/동기화 중 오류 발생: {e}")

    @discord.ui.button(label="🔊 팀원 음성 채널 분배", style=discord.ButtonStyle.secondary, row=1)
    async def move_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        move_success = 0
        for i, team in enumerate(self.teams):
            ch_id = self.team_channels.get(str(i + 1))
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if hasattr(p, 'voice') and p.voice:
                        try: await p.move_to(bot.get_channel(int(ch_id))); move_success += 1
                        except: pass
        await interaction.followup.send(f"✅ 팀원 음성 분배 완료! ({move_success}명)", ephemeral=True)

    @discord.ui.button(label="🛠️ 코드 DM 받기", style=discord.ButtonStyle.secondary, row=1)
    async def send_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.send(f"🛠️ **방장용 워크샵 자동 연동 코드 ({self.set_count}세트)**\n{self.ws_code}")
            await interaction.response.send_message("✅ DM으로 코드를 전송했습니다!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ DM 전송 실패.", ephemeral=True)

    @discord.ui.button(label="↩️ 대기실 복귀", style=discord.ButtonStyle.danger, row=2)
    async def return_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏳ 고정 메인 대기실로 복귀시킵니다...", ephemeral=True)
        cfg = load_data(CONFIG_FILE)
        lobby_id = cfg.get('lobby_id')
        main_lobby = bot.get_channel(int(lobby_id)) if lobby_id else None
        if not main_lobby: return await interaction.edit_original_response(content="❌ 채널을 찾을 수 없습니다.")
        move_success = 0
        for team in self.teams:
            for p in team:
                if hasattr(p, 'voice') and p.voice:
                    try: await p.move_to(main_lobby); move_success += 1
                    except: pass
        await interaction.edit_original_response(content=f"✅ {move_success}명을 대기실로 이동시켰습니다!")

    @discord.ui.button(label="🛑 경기 무효 (전액 환불)", style=discord.ButtonStyle.danger, row=2)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if global_betting.active: global_betting.active = False
        
        refund_count = 0
        for t in ["1팀", "2팀"]:
            for uid, amt in global_betting.bets[t].items():
                add_points(uid, amt)
                refund_count += 1
                
        if self.ann_msg_obj:
            try:
                embed = self.ann_msg_obj.embeds[0]
                embed.color = discord.Color.dark_gray()
                embed.title = f"🛑 [{self.set_count}세트] 경기 무효 (취소됨)"
                embed.set_footer(text="🚨 배팅 전액 환불 완료")
                await self.ann_msg_obj.edit(content=f"🚨 **경기가 무효 처리되었습니다. 배팅된 {refund_count}건의 포인트가 모두 반환되었습니다.**", embed=embed, view=None)
            except: pass
            
        for child in self.children: child.disabled = True
        await interaction.message.edit(content="🛑 경기가 무효 처리되었습니다. 다음 세트를 준비하려면 `!내전시작`을 이용해 주세요.", view=self)

class BanRoleSelect(discord.ui.Select):
    def __init__(self, role, heroes, parent_view):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=h, value=h) for h in heroes if h not in parent_view.banned_heroes]
        super().__init__(
            placeholder=f"🚫 [{role}] 밴 선택 ({len(parent_view.banned_heroes)}/{parent_view.max_bans}개)",
            options=options[:25], custom_id=f"ban_select_{role}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.parent_view
        if not (is_admin(interaction) or interaction.user.id in [c.id for c in view.captains]):
            return await interaction.response.send_message("❌ 밴픽 권한이 없습니다.", ephemeral=True)
        chosen = self.values[0]
        view.banned_heroes.append(chosen)
        if len(view.banned_heroes) >= view.max_bans: await view.execute_final(interaction)
        else:
            view.update_selects()
            embed = build_horizontal_embed(view.teams, len(view.teams), f"🏆 [{view.set_count}세트] 밴픽 진행 중")
            embed.add_field(name="🚫 현재 금지된 영웅 목록", value=", ".join(view.banned_heroes), inline=False)
            await interaction.response.edit_message(embed=embed, view=view)

class ManualCaptainSelectView(discord.ui.View):
    def __init__(self, teams, team_channels, set_count=1):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.set_count = teams, team_channels, set_count
        self.c1, self.c2 = None, None

        options_t1 = [discord.SelectOption(label=p.display_name, value=str(p.id)) for p in teams[0]]
        self.s1 = discord.ui.Select(placeholder="👑 1팀 주장 선택...", options=options_t1, custom_id="cap_select_1")
        options_t2 = [discord.SelectOption(label=p.display_name, value=str(p.id)) for p in teams[1]] if len(teams) > 1 else []
        self.s2 = discord.ui.Select(placeholder="👑 2팀 주장 선택...", options=options_t2, custom_id="cap_select_2") if options_t2 else None

        async def cb1(interaction: discord.Interaction):
            self.c1 = interaction.guild.get_member(int(self.s1.values[0]))
            await interaction.response.defer()
        self.s1.callback = cb1
        self.add_item(self.s1)
        if self.s2:
            async def cb2(interaction: discord.Interaction):
                self.c2 = interaction.guild.get_member(int(self.s2.values[0]))
                await interaction.response.defer()
            self.s2.callback = cb2
            self.add_item(self.s2)

    @discord.ui.button(label="🚫 주장 확정 및 밴픽 시작", style=discord.ButtonStyle.danger, row=2)
    async def go_banpick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.c1 or (self.s2 and not self.c2): return await interaction.response.send_message("❌ 모든 팀의 주장을 선택해 주세요!", ephemeral=True)
        captains = [self.c1]
        if self.c2: captains.append(self.c2)
        view = discord.ui.View()
        view.add_item(DirectSelectBanCount(captains, self.teams, self.team_channels, interaction.channel, self.set_count))
        await interaction.response.edit_message(content=f"⚖️ [{self.set_count}세트] 영웅 밴픽 개수를 정해주세요.", view=view)

class MoveConfirmView(discord.ui.View):
    def __init__(self, teams, team_channels, members, conditions, set_count=1):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.members, self.conditions, self.set_count = teams, team_channels, members, conditions, set_count

    @discord.ui.button(label="🔄 랜덤 다시 짜기 (조건유지)", style=discord.ButtonStyle.blurple)
    async def reroll_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        scores = load_data(SCORE_FILE)
        import random
        noisy_scores = {k: {"score": float(v.get("score",0)) + random.uniform(-1.0, 1.0)} for k, v in scores.items()}
        new_teams, error_msg = divide_teams_with_conditions(self.members, len(self.teams), noisy_scores, self.conditions)
        if error_msg: return await interaction.followup.send(error_msg, ephemeral=True)
        self.teams = new_teams
        embed = build_horizontal_embed(self.teams, len(self.teams), f"⚖️ [{self.set_count}세트] 내전 밸런스 (조건 유지 재배치됨)")
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="👥 수동 팀원 교체", style=discord.ButtonStyle.secondary)
    async def manual_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🔄 맞교환할 인원을 선택하세요.", view=SwapView(self.teams, self.team_channels, self.members, self.conditions, self.set_count))
        
    @discord.ui.button(label="👑 [최종 확정] 주장 선택 및 밴픽", style=discord.ButtonStyle.danger, row=1)
    async def finalize_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = load_data(CONFIG_FILE)
        if 'announce_id' not in cfg: return await interaction.response.send_message("❌ `!공지채널설정`이 필요합니다!", ephemeral=True)
        await interaction.response.edit_message(content=f"👑 [{self.set_count}세트] 각 팀의 주장을 선출해 주세요.", embed=None, view=ManualCaptainSelectView(self.teams, self.team_channels, self.set_count))

    @discord.ui.button(label="⏩ 밴픽 건너뛰기 (바로 공지)", style=discord.ButtonStyle.gray, row=1)
    async def skip_banpick_entirely(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        cfg = load_data(CONFIG_FILE)
        announce_id = cfg.get('announce_id')
        save_data(MATCH_FILE, pack_match_data(self.teams))

        ann_msg_obj = None
        if announce_id:
            ann_channel = bot.get_channel(int(announce_id))
            if ann_channel:
                import datetime as dt
                kst_time = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
                ann_title = f"⚔️ [{self.set_count}세트] 공식 라인업 확정 ({kst_time})"
                ann_msg = f"📢 **제 {self.set_count}세트 매치가 곧 시작됩니다. 5분간 배팅이 진행됩니다!**\n━━━━━━━━━━━━━━━━━━━━━━━━━"
                embed = build_horizontal_embed(self.teams, len(self.teams), ann_title)
                
                ann_msg_obj = await ann_channel.send(content=ann_msg, embed=embed)
                bet_view = BettingView(ann_msg_obj, self.teams)
                await ann_msg_obj.edit(view=bet_view)
                await bet_view.update_msg()
                
        ws_code = generate_workshop_code(self.teams, [])
        await interaction.response.edit_message(content=f"⚙️ **[방장 컨트롤 패널 - {self.set_count}세트]** 내전 관리를 시작합니다.", view=AdminControlPanel(self.teams, self.team_channels, ws_code, captains=None, set_count=self.set_count, ann_msg_obj=ann_msg_obj))

class SwapView(discord.ui.View):
    def __init__(self, teams, team_channels, members, conditions, set_count=1):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.members, self.conditions, self.set_count = teams, team_channels, members, conditions, set_count
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
        
        embed = build_horizontal_embed(self.teams, len(self.teams), f"⚖️ [{self.set_count}세트] 내전 밸런스 조정 중 (수동 교체됨)")
        await interaction.response.edit_message(content="✅ 교환 완료!", embed=embed, view=MoveConfirmView(self.teams, self.team_channels, self.members, self.conditions, self.set_count))

@bot.command(name='내전시작')
async def start_civil_war(ctx):
    if not is_admin(ctx): return
    cfg = load_data(CONFIG_FILE)
    if 'lobby_id' not in cfg: return await ctx.send("❌ 대기실 설정 필요 (`!대기실설정`)")
    lobby = bot.get_channel(int(cfg['lobby_id']))
    mems = [m for m in lobby.members if not m.bot]
    if len(mems) < 2: return await ctx.send("❌ 대기실 인원 부족!")
    await ctx.send(f"📋 **현재 대기실 인원:** {len(mems)}명", view=ExcludeSelectView(mems))

# ==========================================
class DummyUser:
    def __init__(self, uid, name):
        self.id = uid
        self.display_name = name
        self.mention = f"<@{uid}>" # 태그 파랗게 보이게 설정
        self.voice = True # 음성 채널에 있는 것처럼 속임

    # 채널 이동 명령을 받으면 에러 없이 무시하는 가짜 함수
    async def move_to(self, channel):
        pass

@bot.command(name='테스트시작')
async def test_civil_war(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자만 사용할 수 있습니다.")
    scores = load_data(SCORE_FILE)
    
    # 💡 [핵심 추가] 내전 점수(score)가 0점보다 큰(유효한) 사람들의 ID만 뽑아냅니다.
    valid_uids = [uid for uid, data in scores.items() if float(data.get('score', 0)) > 0]
    
    if len(valid_uids) < 4:
        return await ctx.send("❌ 구글 시트에 내전 점수가 등록된 유저가 최소 4명은 있어야 합니다!")
        
    # 점수가 있는 사람 중에서만 랜덤 8명 추출
    sample_ids = random.sample(valid_uids, min(8, len(valid_uids)))
    
    dummy_members = []
    for uid in sample_ids:
        dummy_members.append(DummyUser(int(uid), scores[uid]['nickname']))
        
    await ctx.send(f"🛠️ **[개발자 테스트 모드 가동]**\n점수 등록자 중 랜덤으로 **{len(dummy_members)}명**을 대기실 가상 인원으로 구성했습니다.", view=ExcludeSelectView(dummy_members))

token = os.environ.get('BOT_TOKEN')
if not token and os.path.exists('token.txt'):
    with open('token.txt', 'r', encoding='utf-8') as f: token = f.read().strip()
if token: bot.run(token)
else: print("❌ 토큰 오류")
