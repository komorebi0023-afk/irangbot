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

# --- 🗺️ 오버워치 전장 데이터 ---
OW_MAPS = {
    "호위": ["66번 국도", "감시기지: 지브롤터", "도라도", "리알토", "샴발리 수도원", "서킷 로얄", "쓰레기촌", "하바나"],
    "혼합": ["눔바니", "미드타운", "블리자드 월드", "아이헨발데", "왕의 길", "파라이수", "할리우드"],
    "쟁탈": ["남극 반도", "네팔", "리장 타워", "사모아", "부산", "오아시스", "일리오스"],
    "밀기": ["뉴 퀸 스트리트", "루나사피", "이스페란사", "콜로세오"],
    "플래시포인트": ["뉴 정크 시티", "수라바사", "아틀리스"]
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
    "왕의 길": "https://via.placeholder.com/800x450/2c2f33/ffffff.png?text=Kings+Row",
    "일리오스": "https://via.placeholder.com/800x450/2c2f33/ffffff.png?text=Ilios",
}

# --- 💾 데이터 관리 및 권한 확인 ---
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
    print('=========================')
    print(f'로그인 성공: {bot.user.name}')
    print('오버워치 내전 마스터 봇 (구글 시트 연동) 온라인!')
    print('=========================')


# --- 👑 구글 시트 동기화 (보안 패치 적용) ---
@bot.command(name='점수동기화')
async def sync_scores(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자만 사용할 수 있습니다.")
    if not os.path.exists('credentials.json'): return await ctx.send("❌ 서버에 `credentials.json` 열쇠 파일이 없습니다!")
    
    status_msg = await ctx.send("⏳ 구글 시트에서 최신 데이터를 불러오는 중입니다...")
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
        client = gspread.authorize(creds)
        
        # 보안: sheet_key.txt 파일이나 환경변수에서 키값을 가져옵니다.
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
        # 6번째 줄(index 5)부터 데이터 읽기 (B열: ID, K열: 점수 등)
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
                "main_hero": row[9] if len(row) > 9 and row[9] else "-"
            }
            
        save_data(SCORE_FILE, synced_data)
        await status_msg.edit(content=f"✅ 구글 시트 동기화 완료! 총 **{len(synced_data)}명**의 최신 프로필을 저장했습니다.")
    except Exception as e:
        await status_msg.edit(content=f"❌ 동기화 실패! 에러 발생:\n```{e}```")


# --- 📊 프로필 확인 및 이스터에그 ---
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

@bot.command(name='귀여워')
async def show_cute_instagram(ctx):
    await ctx.send("🐾 https://www.instagram.com/i.rang0321/")


# --- 🛠️ 일반 관리자 유틸 ---
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
    embed.add_field(name="`!점수동기화` (관리자)", value="구글 시트의 정보를 실시간으로 봇에 덮어씌웁니다.", inline=False)
    embed.add_field(name="`!점수` / `!점수 @유저`", value="유저의 상세 내전 프로필과 점수를 확인합니다.", inline=False)
    embed.add_field(name="`!내전시작` (관리자)", value="팀 자동 분배 및 음성 채널 배치를 진행합니다.", inline=False)
    embed.add_field(name="`!대기실복귀` (관리자)", value="팀 채널에 흩어진 유저들을 대기실로 불러옵니다.", inline=False)
    embed.add_field(name="`!대기실설정` / `!팀채널설정 [1~4]` (관리자)", value="내전용 음성 채널들을 지정합니다.", inline=False)
    embed.add_field(name="`!관리자추가 @유저` (관리자)", value="해당 유저에게 봇 제어 권한을 줍니다.", inline=False)
    embed.add_field(name="`!맵`", value="내전 전장 선택 및 룰렛을 돌립니다.", inline=False)
    embed.add_field(name="`!청소`", value="입력한 숫자만큼 위의 채팅을 깔끔하게 삭제합니다.", inline=False)
    embed.add_field(name="`!귀여워`", value="비밀 이스터에그 🐾", inline=False)
    await ctx.send(embed=embed)


# --- 🔊 채널 설정 및 이동 ---
@bot.command(name='대기실설정')
async def set_lobby(ctx):
    if not is_admin(ctx) or not ctx.author.voice: return await ctx.send("❌ 채널에 접속한 상태에서 사용하세요.")
    config = load_data(CONFIG_FILE)
    config['lobby_id'] = ctx.author.voice.channel.id
    save_data(CONFIG_FILE, config)
    await ctx.send(f'📢 **{ctx.author.voice.channel.name}** 채널 [대기실] 등록 완료.')

@bot.command(name='팀채널설정')
async def set_team_channel(ctx, team_num: int):
    if not is_admin(ctx) or not ctx.author.voice: return await ctx.send("❌ 채널에 접속한 상태에서 사용하세요.")
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
                    try:
                        await member.move_to(lobby_channel)
                        move_success += 1
                    except: move_fail += 1
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


