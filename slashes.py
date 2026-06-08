import discord
from discord import app_commands
from discord.ext import commands
import random
import time
from db_interface import (
    get_user_data, update_user_points, update_user_stats,
    get_server_config, update_server_config, db, delete_user_stats
)
import views  # 앞서 만든 views.py 모듈 호출

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 권한 검증 헬퍼 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def check_admin(interaction: discord.Interaction) -> bool:
    """디스코드 관리자 권한이 있거나 지정된 봇 관리자 역할이 있는지 확인"""
    if interaction.user.guild_permissions.administrator:
        return True
    cfg = get_server_config(interaction.guild.id)
    admin_role_id = cfg.get('admin_role_id')
    if admin_role_id and any(role.id == int(admin_role_id) for role in interaction.user.roles):
        return True
    return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 메인 명령어 클래스 (Cog)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------
    # [관리자 전용] 시스템 및 세팅 명령어 (ephemeral=True)
    # ---------------------------------------------------------
    
    @app_commands.command(name="입장채널세팅", description="[관리자] 현재 채널에 내전 입장(가입) 영구 버튼을 생성합니다.")
    async def setup_entry_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 관리자 권한이 없습니다.", ephemeral=True)
        
        embed = discord.Embed(
            title="🎮 내전 프로필 등록", 
            description="아래 버튼을 눌러 본인의 포지션과 티어, 배틀태그를 등록해야 내전에 참여할 수 있습니다.", 
            color=discord.Color.green()
        )
        # 영구 뷰(EntryButtonView) 전송 - 버튼을 누르면 views.py의 로직이 실행됨
        await interaction.channel.send(embed=embed, view=views.EntryButtonView())
        await interaction.followup.send("✅ 이 채널에 입장 버튼 세팅이 완료되었습니다.", ephemeral=True)

    @app_commands.command(name="서버세팅", description="[관리자] 대기실 및 공지 채널을 설정합니다.")
    async def server_setup(self, interaction: discord.Interaction, 대기실채널: discord.VoiceChannel = None, 공지채널: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 관리자 권한이 없습니다.", ephemeral=True)
        
        if 대기실채널: update_server_config(interaction.guild.id, 'lobby_id', str(대기실채널.id))
        if 공지채널: update_server_config(interaction.guild.id, 'announce_id', str(공지채널.id))
            
        await interaction.followup.send("✅ 서버 채널 설정이 성공적으로 업데이트 되었습니다.", ephemeral=True)

    @app_commands.command(name="관리자역할설정", description="[서버장 전용] 봇 관리자 명령어를 사용할 디스코드 역할을 지정합니다.")
    async def set_admin_role(self, interaction: discord.Interaction, 역할: discord.Role):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ 디스코드 서버 관리자(서버장) 권한이 필요합니다.", ephemeral=True)
            
        update_server_config(interaction.guild.id, 'admin_role_id', str(역할.id))
        await interaction.followup.send(f"✅ 앞으로 {역할.mention} 역할을 가진 유저는 봇 관리자 기능을 사용할 수 있습니다.", ephemeral=True)

    @app_commands.command(name="포인트", description="[관리자] 특정 유저의 포인트를 지급, 차감 또는 설정합니다.")
    @app_commands.describe(유저="대상 유저", 작업="조작 방식 (지급/차감/설정)", 금액="포인트 양")
    @app_commands.choices(작업=[
        app_commands.Choice(name="지급 (+)", value="add"),
        app_commands.Choice(name="차감 (-)", value="sub"),
        app_commands.Choice(name="설정 (=)", value="set")
    ])
    async def manage_points(self, interaction: discord.Interaction, 유저: discord.Member, 작업: app_commands.Choice[str], 금액: int):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction): return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)
            
        guild_id, user_id = interaction.guild.id, 유저.id
        current_points = get_user_data(guild_id, user_id).get('points', 0)
        
        if 작업.value == "add":
            update_user_points(guild_id, user_id, 금액)
            msg = f"✅ {유저.mention}님에게 {금액}P를 지급했습니다. (현재 {current_points + 금액}P)"
        elif 작업.value == "sub":
            update_user_points(guild_id, user_id, -금액)
            msg = f"✅ {유저.mention}님의 {금액}P를 차감했습니다. (현재 {current_points - 금액}P)"
        elif 작업.value == "set":
            update_user_stats(guild_id, user_id, {'points': 금액})
            msg = f"✅ {유저.mention}님의 포인트를 {금액}P로 설정했습니다."
            
        await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="청소", description="[관리자] 현재 채널의 채팅을 일정 수량만큼 일괄 삭제합니다.")
    async def clear_messages(self, interaction: discord.Interaction, 수량: int):
        await interaction.response.defer(ephemeral=True)
        if not check_admin(interaction): return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)
            
        deleted = await interaction.channel.purge(limit=수량)
        await interaction.followup.send(f"✅ {len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)


    # ---------------------------------------------------------
    # [일반 유저] 공용 명령어 (ephemeral=False)
    # ---------------------------------------------------------

    @app_commands.command(name="정보", description="자신 또는 다른 유저의 프로필, 전적, 포인트를 확인합니다.")
    async def user_info(self, interaction: discord.Interaction, 대상: discord.Member = None):
        await interaction.response.defer(ephemeral=False)
        target = 대상 or interaction.user
        data = get_user_data(interaction.guild.id, target.id)
        
        embed = discord.Embed(title=f"📊 {data.get('nickname', target.display_name)}님의 정보", color=discord.Color.blue())
        embed.add_field(name="배틀태그", value=data.get('battletag', '-'), inline=True)
        embed.add_field(name="티어", value=f"현재: {data.get('current_tier', '-')} / 최고: {data.get('max_tier', '-')}", inline=True)
        embed.add_field(name="포지션", value=f"주: {data.get('main_pos', '-')} / 부: {data.get('sub_pos', '-')}", inline=True)
        embed.add_field(name="모스트 영웅", value=data.get('main_hero', '-'), inline=False)
        
        wins, losses = int(data.get('wins', 0)), int(data.get('losses', 0))
        winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        embed.add_field(name="전적", value=f"{wins}승 {losses}패 (승률 {winrate:.1f}%)", inline=True)
        embed.add_field(name="보유 포인트", value=f"{data.get('points', 0):,} P", inline=True)
        
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

    @app_commands.command(name="귀여워", description="🐾 귀여운 강아지 인스타그램 링크를 호출합니다.")
    async def cute_link(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send("🐾 https://www.instagram.com/i.rang0321/")

    # ---------------------------------------------------------
    # [핵심] 내전 매칭 및 게임 시작 로직
    # ---------------------------------------------------------

    @app_commands.command(name="내전시작", description="[관리자] 대기실 인원을 바탕으로 10인 내전 매칭, 밴픽, 배팅을 엽니다.")
    async def start_civil_war(self, interaction: discord.Interaction):
        # 복잡한 매칭 계산이 있으므로 전체 공개 defer 처리
        await interaction.response.defer(ephemeral=False)
        if not check_admin(interaction):
            return await interaction.followup.send("❌ 관리자 권한이 없습니다.", ephemeral=True)
            
        cfg = get_server_config(interaction.guild.id)
        lobby_id = cfg.get('lobby_id')
        if not lobby_id:
            return await interaction.followup.send("❌ `/서버세팅` 명령어로 대기실 음성 채널을 먼저 설정하세요.", ephemeral=True)
            
        lobby = interaction.guild.get_channel(int(lobby_id))
        if not lobby or not isinstance(lobby, discord.VoiceChannel):
            return await interaction.followup.send("❌ 유효한 대기실 음성 채널이 아닙니다.", ephemeral=True)
            
        members = [m for m in lobby.members if not m.bot]
        
        # 실제 환경에서는 len(members) < 10 으로 제한, 테스트를 위해 유동적 분배 가능
        if len(members) < 2:
            return await interaction.followup.send(f"❌ 인원이 너무 부족하여 내전을 시작할 수 없습니다. (현재 {len(members)}명)", ephemeral=True)
            
        # 팀 무작위 셔플 및 절반 분배 (기존의 상세 알고리즘 적용 지점)
        random.shuffle(members)
        mid = len(members) // 2
        t1_members, t2_members = members[:mid], members[mid:]
        
        # 주장 선출 (첫 번째 인원)
        t1_cap, t2_cap = t1_members[0], t2_members[0]
        
        # 1. 분배 결과 출력
        embed = discord.Embed(title="🔥 내전 매칭 완료!", description="팀 분배가 완료되었습니다. 밴픽 및 배팅을 시작합니다.", color=discord.Color.red())
        embed.add_field(name="🛡️ 1팀", value="\n".join([m.mention for m in t1_members]), inline=True)
        embed.add_field(name="⚔️ 2팀", value="\n".join([m.mention for m in t2_members]), inline=True)
        
        # 2. 밴픽 뷰 연결
        bp_view = views.BanPickView(t1_cap, t2_cap, t1_members, t2_members)
        await interaction.followup.send(embed=embed, view=bp_view)
        
        # 3. 배팅 시스템 연결
        match_id = f"{interaction.guild.id}_{int(time.time())}"
        bet_embed = discord.Embed(title="🪙 내전 승부 예측", description="승리할 것 같은 팀에 포인트를 배팅하세요!", color=discord.Color.gold())
        bet_view = views.BettingView(match_id, "1팀", "2팀")
        await interaction.channel.send(embed=bet_embed, view=bet_view)
        
        # 4. 관리자 정산 패널 연결 (비공개 처리 불가 사유: 일반 채널 버튼)
        admin_embed = discord.Embed(title="⚙️ 관리자 정산 패널", description="경기가 종료되면 승리한 팀을 눌러 전적과 배팅을 정산하세요.", color=discord.Color.dark_gray())
        await interaction.channel.send(embed=admin_embed, view=views.AdminControlPanel(match_id, bet_view))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Cog 초기화 함수 (main.py에서 호출)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def setup(bot):
    await bot.add_cog(GameCommands(bot))
    
    # 봇 기동 시 영구 뷰(Entry Button View)가 기존 메시지에 남아있을 경우를 위해 등록
    bot.add_view(views.EntryButtonView())