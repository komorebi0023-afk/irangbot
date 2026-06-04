import discord
from discord.ext import commands, tasks
import sqlite3
import random
import os
import json
import gspread
from google.oauth2.service_account import Credentials
import datetime as dt
import time
import asyncio
import re

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 봇 초기 세팅 및 권한
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# 채팅 포인트 쿨타임 (메모리)
chat_cooldowns = {} 

# 서버별 실시간 배팅 상태 관리 (메모리 격리)
class BettingState:
    def __init__(self):
        self.active = False
        self.bets = {"1팀": {}, "2팀": {}}
        self.ann_msg = None
        self.last_transactions = {}

server_bets = {}
def get_betting(guild_id):
    gid = str(guild_id)
    if gid not in server_bets:
        server_bets[gid] = BettingState()
    return server_bets[gid]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💾 다중 서버 전용 SQLite DB 세팅
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS server_config (
                    guild_id TEXT PRIMARY KEY,
                    sheet_key TEXT, announce_id TEXT, lobby_id TEXT,
                    t1_id TEXT, t2_id TEXT, t3_id TEXT, t4_id TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS server_admins (
                    guild_id TEXT, user_id TEXT, PRIMARY KEY (guild_id, user_id)
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_stats (
                    guild_id TEXT, user_id TEXT, points INTEGER DEFAULT 1000,
                    score REAL DEFAULT 0.0, battletag TEXT DEFAULT '-',
                    nickname TEXT DEFAULT '-', main_pos TEXT DEFAULT '-',
                    sub_pos TEXT DEFAULT '-', max_tier TEXT DEFAULT '-',
                    current_tier TEXT DEFAULT '-', main_hero TEXT DEFAULT '-',
                    wins TEXT DEFAULT '0', losses TEXT DEFAULT '0',
                    last_daily TEXT DEFAULT '', last_relief TEXT DEFAULT '',
                    PRIMARY KEY (guild_id, user_id)
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_match (
                    guild_id TEXT PRIMARY KEY, match_data TEXT
                 )''')
    conn.commit()
    conn.close()

init_db()

def get_server_config(guild_id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM server_config WHERE guild_id=?", (str(guild_id),))
    res = c.fetchone()
    conn.close()
    return dict(res) if res else {}

def update_server_config(guild_id, col, val):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute(f"INSERT INTO server_config (guild_id, {col}) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET {col}=excluded.{col}", (str(guild_id), str(val)))
    conn.commit()
    conn.close()

def is_admin(obj):
    author = obj.author if hasattr(obj, 'author') else obj.user
    if author.guild_permissions.administrator: return True
    guild_id = str(obj.guild.id) if obj.guild else None
    if not guild_id: return False
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM server_admins WHERE guild_id=? AND user_id=?", (guild_id, str(author.id)))
    res = c.fetchone()
    conn.close()
    return bool(res)

def get_user_data(guild_id, user_id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM user_stats WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))
    res = c.fetchone()
    if not res:
        c.execute("INSERT INTO user_stats (guild_id, user_id, points) VALUES (?, ?, 1000)", (str(guild_id), str(user_id)))
        conn.commit()
        c.execute("SELECT * FROM user_stats WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))
        res = c.fetchone()
    conn.close()
    return dict(res)

def update_user_points(guild_id, user_id, amount):
    get_user_data(guild_id, user_id)
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE user_stats SET points = points + ? WHERE guild_id=? AND user_id=?", (amount, str(guild_id), str(user_id)))
    conn.commit()
    conn.close()

def save_match_data(guild_id, data):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("REPLACE INTO active_match (guild_id, match_data) VALUES (?, ?)", (str(guild_id), json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()

def load_match_data(guild_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT match_data FROM active_match WHERE guild_id=?", (str(guild_id),))
    res = c.fetchone()
    conn.close()
    return json.loads(res[0]) if res else {}

def get_google_client():
    if not os.path.exists('credentials.json'): return None
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    return gspread.authorize(creds)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎮 전장 및 영웅 기본 데이터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
    "전체": "https://cdn.discordapp.com/attachments/1508104373568274482/1508115279249543168/all.png",
    "호위": "https://cdn.discordapp.com/attachments/1508104373568274482/1508115373981962352/2026-05-24_232829.png",
    "혼합": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113692955377844/2026-05-24_232456.png",
    "쟁탈": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113692535816243/2026-05-24_232448.png",
    "밀기": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113693370617947/2026-05-24_232500.png",
    "플래시포인트": "https://cdn.discordapp.com/attachments/1508104373568274482/1508113693773398086/2026-05-24_232505.png"
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔄 봇 루프 및 이벤트 (멀티 서버 대응)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@tasks.loop(minutes=10)
async def voice_reward_loop():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            real_members = [m for m in vc.members if not m.bot]
            if len(real_members) >= 2:
                for member in real_members:
                    if not member.voice.afk and not member.voice.self_deaf:
                        reward = random.randint(1, 5)
                        update_user_points(guild.id, member.id, reward)

@bot.event
async def on_ready():
    print(f'로그인 성공: {bot.user.name} | 멀티 서버 기능 100% 복구 완료!')
    if not voice_reward_loop.is_running():
        voice_reward_loop.start()

@bot.event
async def on_message(message):
    if message.type == discord.MessageType.new_member:
        try:
            await message.delete()
            return
        except: pass
    if message.author.bot: return
    
    uid = str(message.author.id)
    now = time.time()
    if uid not in chat_cooldowns or (now - chat_cooldowns[uid]) >= 30:
        if message.guild:
            reward = random.randint(1, 5)
            update_user_points(message.guild.id, uid, reward)
            chat_cooldowns[uid] = now
        
    await bot.process_commands(message)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ 다중 서버 환경 세팅 및 데이터 동기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ServerSettingModal(discord.ui.Modal, title="⚙️ 멀티 서버 통합 세팅"):
    sheet_link = discord.ui.TextInput(label="구글 시트 링크 (안 쓰면 비워두세요)", placeholder="https://docs...", required=False)
    announce_ch = discord.ui.TextInput(label="공지 채널 ID", placeholder="예: 1234567890", required=True)
    lobby_ch = discord.ui.TextInput(label="대기실 음성 채널 ID", placeholder="예: 1234567890", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        sheet_key = ""
        link = self.sheet_link.value.strip()
        if link:
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', link)
            sheet_key = match.group(1) if match else link

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''INSERT INTO server_config (guild_id, sheet_key, announce_id, lobby_id)
                     VALUES (?, ?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET 
                     sheet_key=excluded.sheet_key, announce_id=excluded.announce_id, lobby_id=excluded.lobby_id''',
                  (gid, sheet_key, self.announce_ch.value.strip(), self.lobby_ch.value.strip()))
        conn.commit()
        conn.close()
        
        msg = f"✅ **[{interaction.guild.name}] 서버 세팅 완료!**\n📢 공지: <#{self.announce_ch.value.strip()}>\n🔊 대기실: <#{self.lobby_ch.value.strip()}>\n📊 시트 키: `{sheet_key if sheet_key else '연동 안함'}`"
        await interaction.response.send_message(msg, ephemeral=True)

@bot.command(name='서버세팅')
async def server_setup(ctx):
    if not ctx.author.guild_permissions.administrator: return
    view = discord.ui.View()
    btn = discord.ui.Button(label="⚙️ 서버 세팅 패널 열기", style=discord.ButtonStyle.primary)
    async def btn_cb(interaction):
        if not interaction.user.guild_permissions.administrator: return
        await interaction.response.send_modal(ServerSettingModal())
    btn.callback = btn_cb
    view.add_item(btn)
    await ctx.send("아래 버튼을 눌러 서버 환경을 설정하세요.", view=view)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👤 유저 자율 등록(!입장), 관리자 관리 및 부분 수정 UI (채팅형 흐름)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_ow_nickname(battletag):
    if not battletag or battletag == "-": return "-"
    return battletag.split('#')[0].strip()

async def sync_user_to_sheet(guild_id, member, db_data):
    cfg = get_server_config(guild_id)
    if not cfg or not cfg.get("sheet_key"): return
    
    uid = str(member.id)
    discord_nick = member.display_name.split(' (')[0] # 기존 괄호가 있다면 제거한 순수 디코 닉네임
    battletag = db_data.get('battletag', '-')
    ow_nick = get_ow_nickname(battletag)
    
    update_data = [
        "", # A열 (빈칸)
        uid, # B열: 디스코드 ID
        discord_nick, # C열: 디스코드 닉네임
        battletag, # D열: 배틀태그
        ow_nick, # E열: 오버워치 닉네임
        db_data.get('main_pos', '-'), # F열: 주 포지션
        db_data.get('sub_pos', '-'), # G열: 보조 포지션
        db_data.get('max_tier', '-'), # H열: 최고 티어
        db_data.get('current_tier', '-'), # I열: 현재 티어
        db_data.get('main_hero', '-'), # J열: 주 영웅
        db_data.get('score', 0.0) # K열: 내전 점수
    ]
    
    try:
        client = get_google_client()
        sheet = client.open_by_key(cfg["sheet_key"]).get_worksheet(0)
        rows = sheet.get_all_values()
        row_idx = -1
        for i, row in enumerate(rows):
            if i >= 5 and len(row) > 1 and row[1].strip() == uid: 
                row_idx = i + 1; break
                
        if row_idx != -1: sheet.update(f'A{row_idx}:K{row_idx}', [update_data])
        else: sheet.append_row(update_data, table_range='A6')
    except Exception as e:
        print(f"시트 연동 에러: {e}")

# --- 1단계: 포지션 & 티어 선택 뷰 ---
class PositionTierView(discord.ui.View):
    def __init__(self, db_data):
        super().__init__(timeout=120)
        self.result = db_data.copy()
        self.is_done = False
        
        pos_opts = [discord.SelectOption(label=x, value=x) for x in ["돌격", "공격", "지원", "자유"]]
        sub_pos_opts = pos_opts + [discord.SelectOption(label="없음", value="없음")]
        tier_opts = [discord.SelectOption(label=x, value=x) for x in ["언랭", "브론즈", "실버", "골드", "플래티넘", "다이아몬드", "마스터", "그랜드마스터", "챔피언"]]
        
        self.s1 = discord.ui.Select(placeholder="1. 주 포지션 선택", options=pos_opts, custom_id="m_pos")
        self.s2 = discord.ui.Select(placeholder="2. 보조 포지션 선택", options=sub_pos_opts, custom_id="s_pos")
        self.s3 = discord.ui.Select(placeholder="3. 최고 티어 선택", options=tier_opts, custom_id="max_t")
        self.s4 = discord.ui.Select(placeholder="4. 현재 티어 선택", options=tier_opts, custom_id="cur_t")
        
        async def cb(interaction):
            sel = interaction.data["custom_id"]
            val = interaction.data["values"][0]
            if sel == "m_pos": self.result['main_pos'] = val
            elif sel == "s_pos": self.result['sub_pos'] = val
            elif sel == "max_t": self.result['max_tier'] = val
            elif sel == "cur_t": self.result['current_tier'] = val
            await interaction.response.defer()
            
        for s in [self.s1, self.s2, self.s3, self.s4]: s.callback = cb; self.add_item(s)

    @discord.ui.button(label="➡️ 다음 단계로 (영웅 선택)", style=discord.ButtonStyle.primary, row=4)
    async def nxt(self, interaction: discord.Interaction, btn):
        self.is_done = True
        await interaction.response.defer()
        self.stop()

# --- 2단계: 모스트 영웅 선택 뷰 ---
class HeroSelectView(discord.ui.View):
    def __init__(self, db_data):
        super().__init__(timeout=120)
        self.result = db_data.copy()
        self.selected_heroes = []
        self.is_done = False
        
        async def cb(interaction):
            self.selected_heroes.extend(interaction.data["values"])
            await interaction.response.defer()

        for role, heroes in OW_HEROES.items():
            opts = [discord.SelectOption(label=h, value=h) for h in heroes[:25]]
            sel = discord.ui.Select(placeholder=f"{role} 모스트 영웅 (선택)", options=opts, min_values=0, max_values=3, custom_id=f"h_{role}")
            sel.callback = cb
            self.add_item(sel)

    @discord.ui.button(label="✅ 영웅 선택 완료", style=discord.ButtonStyle.success, row=3)
    async def nxt(self, interaction: discord.Interaction, btn):
        if self.selected_heroes:
            # 중복 제거 후 최대 3개까지만 텍스트로 저장
            self.result['main_hero'] = ", ".join(list(set(self.selected_heroes))[:3]) 
        self.is_done = True
        await interaction.response.defer()
        self.stop()

# --- 통합 흐름 제어 함수 ---
async def run_user_setup_flow(ctx, target_member, fields, is_admin):
    gid, uid = str(ctx.guild.id), str(target_member.id)
    db_data = get_user_data(gid, uid)
    
    def check_msg(m): return m.author == ctx.author and m.channel == ctx.channel

    # 1. 포지션 & 티어
    if 'all' in fields or 'pos_tier' in fields:
        view1 = PositionTierView(db_data)
        msg1 = await ctx.send(f"🔹 **[{target_member.display_name}]** 님의 포지션과 티어를 모두 선택한 후 `[다음 단계로]` 버튼을 눌러주세요.", view=view1)
        await view1.wait()
        if not view1.is_done: return await msg1.edit(content="⏳ 시간 초과로 취소되었습니다.", view=None)
        db_data.update(view1.result)
        await msg1.delete()

    # 2. 모스트 영웅
    if 'all' in fields or 'hero' in fields:
        view2 = HeroSelectView(db_data)
        msg2 = await ctx.send(f"🔹 **[{target_member.display_name}]** 님의 모스트 영웅을 골라주세요. (각 포지션별 복수 선택 가능)", view=view2)
        await view2.wait()
        if not view2.is_done: return await msg2.edit(content="⏳ 시간 초과로 취소되었습니다.", view=None)
        db_data.update(view2.result)
        await msg2.delete()

    # 3. 배틀태그 (텍스트 입력)
    if 'all' in fields or 'battletag' in fields:
        msg3 = await ctx.send(f"⌨️ **[{target_member.display_name}]** 님의 **배틀태그**를 채팅으로 입력해주세요. (예: 겐지장인#1234)\n*(건너뛰려면 `스킵` 입력)*")
        try:
            m = await bot.wait_for('message', check=check_msg, timeout=60.0)
            if m.content.strip() != "스킵":
                db_data['battletag'] = m.content.strip()
                db_data['nickname'] = target_member.display_name.split(' (')[0]
            await msg3.delete(); await m.delete(delay=1)
        except asyncio.TimeoutError: return await msg3.edit(content="⏳ 시간 초과로 취소되었습니다.")

    # 4. 내전 점수 (텍스트 입력, 관리자만 가능)
    if is_admin and ('all' in fields or 'score' in fields):
        msg4 = await ctx.send(f"🎯 **[{target_member.display_name}]** 님의 **내전 점수(1~100점)**를 채팅으로 입력해주세요.\n*(숫자만 입력)*")
        try:
            m = await bot.wait_for('message', check=check_msg, timeout=60.0)
            val = m.content.strip()
            if val.isdigit() and 1 <= int(val) <= 100:
                db_data['score'] = float(val)
            else:
                await ctx.send("⚠️ 점수는 1~100 사이의 숫자로만 저장됩니다. (기본값 유지됨)", delete_after=5)
            await msg4.delete(); await m.delete(delay=1)
        except asyncio.TimeoutError: return await msg4.edit(content="⏳ 시간 초과로 취소되었습니다.")

    # DB 저장
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''UPDATE user_stats SET nickname=?, battletag=?, score=?, main_pos=?, sub_pos=?, max_tier=?, current_tier=?, main_hero=? WHERE guild_id=? AND user_id=?''',
              (db_data['nickname'], db_data['battletag'], db_data['score'], db_data['main_pos'], db_data['sub_pos'], db_data['max_tier'], db_data['current_tier'], db_data['main_hero'], gid, uid))
    conn.commit()
    conn.close()

    # 시트 연동
    status_msg = await ctx.send("⏳ 데이터를 DB와 구글 시트에 저장하는 중입니다...")
    await sync_user_to_sheet(gid, target_member, db_data)

    # 닉네임 자동 변경 (권한 에러 예외 처리 포함)
    ow_nick = get_ow_nickname(db_data['battletag'])
    if ow_nick != "-":
        new_nick = f"{db_data['nickname']} ({ow_nick})"
        if len(new_nick) > 32: new_nick = new_nick[:32]
        try:
            await target_member.edit(nick=new_nick)
            nick_msg = f"\n✅ 서버 닉네임이 `{new_nick}`(으)로 자동 변경되었습니다."
        except discord.errors.Forbidden:
            nick_msg = f"\n⚠️ (봇 권한 문제로 닉네임 자동 변경은 생략되었습니다. 정보는 정상 저장됨!)"
    else:
        nick_msg = ""

    await status_msg.edit(content=f"🎉 **[{target_member.display_name}]** 님의 데이터 설정이 완벽하게 끝났습니다!{nick_msg}")


class EditTargetSelect(discord.ui.Select):
    # 💡 수정된 부분 1: __init__에 ctx를 받을 수 있도록 추가했습니다.
    def __init__(self, ctx, target_member, is_admin):
        self.ctx = ctx
        self.target_member = target_member
        self.is_admin = is_admin
        opts = [
            discord.SelectOption(label="전체 새로 입력", description="모든 정보를 백지부터 다시 기입합니다.", value="all"),
            discord.SelectOption(label="포지션 및 티어 수정", value="pos_tier"),
            discord.SelectOption(label="모스트 영웅 수정", value="hero"),
            discord.SelectOption(label="배틀태그 수정", value="battletag")
        ]
        if is_admin:
            opts.append(discord.SelectOption(label="내전 점수 수정", description="관리자 전용", value="score"))
            
        super().__init__(placeholder="수정할 항목을 선택해주세요...", min_values=1, max_values=len(opts), options=opts)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🔄 선택하신 항목의 수정을 시작합니다...", view=None)
        # 💡 수정된 부분 2: interaction.message 대신 self.ctx를 넘겨줍니다.
        await run_user_setup_flow(self.ctx, self.target_member, self.values, self.is_admin)

@bot.command(name='유저관리')
async def manage_user(ctx, member: discord.Member = None):
    if not is_admin(ctx): return await ctx.send("❌ 관리자만 사용할 수 있습니다.")
    if not member: return await ctx.send("❌ 사용법: `!유저관리 @유저명`")
    
    view = discord.ui.View()
    # 💡 수정된 부분 3: EditTargetSelect에 ctx를 전달합니다.
    view.add_item(EditTargetSelect(ctx, member, is_admin=True))
    await ctx.send(f"🛠️ **[{member.display_name}]** 유저 관리 패널입니다. 수정할 항목을 선택하세요.", view=view)

@bot.command(name='입장')
async def self_register(ctx):
    # 유저 자율 초기 등록 (점수 제외 all)
    await ctx.send(f"👋 환영합니다, **{ctx.author.display_name}**님! 내전 등록 절차를 시작합니다.")
    await run_user_setup_flow(ctx, ctx.author, ['all'], is_admin=False)

@bot.command(name='정보수정')
async def self_update(ctx):
    view = discord.ui.View()
    # 💡 수정된 부분 4: EditTargetSelect에 ctx를 전달합니다.
    view.add_item(EditTargetSelect(ctx, ctx.author, is_admin=False))
    await ctx.send(f"🔧 **[{ctx.author.display_name}]** 님의 정보 수정 패널입니다. 수정할 항목을 선택하세요.", view=view)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_sync_scores(guild_id):
    cfg = get_server_config(guild_id)
    if not cfg or not cfg.get("sheet_key"): return False
    try:
        client = get_google_client()
        sheet = client.open_by_key(cfg["sheet_key"]).get_worksheet(0)
        rows = sheet.get_all_values()
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        sync_count = 0
        for i in range(5, len(rows)):
            row = rows[i]
            if len(row) >= 2 and row[1].strip(): 
                nickname = row[0].strip() if len(row) > 0 else "-"
                uid = row[1].strip()
                score = float(row[2]) if len(row) > 2 and row[2].strip().replace('.','',1).isdigit() else 0.0
                main_pos = row[3].strip() if len(row) > 3 else "-"
                main_hero = row[4].strip() if len(row) > 4 else "-"
                battletag = row[3].strip() if len(row) > 3 else "-"
                c.execute('''UPDATE user_stats SET nickname=?, score=?, main_pos=?, main_hero=?, battletag=? WHERE guild_id=? AND user_id=?''', (nickname, score, main_pos, main_hero, battletag, str(guild_id), uid))
                if c.rowcount == 0:
                    c.execute('''INSERT INTO user_stats (guild_id, user_id, nickname, score, main_pos, main_hero, battletag) VALUES (?, ?, ?, ?, ?, ?, ?)''', (str(guild_id), uid, nickname, score, main_pos, main_hero, battletag))
                sync_count += 1
        conn.commit()
        conn.close()
        return sync_count
    except Exception as e: return False

@bot.command(name='동기화')
async def sync_data(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자만 사용할 수 있습니다.")
    msg = await ctx.send("🔄 구글 시트에서 최신 데이터를 긁어오는 중입니다...")
    res = await auto_sync_scores(ctx.guild.id)
    if res is False: await msg.edit(content="❌ 연동 실패 (시트 키 오류 또는 권한 없음).")
    else: await msg.edit(content=f"✅ **동기화 완료!** 시트 데이터({res}명)를 DB에 덮어씌웠습니다.")

class ResetConfirmView(discord.ui.View):
    def __init__(self, guild_id, ctx):
        super().__init__(timeout=60)
        self.guild_id = str(guild_id)
        self.ctx = ctx

    @discord.ui.button(label="✅ 확정 (데이터 전체 삭제)", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        await interaction.response.defer()
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("DELETE FROM user_stats WHERE guild_id=?", (self.guild_id,))
        conn.commit()
        conn.close()
        cfg = get_server_config(self.guild_id)
        sheet_msg = ""
        if cfg and cfg.get("sheet_key"):
            try:
                client = get_google_client()
                sheet = client.open_by_key(cfg["sheet_key"]).get_worksheet(0)
                rows = sheet.get_all_values()
                if len(rows) >= 6: 
                    # ✅ 행 자체를 삭제하지 않고, A열부터 M열까지의 '내용'만 싹 지웁니다.
                    # (지워야 하는 열이 더 넓다면 M 대신 Z 등으로 알파벳을 늘려주세요)
                    sheet.batch_clear([f'A6:M{len(rows)}']) 
                sheet_msg = "\n📊 구글 시트 데이터(6행부터)도 초기화되었습니다."
            except Exception as e: sheet_msg = f"\n⚠️ 구글 시트 삭제 중 오류 발생: {e}"
        for child in self.children: child.disabled = True
        await interaction.message.edit(content=f"💥 **서버 데이터베이스가 완전히 초기화되었습니다.**{sheet_msg}", view=self)

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        for child in self.children: child.disabled = True
        await interaction.message.edit(content="🛑 서버 초기화가 취소되었습니다.", view=self)

@bot.command(name='서버초기화')
async def reset_server(ctx):
    if not ctx.author.guild_permissions.administrator: return
    warning_msg = "⚠️ **[경고] 정말로 서버 데이터를 초기화하시겠습니까?**\n1. 유저 전적, 포인트, 출석 기록 모두 삭제\n2. 연동 구글 시트 6번째 줄부터 전체 삭제\n3. 이 작업은 복구 불가능합니다."
    await ctx.send(warning_msg, view=ResetConfirmView(ctx.guild.id, ctx))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💰 경제 시스템 및 유틸 명령어
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.command(name='출석')
async def daily_attendance(ctx):
    gid, uid = str(ctx.guild.id), str(ctx.author.id)
    data = get_user_data(gid, uid)
    today = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    
    if data.get("last_daily") == today: return await ctx.send(f"❌ **{ctx.author.display_name}**님, 오늘은 이미 출석하셨습니다!")
    reward = random.randint(10, 100)
    update_user_points(gid, uid, reward)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE user_stats SET last_daily=? WHERE guild_id=? AND user_id=?", (today, gid, uid))
    conn.commit()
    conn.close()
    
    bal = get_user_data(gid, uid).get("points", 0)
    await ctx.send(f"✅ **{ctx.author.display_name}**님 출석 완료! **{reward} P** 지급 (현재: {bal:,} P)")

@bot.command(name='구제')
async def relief_funds(ctx):
    gid, uid = str(ctx.guild.id), str(ctx.author.id)
    data = get_user_data(gid, uid)
    bal = data.get("points", 0)
    if bal > 100: return await ctx.send(f"❌ 잔액이 100 P 이하일 때만 사용 가능합니다. (현재: {bal:,} P)")
    
    today = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    if data.get("last_relief") == today: return await ctx.send("❌ 구제금은 하루에 한 번만 받을 수 있습니다.")
    
    update_user_points(gid, uid, 300)
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE user_stats SET last_relief=? WHERE guild_id=? AND user_id=?", (today, gid, uid))
    conn.commit()
    conn.close()
    
    new_bal = get_user_data(gid, uid).get("points", 0)
    await ctx.send(f"🚑 파산 구제금 **300 P** 지급! (현재: {new_bal:,} P)")

@bot.command(name='포인트')
async def manage_points(ctx, member: discord.Member, op: str):
    if not is_admin(ctx): return
    gid, uid = str(ctx.guild.id), str(member.id)
    current = get_user_data(gid, uid).get("points", 0)
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        if op.startswith('+'):
            val = int(op[1:])
            update_user_points(gid, uid, val)
        elif op.startswith('-'):
            val = int(op[1:])
            update_user_points(gid, uid, -val)
        elif op.startswith('='):
            val = int(op[1:])
            c.execute("UPDATE user_stats SET points=? WHERE guild_id=? AND user_id=?", (val, gid, uid))
            conn.commit()
        else: return await ctx.send("❌ 형식: `!포인트 @유저 +500` 또는 `=1000`")
        conn.close()
        new_pt = get_user_data(gid, uid).get("points", 0)
        await ctx.send(f"✅ **{member.display_name}**님의 포인트: `{current:,} P` ➡️ `{new_pt:,} P`")
    except: await ctx.send("❌ 숫자 형식이 잘못되었습니다.")

@bot.command(name='점수')
async def check_profile(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = get_user_data(str(ctx.guild.id), str(target.id))
    if not data or data.get('score', 0) == 0: return await ctx.send(f"❌ **{target.display_name}** 님의 전적 데이터가 없습니다.")
    
    embed = discord.Embed(title=f"📋 {target.display_name} 프로필", color=discord.Color.blue())
    embed.add_field(name="🎯 내전 점수", value=f"**{data.get('score', 0):g} 점**", inline=True)
    embed.add_field(name="💰 포인트", value=f"**{data.get('points', 0):,} P**", inline=True)
    embed.add_field(name="닉네임", value=data.get('nickname', '-'), inline=False)
    embed.add_field(name="주 영웅", value=data.get('main_hero', '-'), inline=True)
    embed.add_field(name="🏆 누적 전적", value=f"{data.get('losses', '-')} (승: {data.get('wins', '-')})", inline=False)
    embed.add_field(name="포지션", value=f"{data.get('main_pos', '-')} / {data.get('sub_pos', '-')}", inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='랭킹')
async def show_ranking(ctx):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM user_stats WHERE guild_id=?", (str(ctx.guild.id),))
    rows = c.fetchall()
    conn.close()

    rate_list = []
    for row in rows:
        record_str = str(row['losses'])
        nums = re.findall(r'\d+', record_str)
        wins, losses = (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (0, 0)
        if (wins + losses) >= 3:
            rate = (wins / (wins + losses)) * 100
            rate_list.append((row['nickname'], rate, wins, losses))
    rate_list.sort(key=lambda x: x[1], reverse=True)

    pt_list = sorted([r for r in rows if r['points'] > 0], key=lambda x: x['points'], reverse=True)[:10]
    
    embed = discord.Embed(title="🏆 통합 랭킹", color=discord.Color.gold())
    rate_text = ""
    for i, (nick, rate, w, l) in enumerate(rate_list[:10]): rate_text += f"**{i+1}위.** {nick} - {rate:.1f}% ({w}승 {l}패)\n"
    if not rate_text: rate_text = "조건(최소 3판) 달성자 없음."
    embed.add_field(name="⚔️ 승률 랭킹 (TOP 10)", value=rate_text, inline=False)

    pt_text = ""
    for i, row in enumerate(pt_list): pt_text += f"**{i+1}위.** {row['nickname']} - {row['points']:,} P\n"
    if not pt_text: pt_text = "기록이 없습니다."
    embed.add_field(name="💰 포인트 랭킹 (TOP 10)", value=pt_text, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='명령어')
async def show_help(ctx):
    embed = discord.Embed(title="🤖 내전 마스터 봇 안내서", color=discord.Color.gold())
    embed.add_field(name="`!점수` / `!점수 @유저`", value="유저의 상세 내전 프로필과 전적, 점수를 확인합니다.", inline=False)
    embed.add_field(name="`!맵`", value="내전 전장 선택 및 무작위 룰렛을 돌립니다.", inline=False)
    embed.add_field(name="`!동기화` (관리자)", value="구글 시트의 정보를 실시간으로 봇 DB에 덮어씌웁니다.", inline=False)
    embed.add_field(name="`!내전시작` (관리자)", value="인원 제외, 조건 분배, 밴픽, 워크샵 생성을 진행합니다.", inline=False)
    embed.add_field(name="`!테스트시작` (관리자)", value="DB 인원을 가상으로 불러와 밸런싱을 테스트합니다.", inline=False)
    embed.add_field(name="`!대기실복귀` (관리자)", value="팀 채널에 흩어진 유저들을 대기실로 불러옵니다.", inline=False)
    embed.add_field(name="`!서버세팅` / `!유저관리` (관리자)", value="서버 환경과 유저 DB를 설정합니다.", inline=False)
    embed.add_field(name="`!귀여워`", value="비밀 이스터에그 🐾", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='귀여워')
async def show_cute_instagram(ctx):
    await ctx.send("🐾 https://www.instagram.com/i.rang0321/")

@bot.command(name='청소')
async def clear_messages(ctx, amount: int):
    if not is_admin(ctx): return
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 최근 채팅 **{amount}개** 삭제!")
    await msg.delete(delay=3)

@bot.command(name='관리자추가')
async def add_admin(ctx, member: discord.Member):
    if not ctx.author.guild_permissions.administrator: return
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO server_admins (guild_id, user_id) VALUES (?, ?)", (str(ctx.guild.id), str(member.id)))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ **{member.display_name}** 님이 이 서버의 관리자로 등록되었습니다.")

@bot.command(name='공지채널설정')
async def set_announce(ctx):
    if not is_admin(ctx): return
    update_server_config(ctx.guild.id, 'announce_id', ctx.channel.id)
    await ctx.send(f'📢 **{ctx.channel.name}** 채널 [공지 채널] 등록 완료.')

@bot.command(name='대기실설정')
async def set_lobby(ctx):
    if not is_admin(ctx) or not ctx.author.voice: return
    update_server_config(ctx.guild.id, 'lobby_id', ctx.author.voice.channel.id)
    await ctx.send(f'📢 **{ctx.author.voice.channel.name}** 채널 [대기실] 등록 완료.')

@bot.command(name='팀채널설정')
async def set_team_channel(ctx, team_num: int):
    if not is_admin(ctx) or not ctx.author.voice: return
    if team_num not in [1,2,3,4]: return await ctx.send("1~4팀까지만 설정 가능합니다.")
    update_server_config(ctx.guild.id, f't{team_num}_id', ctx.author.voice.channel.id)
    await ctx.send(f'📢 **{ctx.author.voice.channel.name}** 채널 [{team_num}팀] 등록 완료.')

@bot.command(name='대기실복귀')
async def return_to_lobby(ctx):
    if not is_admin(ctx): return
    cfg = get_server_config(ctx.guild.id)
    if not cfg or not cfg.get('lobby_id'): return await ctx.send("❌ 대기실 설정 필요")
    lobby_channel = bot.get_channel(int(cfg['lobby_id']))
    status_msg = await ctx.send("⏳ 유저 이동 중...")
    success = 0
    for i in range(1, 5):
        t_id = cfg.get(f't{i}_id')
        if t_id and bot.get_channel(int(t_id)):
            for member in bot.get_channel(int(t_id)).members:
                if not member.bot:
                    try: await member.move_to(lobby_channel); success += 1
                    except: pass
    await status_msg.edit(content=f"✅ 총 **{success}명** 대기실 복귀 완료!")

@bot.command(name='비밀초대')
async def secret_invite(ctx, guild_id: int = None):
    if ctx.guild is not None: return 
    if not bot.guilds: return await ctx.send("❌ 봇이 어떤 서버에도 소속되어 있지 않습니다.")
    if guild_id is None:
        server_list = "\n".join([f"• **{g.name}** (ID: `{g.id}`)" for g in bot.guilds])
        return await ctx.send(f"📋 **봇이 소속된 서버 목록**\n{server_list}\n\n💡 `!비밀초대 [서버ID]`")
    target_guild = bot.get_guild(guild_id)
    if not target_guild: return await ctx.send("❌ 서버를 찾을 수 없습니다.")
    for channel in target_guild.text_channels:
        try:
            inv = await channel.create_invite(max_age=300, max_uses=1, unique=True, reason="비밀 방장 호출")
            return await ctx.send(f"🎟️ **[{target_guild.name}]** 1회용 초대:\n{inv.url}")
        except: continue
    await ctx.send("❌ 초대장 권한이 없습니다.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎲 맵 및 내전 밸런싱 로직 (특수 조건 복구)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class MapDetailSelect(discord.ui.Select):
    def __init__(self, mode):
        self.mode = mode
        options = [discord.SelectOption(label="🎲 무작위", value="랜덤")] + [discord.SelectOption(label=m, value=m) for m in OW_MAPS[mode]]
        super().__init__(placeholder=f"{mode} 전장을 고르세요...", options=options[:25])
    async def callback(self, interaction: discord.Interaction):
        result = random.choice(OW_MAPS[self.mode]) if self.values[0] == "랜덤" else self.values[0]
        embed = discord.Embed(title=f"✅ [{self.mode}] 전장 확정!", description=f"**{result}**", color=discord.Color.green())
        if result in MAP_IMAGES: embed.set_image(url=MAP_IMAGES[result])
        await interaction.response.edit_message(embed=embed, view=None)

class MapModeSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="모드 선택...", options=[discord.SelectOption(label=k, value=k) for k in OW_MAPS.keys()] + [discord.SelectOption(label="🎲 전체 랜덤", value="전체랜덤")])
    async def callback(self, interaction: discord.Interaction):
        mode = self.values[0]
        if mode == "전체랜덤":
            all_maps = [m for maps in OW_MAPS.values() for m in maps]
            result = random.choice(all_maps)
            fm = [k for k, v in OW_MAPS.items() if result in v][0]
            embed = discord.Embed(title="🎲 전체 무작위!", description=f"**[{fm}] {result}**", color=discord.Color.gold())
            if result in MAP_IMAGES: embed.set_image(url=MAP_IMAGES[result])
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(title=f"🗺️ {mode} 전장 선택", color=discord.Color.blue())
            if mode in MODE_IMAGES: embed.set_image(url=MODE_IMAGES[mode])
            view = discord.ui.View()
            view.add_item(MapDetailSelect(mode))
            await interaction.response.edit_message(embed=embed, view=view)

@bot.command(name='맵')
async def select_map(ctx):
    embed = discord.Embed(title="🗺️ 전장 선택기", color=discord.Color.dark_gray())
    embed.set_image(url=MODE_IMAGES["전체"])
    view = discord.ui.View()
    view.add_item(MapModeSelect())
    await ctx.send(embed=embed, view=view)

def build_horizontal_embed(teams, team_count, guild_id, title="🎲 내전 팀 구성 결과"):
    team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
    embed = discord.Embed(title=title, color=discord.Color.gold())
    for i in range(team_count):
        if i >= len(teams): break
        team = teams[i]
        t_score = sum(float(get_user_data(guild_id, p.id).get("score", 0)) for p in team)
        avg = round(t_score / len(team), 1) if team else 0
        members_text = "\n".join([f"{p.mention} ({get_user_data(guild_id, p.id).get('score', 0):g}점)" for p in team]) if team else "없음"
        embed.add_field(name=f"{team_colors[i]} (평균 {avg})", value=members_text, inline=True)
    return embed

def generate_workshop_code(teams, banned_heroes, guild_id):
    ws_text = "```javascript\n// 워크샵 스크립트 (복사해서 붙여넣기)\n"
    ws_text += "variables {\n  global:\n    0: Team1_Names\n    1: Team2_Names\n    2: Team3_Names\n    3: Team4_Names\n    4: Banned_Heroes\n}\n\n"
    def get_ingame_names(team_members):
        names = []
        for p in team_members:
            btag = get_user_data(guild_id, p.id).get("battletag", "-")
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
    ws_text += 'rule("내전 시스템: 팀 분배") {\n  event { Ongoing - Each Player; All; All; }\n  action {\n'
    ws_text += '    If(Array Contains(Global.Team1_Names, Custom String("{0}", Event Player)));\n      Move Player to Team(Event Player, Team 1, -1);\n'
    ws_text += '    Else If(Array Contains(Global.Team2_Names, Custom String("{0}", Event Player)));\n      Move Player to Team(Event Player, Team 2, -1);\n    End;\n  }\n}\n'
    ws_text += 'rule("내전 시스템: 영웅 밴픽 제한") {\n  event { Ongoing - Each Player; All; All; }\n  condition { Has Spawned(Event Player) == True; }\n  action {\n'
    ws_text += '    Set Player Allowed Heroes(Event Player, Remove From Array(Allowed Heroes(Event Player), Global.Banned_Heroes));\n  }\n}\n```'
    return ws_text

def pack_match_data(teams, guild_id):
    def get_fields(team):
        return ([p.display_name for p in team], [str(p.id) for p in team], [get_user_data(guild_id, p.id).get('battletag', '-') for p in team])
    t1_n, t1_i, t1_b = get_fields(teams[0]) if len(teams) > 0 else ([], [], [])
    t2_n, t2_i, t2_b = get_fields(teams[1]) if len(teams) > 1 else ([], [], [])
    return {"t1_nicks": t1_n, "t1_ids": t1_i, "t1_btags": t1_b, "t2_nicks": t2_n, "t2_ids": t2_i, "t2_btags": t2_b}

# 💡 [복구완료] 특수 조건 밸런싱 알고리즘
def divide_teams_with_conditions(members, t_count, guild_id, conditions):
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

    rival_graph = {i: set() for i in range(len(sn_list))}
    for u1, u2 in conditions['rivals']:
        if u1 in parent and u2 in parent:
            r1, r2 = find(u1), find(u2)
            if r1 == r2: return None, f"❌ 모순된 조건: <@{u1}>님과 <@{u2}>님은 듀오이자 라이벌입니다!"
            idx1, idx2 = list(super_nodes.keys()).index(r1), list(super_nodes.keys()).index(r2)
            rival_graph[idx1].add(idx2)
            rival_graph[idx2].add(idx1)

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
        sn_score = sum(float(get_user_data(guild_id, m.id).get("score", 0)) for m in sn)

        for t_idx in range(t_count):
            if any(existing in rival_graph[node_idx] for existing in teams_sn[t_idx]): continue
            teams_sn[t_idx].append(node_idx)
            team_scores[t_idx] += sn_score
            team_sizes[t_idx] += sn_size
            dfs(node_idx + 1)
            teams_sn[t_idx].pop()
            team_scores[t_idx] -= sn_score
            team_sizes[t_idx] -= sn_size

    dfs(0)
    if not best_teams: return None, "❌ 조건을 모두 만족하며 팀을 나눌 방법이 없습니다."
    return best_teams, None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ 밴픽, 배팅, 다전제 UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class BetModal(discord.ui.Modal, title="💰 포인트 배팅"):
    amount_input = discord.ui.TextInput(label="금액 (10 이상 또는 '올인')", placeholder="예: 500, 올인")

    def __init__(self, team_name, view):
        super().__init__()
        self.team_name = team_name
        self.b_view = view

    async def on_submit(self, interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        g_bet = get_betting(gid)
        if not g_bet.active: return await interaction.response.send_message("❌ 배팅 마감됨.", ephemeral=True)
        uid = str(interaction.user.id)
        
        is_player, my_team_name = False, None
        for i, team in enumerate(self.b_view.teams):
            if any(uid == str(p.id) for p in team):
                is_player, my_team_name = True, f"{i+1}팀"
                break
        if is_player and self.team_name != my_team_name:
            return await interaction.response.send_message(f"❌ 선수는 속한 **{my_team_name}**에만 걸 수 있습니다!", ephemeral=True)
        opp_team = "2팀" if self.team_name == "1팀" else "1팀"
        if uid in g_bet.bets[opp_team]: return await interaction.response.send_message("❌ 양방향 배팅 불가!", ephemeral=True)

        bal = get_user_data(gid, uid).get("points", 0)
        val = self.amount_input.value.strip()
        if val == "올인": bet_amt = bal
        elif val.isdigit(): bet_amt = int(val)
        else: return await interaction.response.send_message("❌ 숫자 입력 필요.", ephemeral=True)

        if bet_amt <= 9: return await interaction.response.send_message("❌ 10 P 이상 배팅.", ephemeral=True)
        if bet_amt > bal: return await interaction.response.send_message("❌ 잔액 부족!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        update_user_points(gid, uid, -bet_amt)
        g_bet.bets[self.team_name][uid] = g_bet.bets[self.team_name].get(uid, 0) + bet_amt

        await self.b_view.update_msg()
        await interaction.followup.send(f"✅ **{bet_amt:,} P** 배팅 완료! (잔액: {bal - bet_amt:,} P)", ephemeral=True)

class BettingView(discord.ui.View):
    def __init__(self, msg, teams, embed):
        super().__init__(timeout=None)
        self.msg, self.teams, self.embed = msg, teams, embed
        gid = str(msg.guild.id)
        g_bet = get_betting(gid)
        g_bet.active, g_bet.bets, g_bet.ann_msg = True, {"1팀": {}, "2팀": {}}, msg
        bot.loop.create_task(self.timer_task(gid))

    async def timer_task(self, gid):
        await asyncio.sleep(300)
        g_bet = get_betting(gid)
        if g_bet.active:
            g_bet.active = False
            for child in self.children: child.disabled = True
            try:
                p1 = sum(g_bet.bets["1팀"].values())
                p2 = sum(g_bet.bets["2팀"].values())
                self.embed.set_footer(text=f"⏳ 배팅 마감 | 🔴 1팀: {p1:,} P | 🔵 2팀: {p2:,} P")
                await g_bet.ann_msg.edit(embed=self.embed, view=self)
            except: pass

    async def update_msg(self):
        gid = str(self.msg.guild.id)
        g_bet = get_betting(gid)
        p1, p2 = sum(g_bet.bets["1팀"].values()), sum(g_bet.bets["2팀"].values())
        try:
            self.embed.set_footer(text=f"💰 실시간 풀 | 🔴 1팀: {p1:,} P | 🔵 2팀: {p2:,} P | (5분 후 마감)")
            await g_bet.ann_msg.edit(embed=self.embed)
        except: pass

    @discord.ui.button(label="🔴 1팀 배팅", style=discord.ButtonStyle.danger)
    async def bet_t1(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(BetModal("1팀", self))
    @discord.ui.button(label="🔵 2팀 배팅", style=discord.ButtonStyle.primary)
    async def bet_t2(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.send_modal(BetModal("2팀", self))

class AdminControlPanel(discord.ui.View):
    def __init__(self, teams, set_count=1, ann_msg_obj=None, ws_code="", captains=None):
        super().__init__(timeout=None)
        self.teams, self.set_count, self.ann_msg_obj, self.ws_code, self.captains = teams, set_count, ann_msg_obj, ws_code, captains
        styles = [discord.ButtonStyle.danger, discord.ButtonStyle.primary, discord.ButtonStyle.success, discord.ButtonStyle.secondary]
        emojis = ["🔴", "🔵", "🟢", "🟡"]
        for i in range(len(teams)):
            self.add_item(discord.ui.Button(label=f"{i+1}팀 승리", style=styles[i], emoji=emojis[i], custom_id=f"win_{i}", row=0))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if "win_" in interaction.data["custom_id"]:
            t_idx = int(interaction.data["custom_id"].split("_")[1])
            await self.record_result(interaction, f"{t_idx+1}팀", t_idx)
        return True

    async def record_result(self, interaction, winner, team_idx):
        await interaction.response.defer()
        gid = str(interaction.guild.id)
        status_msg = await interaction.followup.send(f"⏳ 전적 기록 및 배팅 정산 중...", ephemeral=True)
        g_bet = get_betting(gid)
        if g_bet.active: g_bet.active = False
        
        for i, team in enumerate(self.teams):
            reward = 300 if i == team_idx else 100
            for p in team: update_user_points(gid, p.id, reward)

        p_win, p_lose = sum(g_bet.bets[winner].values()), sum(g_bet.bets["1팀" if winner=="2팀" else "2팀"].values())
        bet_results_text = ""
        if p_win > 0:
            if p_lose == 0:
                for uid, amt in g_bet.bets[winner].items(): update_user_points(gid, uid, amt)
                bet_results_text = "\n💸 원금 반환됨."
            else:
                ratio = p_lose / p_win
                for uid, amt in g_bet.bets[winner].items(): update_user_points(gid, uid, amt + int(amt*ratio))
                bet_results_text = f"\n📈 적중 배당률: 1.0 + {ratio:.2f}배"
                    
        if self.ann_msg_obj:
            try:
                embed = self.ann_msg_obj.embeds[0]
                colors = [discord.Color.red(), discord.Color.blue(), discord.Color.green(), discord.Color.gold()]
                embed.color = colors[team_idx]
                embed.title = f"🏆 [{self.set_count}세트 최종 결과] {winner} 승리!"
                await self.ann_msg_obj.edit(content=f"🎉 **{winner} 승리!**" + bet_results_text, embed=embed, view=None)
            except: pass

        cfg = get_server_config(gid)
        client = get_google_client()
        if client and cfg.get("sheet_key"):
            try:
                record_sheet = client.open_by_key(cfg["sheet_key"]).worksheet("전적")
                match_data = load_match_data(gid)
                kst_time = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
                row_data = [kst_time, f"{winner} 승리", 
                            ", ".join(match_data.get('t1_nicks', [])), ", ".join(match_data.get('t1_ids', [])), ", ".join(match_data.get('t1_btags', [])),
                            ", ".join(match_data.get('t2_nicks', [])), ", ".join(match_data.get('t2_ids', [])), ", ".join(match_data.get('t2_btags', []))]
                record_sheet.append_row(row_data)
                await asyncio.sleep(2)
                await auto_sync_scores(gid)
            except Exception: pass
            
        for c in self.children: c.disabled = True
        await interaction.message.edit(content=f"✅ **[{self.set_count}세트 완료]**", view=self)
        
        # 💡 [복구완료] 다전제 다음 세트 질문 UI
        await interaction.channel.send(content=f"🔄 동일한 멤버로 다음 세트를 진행하시겠습니까?", view=NextSetConfirmView(self.teams, self.captains, self.set_count, self.ws_code, self.ann_msg_obj))
        await status_msg.edit(content="✅ 처리 완료!")

    @discord.ui.button(label="🔊 음성 분배", style=discord.ButtonStyle.secondary, row=1)
    async def move_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cfg = get_server_config(interaction.guild.id)
        success = 0
        for i, team in enumerate(self.teams):
            ch_id = cfg.get(f't{i+1}_id')
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if hasattr(p, 'voice') and p.voice:
                        try: await p.move_to(bot.get_channel(int(ch_id))); success += 1
                        except: pass
        await interaction.followup.send(f"✅ 음성 채널 분배 완료 ({success}명)!", ephemeral=True)

    @discord.ui.button(label="🛠️ 코드 DM 받기", style=discord.ButtonStyle.secondary, row=1)
    async def send_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.send(f"🛠️ **워크샵 연동 코드 ({self.set_count}세트)**\n{self.ws_code}")
            await interaction.response.send_message("✅ DM 전송 완료!", ephemeral=True)
        except: await interaction.response.send_message("❌ DM 전송 실패.", ephemeral=True)

    @discord.ui.button(label="↩️ 대기실 복귀", style=discord.ButtonStyle.danger, row=2)
    async def return_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cfg = get_server_config(interaction.guild.id)
        if cfg.get("lobby_id") and bot.get_channel(int(cfg["lobby_id"])):
            lobby = bot.get_channel(int(cfg["lobby_id"]))
            for t in self.teams:
                for p in t:
                    if hasattr(p, 'voice') and p.voice:
                        try: await p.move_to(lobby)
                        except: pass
        await interaction.followup.send("✅ 복귀 완료!", ephemeral=True)
        
    @discord.ui.button(label="🛑 경기 무효 (전액 환불)", style=discord.ButtonStyle.danger, row=2)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        gid = str(interaction.guild.id)
        g_bet = get_betting(gid)
        if g_bet.active: g_bet.active = False
        refund_count = 0
        for t in ["1팀", "2팀"]:
            for uid, amt in g_bet.bets[t].items():
                update_user_points(gid, uid, amt)
                refund_count += 1
        if self.ann_msg_obj:
            try:
                embed = self.ann_msg_obj.embeds[0]
                embed.color = discord.Color.dark_gray()
                embed.title = f"🛑 [{self.set_count}세트] 경기 무효"
                await self.ann_msg_obj.edit(content=f"🚨 **경기가 무효 처리되어 {refund_count}건의 포인트가 환불되었습니다.**", embed=embed, view=None)
            except: pass
        for child in self.children: child.disabled = True
        await interaction.message.edit(content="🛑 경기 무효 처리 완료.", view=self)

# 💡 [복구완료] 다전제 세트 진행 뷰
class NextSetConfirmView(discord.ui.View):
    def __init__(self, teams, captains, set_count=1, ws_code="", ann_msg_obj=None):
        super().__init__(timeout=None)
        self.teams, self.captains, self.set_count = teams, captains, set_count
        self.ws_code, self.ann_msg_obj = ws_code, ann_msg_obj

    @discord.ui.button(label="⏩ 밴픽 건너뛰고 바로 공지 (다음 세트)", style=discord.ButtonStyle.secondary, row=0)
    async def next_set_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_set = self.set_count + 1
        cfg = get_server_config(interaction.guild.id)
        ann_ch = bot.get_channel(int(cfg['announce_id'])) if cfg.get('announce_id') else interaction.channel
        
        kst_time = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        ann_title = f"⚔️ [{next_set}세트] 공식 라인업 ({kst_time})"
        embed = build_horizontal_embed(self.teams, len(self.teams), interaction.guild.id, ann_title)
        
        ann_msg = await ann_ch.send(content=f"📢 **제 {next_set}세트 매치가 곧 시작됩니다. 5분간 배팅 진행!**", embed=embed)
        bet_view = BettingView(ann_msg, self.teams, embed)
        await ann_msg.edit(view=bet_view)
        await bet_view.update_msg()
        
        await interaction.response.edit_message(content=f"⚙️ **[방장 컨트롤 패널 - {next_set}세트]**", view=AdminControlPanel(self.teams, next_set, ann_msg, self.ws_code, self.captains))
        
    @discord.ui.button(label="🚫 다시 밴픽하기 (다음 세트)", style=discord.ButtonStyle.danger, row=0)
    async def next_set_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_set = self.set_count + 1
        if not self.captains: return await interaction.response.send_message("❌ 주장 정보가 없어 밴픽을 열 수 없습니다.", ephemeral=True)
        view = discord.ui.View()
        view.add_item(DirectSelectBanCount(self.captains, self.teams, interaction.channel, next_set))
        await interaction.response.edit_message(content=f"⚖️ [{next_set}세트] 영웅 밴픽 개수를 정해주세요.", view=view)


class BanRoleSelect(discord.ui.Select):
    def __init__(self, role, heroes, parent_view):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=h, value=h) for h in heroes if h not in parent_view.banned_heroes]
        super().__init__(placeholder=f"🚫 [{role}] 밴 선택 ({len(parent_view.banned_heroes)}/{parent_view.max_bans}개)", options=options[:25], custom_id=f"ban_select_{role}")
    
    async def callback(self, interaction: discord.Interaction):
        view = self.parent_view
        if not (is_admin(interaction) or interaction.user.id in [c.id for c in view.captains]):
            return await interaction.response.send_message("❌ 밴픽 권한이 없습니다.", ephemeral=True)
        view.banned_heroes.append(self.values[0])
        
        if len(view.banned_heroes) >= view.max_bans:
            gid = str(interaction.guild.id)
            save_match_data(gid, pack_match_data(view.teams, gid))
            
            embed = build_horizontal_embed(view.teams, len(view.teams), gid, f"⚔️ [{view.set_cnt}세트] 라인업")
            embed.add_field(name="🚫 금지 영웅", value=", ".join(view.banned_heroes), inline=False)
            await interaction.response.edit_message(content="📢 **5분간 배팅 진행!**", embed=embed, view=None)
            
            ann_msg = await interaction.original_response() 
            bet_view = BettingView(ann_msg, view.teams, embed)
            await ann_msg.edit(view=bet_view)
            await bet_view.update_msg()
            
            ws_code = generate_workshop_code(view.teams, view.banned_heroes, gid)
            await view.admin_ch.send(f"⚙️ **방장 컨트롤 패널 ({view.set_cnt}세트)**", view=AdminControlPanel(view.teams, view.set_cnt, ann_msg, ws_code, view.captains))
        else:
            view.update_selects()
            embed = build_horizontal_embed(view.teams, len(view.teams), interaction.guild.id, f"🏆 [{view.set_cnt}세트] 밴픽 진행 중")
            embed.add_field(name="🚫 현재 금지 영웅", value=", ".join(view.banned_heroes), inline=False)
            await interaction.response.edit_message(embed=embed, view=view)

class BanPickView(discord.ui.View):
    def __init__(self, caps, teams, ban_cnt, admin_ch, set_cnt):
        super().__init__(timeout=None)
        self.caps, self.teams, self.max_bans, self.admin_ch, self.set_cnt = caps, teams, ban_cnt*len(teams), admin_ch, set_cnt
        self.banned_heroes = []
        self.update_selects()

    def update_selects(self):
        self.clear_items()
        for role, heroes in OW_HEROES.items():
            av = [h for h in heroes if h not in self.banned_heroes]
            if av: self.add_item(BanRoleSelect(role, av, self))

class BanPickAdminPanel(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=None)
        self.teams = teams
    @discord.ui.button(label="🔊 음성 채널 분배", style=discord.ButtonStyle.secondary, row=0)
    async def move_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cfg = get_server_config(interaction.guild.id)
        success = 0
        for i, team in enumerate(self.teams):
            ch_id = cfg.get(f't{i+1}_id')
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if hasattr(p, 'voice') and p.voice:
                        try: await p.move_to(bot.get_channel(int(ch_id))); success += 1
                        except: pass
        await interaction.followup.send(f"✅ 분배 완료 ({success}명)!", ephemeral=True)

class DirectSelectBanCount(discord.ui.Select):
    def __init__(self, caps, tms, admin_ch, set_cnt):
        self.caps, self.tms, self.admin_ch, self.set_cnt = caps, tms, admin_ch, set_cnt
        super().__init__(placeholder="팀당 몇 명 밴?", options=[discord.SelectOption(label=f"팀당 {i} 밴", value=str(i)) for i in range(1, 4)])
    async def callback(self, inter: discord.Interaction):
        cnt = int(self.values[0])
        cfg = get_server_config(inter.guild.id)
        ann_ch = bot.get_channel(int(cfg['announce_id'])) if cfg.get('announce_id') else inter.channel
        
        bp_view = BanPickView(self.caps, self.tms, cnt, self.admin_ch, self.set_cnt)
        embed = build_horizontal_embed(self.tms, len(self.tms), inter.guild.id, f"🏆 [{self.set_cnt}세트] 밴픽 중")
        msg = f"👑 **주장:** " + " / ".join([c.mention for c in self.caps])
        
        await ann_ch.send(content=msg, embed=embed, view=bp_view)
        await self.admin_ch.send(content="⚙️ **[밴픽 대기 중 - 작전회의 패널]**", view=BanPickAdminPanel(self.tms))
        await inter.response.edit_message(content="✅ 공지 채널에 밴픽 띄움!", view=None)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👥 팀 밸런스 흐름 및 조건 UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ManualCaptainSelectView(discord.ui.View):
    def __init__(self, teams, set_count=1):
        super().__init__(timeout=None)
        self.teams, self.set_count = teams, set_count
        self.caps = [None] * len(teams)
        
        for i, team in enumerate(teams):
            if i >= 4: break
            options = [discord.SelectOption(label=p.display_name, value=str(p.id)) for p in team]
            sel = discord.ui.Select(placeholder=f"👑 {i+1}팀 주장 선택...", options=options, custom_id=f"cap_{i}")
            sel.callback = self.make_cb(i, sel)
            self.add_item(sel)

    def make_cb(self, idx, sel):
        async def cb(inter: discord.Interaction):
            self.caps[idx] = inter.guild.get_member(int(sel.values[0]))
            await inter.response.defer()
        return cb

    @discord.ui.button(label="🚫 밴픽 시작", style=discord.ButtonStyle.danger, row=4)
    async def go_banpick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if None in self.caps: return await interaction.response.send_message("❌ 모든 팀 주장 선택 필요!", ephemeral=True)
        view = discord.ui.View()
        view.add_item(DirectSelectBanCount(self.caps, self.teams, interaction.channel, self.set_count))
        await interaction.response.edit_message(content="⚖️ 밴픽 개수 정하기", view=view)

# 💡 [복구완료] 수동 팀원 교환 기능
class SwapView(discord.ui.View):
    def __init__(self, teams, members, conditions, set_count=1):
        super().__init__(timeout=None)
        self.teams, self.members, self.conditions, self.set_count = teams, members, conditions, set_count
        options = [discord.SelectOption(label=p.display_name, value=str(p.id)) for t in teams for p in t]
        self.s1 = discord.ui.Select(placeholder="🔄 첫 번째 유저...", options=options[:25], custom_id="swap_1")
        self.s2 = discord.ui.Select(placeholder="🔄 두 번째 유저...", options=options[:25], custom_id="swap_2")
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
        
        embed = build_horizontal_embed(self.teams, len(self.teams), interaction.guild.id, f"⚖️ 수동 교체됨")
        await interaction.response.edit_message(content="✅ 교환 완료!", embed=embed, view=MoveConfirmView(self.teams, self.members, self.conditions, self.set_count))

class MoveConfirmView(discord.ui.View):
    def __init__(self, teams, members, conditions, set_count=1):
        super().__init__(timeout=None)
        self.teams, self.members, self.conditions, self.set_count = teams, members, conditions, set_count

    @discord.ui.button(label="🔄 조건유지 리롤", style=discord.ButtonStyle.blurple)
    async def reroll_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        new_teams, err = divide_teams_with_conditions(self.members, len(self.teams), str(interaction.guild.id), self.conditions)
        if err: return await interaction.followup.send(err, ephemeral=True)
        self.teams = new_teams
        embed = build_horizontal_embed(self.teams, len(self.teams), interaction.guild.id, "⚖️ 리롤됨")
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="👥 수동 팀원 교체", style=discord.ButtonStyle.secondary)
    async def manual_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🔄 맞교환할 인원 선택", view=SwapView(self.teams, self.members, self.conditions, self.set_count))
        
    @discord.ui.button(label="👑 [최종 확정] 주장 선택", style=discord.ButtonStyle.danger, row=1)
    async def finalize_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = get_server_config(interaction.guild.id)
        if not cfg.get("announce_id"): return await interaction.response.send_message("❌ `!공지채널설정` 필요", ephemeral=True)
        await interaction.response.edit_message(content="👑 주장 선출", embed=None, view=ManualCaptainSelectView(self.teams, self.set_count))

    @discord.ui.button(label="⏩ 밴픽 건너뛰기 (바로 공지)", style=discord.ButtonStyle.gray, row=1)
    async def skip_banpick(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = get_server_config(interaction.guild.id)
        gid = str(interaction.guild.id)
        save_match_data(gid, pack_match_data(self.teams, gid))
        ann_msg_obj = None
        if cfg.get("announce_id"):
            ann_ch = bot.get_channel(int(cfg['announce_id']))
            kst_time = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
            embed = build_horizontal_embed(self.teams, len(self.teams), gid, f"⚔️ [{self.set_count}세트] 공식 라인업")
            ann_msg_obj = await ann_ch.send(content="📢 **5분간 배팅 진행!**", embed=embed)
            bet_view = BettingView(ann_msg_obj, self.teams, embed)
            await ann_msg_obj.edit(view=bet_view)
            await bet_view.update_msg()
            
        ws_code = generate_workshop_code(self.teams, [], gid)
        await interaction.response.edit_message(content=f"⚙️ **[방장 컨트롤 패널]**", view=AdminControlPanel(self.teams, self.set_count, ann_msg_obj, ws_code))


class TeamDivideButton(discord.ui.Button):
    def __init__(self, t_count, members, conditions):
        super().__init__(label="🎲 밸런스 매칭 실행", style=discord.ButtonStyle.primary)
        self.t_count, self.members, self.conditions = t_count, members, conditions

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gid = str(interaction.guild.id)
        unreg = [m.display_name for m in self.members if get_user_data(gid, m.id).get('score', 0) == 0]
        if unreg: return await interaction.followup.send(f"❌ 점수 0점 (미등록) 유저: {', '.join(unreg)}", ephemeral=True)
        
        teams, err = divide_teams_with_conditions(self.members, self.t_count, gid, self.conditions)
        if err: return await interaction.followup.send(err, ephemeral=True)
        embed = build_horizontal_embed(teams, self.t_count, gid, "⚖️ 내전 밸런스 1차 편성")
        await interaction.message.edit(embed=embed, view=MoveConfirmView(teams, self.members, self.conditions, 1))

class TeamCountSelect(discord.ui.Select):
    def __init__(self, members, conditions):
        super().__init__(placeholder="팀 개수 선택...", options=[discord.SelectOption(label=f"{i}개 팀으로 나누기", value=str(i)) for i in range(2, 5)])
        self.members, self.conditions = members, conditions
    async def callback(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(TeamDivideButton(int(self.values[0]), self.members, self.conditions))
        await interaction.response.edit_message(content=f"👥 {self.values[0]}개 팀 선택됨.", view=view)

class ConditionSettingView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=None)
        self.members, self.conditions = members, {'duos': [], 'rivals': []}
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        self.s1 = discord.ui.Select(placeholder="유저 A...", options=options[:25], custom_id="cond_1")
        self.s2 = discord.ui.Select(placeholder="유저 B...", options=options[:25], custom_id="cond_2")
        async def dummy(interaction): await interaction.response.defer()
        self.s1.callback = self.s2.callback = dummy
        self.add_item(self.s1); self.add_item(self.s2)

    def get_status_text(self):
        txt = "👯 **[특수 조건]**\n"
        if self.conditions['duos']: txt += "🤝 듀오: " + ", ".join([f"<@{a}>+<@{b}>" for a,b in self.conditions['duos']]) + "\n"
        if self.conditions['rivals']: txt += "⚔️ 라이벌: " + ", ".join([f"<@{a}>vs<@{b}>" for a,b in self.conditions['rivals']]) + "\n"
        if not self.conditions['duos'] and not self.conditions['rivals']: txt += "조건 없음"
        return txt

    @discord.ui.button(label="🤝 듀오 추가", style=discord.ButtonStyle.success, row=2)
    async def add_duo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.s1.values or not self.s2.values or self.s1.values[0] == self.s2.values[0]: return await interaction.response.send_message("❌ 다른 유저 선택!", ephemeral=True)
        self.conditions['duos'].append((int(self.s1.values[0]), int(self.s2.values[0])))
        await interaction.response.edit_message(content=self.get_status_text(), view=self)

    @discord.ui.button(label="⚔️ 라이벌 추가", style=discord.ButtonStyle.danger, row=2)
    async def add_rival(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.s1.values or not self.s2.values or self.s1.values[0] == self.s2.values[0]: return await interaction.response.send_message("❌ 다른 유저 선택!", ephemeral=True)
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
        await interaction.response.edit_message(content="⚖️ 팀 개수 선택", view=view)

class ExcludeSelectView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=None)
        self.members = members
        self.select = discord.ui.Select(placeholder="제외할 유저 선택", min_values=1, max_values=min(len(members), 25), options=[discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members[:25]])
        async def cb(interaction): await interaction.response.defer()
        self.select.callback = cb
        self.add_item(self.select)

    @discord.ui.button(label="✅ 제외 적용", style=discord.ButtonStyle.primary, row=1)
    async def confirm(self, interaction, btn):
        fil = [m for m in self.members if str(m.id) not in self.select.values] if self.select.values else self.members
        if len(fil) < 2: return await interaction.response.send_message("❌ 인원 부족!", ephemeral=True)
        view = ConditionSettingView(fil)
        await interaction.response.edit_message(content=view.get_status_text(), view=view)

    @discord.ui.button(label="🚀 전원 포함 진행", style=discord.ButtonStyle.green, row=1)
    async def skip(self, interaction, btn):
        view = ConditionSettingView(self.members)
        await interaction.response.edit_message(content=view.get_status_text(), view=view)

@bot.command(name='내전시작')
async def start_civil_war(ctx):
    if not is_admin(ctx): return
    cfg = get_server_config(ctx.guild.id)
    if not cfg.get("lobby_id"): return await ctx.send("❌ 대기실 설정 필요")
    lobby = bot.get_channel(int(cfg['lobby_id']))
    mems = [m for m in lobby.members if not m.bot]
    if len(mems) < 2: return await ctx.send("❌ 대기실 인원 부족!")
    await ctx.send(f"📋 대기실 인원: {len(mems)}명", view=ExcludeSelectView(mems))

# 💡 [복구완료] 개발자 더미 유저 테스트 기능
class DummyUser:
    def __init__(self, uid, name):
        self.id, self.display_name, self.mention, self.voice = uid, name, f"<@{uid}>", True
    async def move_to(self, channel): pass

@bot.command(name='테스트시작')
async def test_civil_war(ctx):
    if not is_admin(ctx): return
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM user_stats WHERE guild_id=? AND score > 0", (str(ctx.guild.id),))
    rows = c.fetchall()
    conn.close()
    
    if len(rows) < 4: return await ctx.send("❌ DB에 점수가 등록된 유저가 최소 4명 이상이어야 합니다!")
    sample = random.sample(rows, min(8, len(rows)))
    dummy = [DummyUser(int(r['user_id']), r['nickname']) for r in sample]
    await ctx.send(f"🛠️ **[테스트 모드 가동]** {len(dummy)}명의 가상 유저 구성 완료.", view=ExcludeSelectView(dummy))

# 실행
token = os.environ.get('BOT_TOKEN')
if not token and os.path.exists('token.txt'):
    with open('token.txt', 'r', encoding='utf-8') as f: token = f.read().strip()
if token: bot.run(token)
else: print("❌ 토큰 오류")