# --- 👥 팀 교환 / 내전 팀 나누기 시스템 ---
class SwapView(discord.ui.View):
    def __init__(self, teams, team_channels, team_count, members):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.team_count, self.members = teams, team_channels, team_count, members
        options = [discord.SelectOption(label=p.display_name, value=str(p.id)) for t in teams for p in t]
        
        self.s1 = discord.ui.Select(placeholder="🔄 바꿀 첫 번째 유저...", options=options, custom_id="swap_1")
        self.s2 = discord.ui.Select(placeholder="🔄 바꿀 두 번째 유저...", options=options, custom_id="swap_2")
        
        async def dummy(interaction): await interaction.response.defer()
        self.s1.callback = self.s2.callback = dummy
        self.add_item(self.s1)
        self.add_item(self.s2)

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
            
        await interaction.response.edit_message(content="✅ 수동 교환이 완료되었습니다!", embed=embed, view=MoveConfirmView(self.teams, self.team_channels, self.team_count, self.members))

    @discord.ui.button(label="↩️ 취소 및 돌아가기", style=discord.ButtonStyle.gray, row=2)
    async def cancel_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        scores = load_data(SCORE_FILE)
        embed = discord.Embed(title="🎲 내전 팀 구성 결과", color=discord.Color.blue())
        team_colors = ["🔴 1팀", "🔵 2팀", "🟢 3팀", "🟡 4팀"]
        
        for i in range(self.team_count):
            t_score = sum(scores.get(str(p.id), {}).get("score", 0) for p in self.teams[i])
            avg = round(t_score / len(self.teams[i]), 1) if self.teams[i] else 0
            names = [p.display_name for p in self.teams[i]]
            embed.add_field(name=f"{team_colors[i]} (평균 {avg}점)", value=", ".join(names) if names else "없음", inline=False)

        await interaction.response.edit_message(content="✅ 교환을 취소했습니다.", embed=embed, view=MoveConfirmView(self.teams, self.team_channels, self.team_count, self.members))

class MoveConfirmView(discord.ui.View):
    def __init__(self, teams, team_channels, team_count, members):
        super().__init__(timeout=None)
        self.teams, self.team_channels, self.team_count, self.members = teams, team_channels, team_count, members

    @discord.ui.button(label="🚀 유저 자동 이동", style=discord.ButtonStyle.green)
    async def confirm_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content="⏳ 채널 이동 중...", view=self)
        
        move_success, move_fail = 0, 0
        for i, team in enumerate(self.teams):
            ch_id = self.team_channels.get(str(i + 1))
            if ch_id and bot.get_channel(int(ch_id)):
                for p in team:
                    if p.voice: 
                        try: 
                            await p.move_to(bot.get_channel(int(ch_id)))
                            move_success += 1
                        except: move_fail += 1
                    else: move_fail += 1
        
        status_text = f"✅ 팀 구성 및 이동 완료! (성공: {move_success}명)"
        if move_fail > 0: status_text += f"\n⚠️ 이동 실패: {move_fail}명 (채널을 나갔거나 권한 부족)"
        await interaction.message.edit(content=status_text)

    @discord.ui.button(label="🔄 랜덤 다시 짜기", style=discord.ButtonStyle.blurple)
    async def reroll_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        scores = load_data(SCORE_FILE)
        p_data = []
        for m in self.members:
            if str(m.id) in scores:
                actual = scores[str(m.id)].get("score", 0)
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
    async def manual_swap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🔄 유저 맞교환을 진행합니다.", view=SwapView(self.teams, self.team_channels, self.team_count, self.members))
        
    @discord.ui.button(label="❌ 이동 안 함", style=discord.ButtonStyle.gray)
    async def cancel_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content="✅ 채널 이동 없이 팀 구성만 마무리되었습니다.", view=self)


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

    async def callback(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(TeamDivideButton(int(self.values[0]), self.members))
        await interaction.response.edit_message(content=f"👥 {self.values[0]}개 팀 선택됨.", view=view)

@bot.command(name='내전시작')
async def start_civil_war(ctx):
    if not is_admin(ctx): return await ctx.send("❌ 관리자 권한이 없습니다.")
    cfg = load_data(CONFIG_FILE)
    if 'lobby_id' not in cfg: return await ctx.send("❌ 대기실 설정이 필요합니다. (`!대기실설정`)")
    
    lobby = bot.get_channel(int(cfg['lobby_id']))
    if not lobby: return await ctx.send("❌ 등록된 대기실 채널을 찾을 수 없습니다.")
    
    mems = [m for m in lobby.members if not m.bot]
    if not mems: return await ctx.send("❌ 대기실에 접속해 있는 유저가 없습니다!")
    
    view = discord.ui.View()
    view.add_item(TeamCountSelect(mems))
    await ctx.send(f"📋 대기실 {len(mems)}명", view=view)

# --- 🚀 봇 실행 (토큰 안전 처리) ---
token = os.environ.get('BOT_TOKEN')
if not token and os.path.exists('token.txt'):
    with open('token.txt', 'r', encoding='utf-8') as f:
        token = f.read().strip()
        
if token: 
    bot.run(token)
else: 
    print("❌ 토큰을 찾을 수 없습니다. 서버에 token.txt 파일이 제대로 있는지 확인해 주세요.")
