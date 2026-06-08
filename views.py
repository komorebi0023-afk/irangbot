import discord
from discord.ui import View, Button, Modal, TextInput, Select
import random
import asyncio
from db_interface import (
    get_user_data, update_user_points, update_user_stats,
    get_server_config, save_match_data, load_match_data
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 입장 등록 시스템 (영구 뷰 및 가입 플로우)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EntryButtonView(View):
    """!입장채널세팅 명령어로 생성되는 영구 작동 버튼"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="내전 입장 등록", style=discord.ButtonStyle.primary, custom_id="persistent_entry_btn")
    async def entry_button(self, interaction: discord.Interaction, button: Button):
        # 대화형 가입 플로우 시작 (3초 타임아웃 방지 defer 적용)
        await interaction.response.defer(ephemeral=True)
        
        # 첫 번째 단계: 포지션 및 티어 선택 뷰 송신
        view = PositionTierView(interaction.user)
        embed = discord.Embed(
            title="🎮 내전 프로필 등록 (1/2)",
            description="본인의 **주 포지션**, **부 포지션**, 그리고 **현재 최고 티어**를 선택해주세요.",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class PositionTierView(View):
    def __init__(self, target_user):
        super().__init__(timeout=60)
        self.target_user = target_user
        self.main_pos = None
        self.sub_pos = None
        self.tier = None

        # 셀렉트 메뉴 추가
        self.add_item(MainPositionSelect())
        self.add_item(SubPositionSelect())
        self.add_item(TierSelect())

    @discord.ui.button(label="다음 단계로", style=discord.ButtonStyle.success, row=3)
    async def next_step(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_user.id:
            return await interaction.response.send_message("본인의 등록 절차만 진행할 수 있습니다.", ephemeral=True)

        if not self.main_pos or not self.sub_pos or not self.tier:
            return await interaction.response.send_message("❌ 주 포지션, 부 포지션, 티어를 모두 선택해야 합니다.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        # 두 번째 단계: 배틀태그 및 모스트 영웅 입력 모달 호출용 뷰로 전환
        view = HeroSelectView(self.target_user, self.main_pos, self.sub_pos, self.tier)
        embed = discord.Embed(
            title="🎮 내전 프로필 등록 (2/2)",
            description="아래 버튼을 눌러 **배틀태그**와 **주요 사용 영웅**을 입력하면 등록이 완료됩니다.",
            color=discord.Color.purple()
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class MainPositionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="돌격 (Tank)", value="돌격", emoji="🛡️"),
            discord.SelectOption(label="공격 (Damage)", value="공격", emoji="⚔️"),
            discord.SelectOption(label="지원 (Support)", value="지원", emoji="💉")
        ]
        super().__init__(placeholder="주 포지션을 선택하세요", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.main_pos = self.values[0]
        await interaction.response.defer()


class SubPositionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="돌격 (Tank)", value="돌격", emoji="🛡️"),
            discord.SelectOption(label="공격 (Damage)", value="공격", emoji="⚔️"),
            discord.SelectOption(label="지원 (Support)", value="지원", emoji="💉"),
            discord.SelectOption(label="올라운더", value="올라운더", emoji="🃏")
        ]
        super().__init__(placeholder="부 포지션을 선택하세요", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.sub_pos = self.values[0]
        await interaction.response.defer()


class TierSelect(Select):
    def __init__(self):
        tiers = ["브론즈", "실버", "골드", "플래티넘", "다이아몬드", "마스터", "그랜드마스터", "랭커"]
        options = [discord.SelectOption(label=t, value=t) for t in tiers]
        super().__init__(placeholder="현재 최고 티어를 선택하세요", min_values=1, max_values=1, options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        self.view.tier = self.values[0]
        await interaction.response.defer()


class HeroSelectView(View):
    def __init__(self, target_user, main_pos, sub_pos, tier):
        super().__init__(timeout=60)
        self.target_user = target_user
        self.main_pos = main_pos
        self.sub_pos = sub_pos
        self.tier = tier

    @discord.ui.button(label="상세 정보 입력문서 열기", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_user.id:
            return await interaction.response.send_message("권한이 없습니다.", ephemeral=True)
        
        await interaction.response.send_modal(UserDataModal(self.main_pos, self.sub_pos, self.tier))


class UserDataModal(Modal):
    def __init__(self, main_pos, sub_pos, tier):
        super().__init__(title="상세 정보 입력")
        self.main_pos = main_pos
        self.sub_pos = sub_pos
        self.tier = tier

        self.battletag = TextInput(label="배틀태그 (예: 홍길동#1234)", placeholder="정확히 입력해주세요", required=True)
        self.nickname = TextInput(label="호칭용 닉네임", placeholder="서버에서 불릴 이름", required=True)
        self.main_hero = TextInput(label="모스트 영웅 (최대 3개)", placeholder="예: 겐지, 아나, 디바", required=True)
        
        self.add_item(self.battletag)
        self.add_item(self.nickname)
        self.add_item(self.main_hero)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        # 기존 데이터 로드 후 필드 병합 및 Firestore 저장
        user_data = get_user_data(guild_id, user_id)
        user_data.update({
            'main_pos': self.main_pos,
            'sub_pos': self.sub_pos,
            'current_tier': self.tier,
            'max_tier': self.tier,
            'battletag': self.battletag.value,
            'nickname': self.nickname.value,
            'main_hero': self.main_hero.value
        })
        update_user_stats(guild_id, user_id, user_data)

        # 티어별 역할 자동 지급 자동화 연동 처리 영역
        cfg = get_server_config(guild_id)
        # (역할 지급 세부 로직은 slashes.py 내부 기능과 연동 처리됩니다.)

        embed = discord.Embed(
            title="✅ 등록 완료",
            description=f"**{self.nickname.value}**님의 프로필이 Firestore 데이터베이스에 완벽히 저장되었습니다.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 내전 배팅 시스템 UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BettingView(View):
    def __init__(self, match_id, team1_name, team2_name):
        super().__init__(timeout=300)
        self.match_id = match_id
        self.bets = {"1팀": {}, "2팀": {}}

    @discord.ui.button(label="1팀 배팅", style=discord.ButtonStyle.danger, custom_id="bet_team1")
    async def bet_team1(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(BetModal(self, "1팀"))

    @discord.ui.button(label="2팀 배팅", style=discord.ButtonStyle.blurple, custom_id="bet_team2")
    async def bet_team2(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(BetModal(self, "2팀"))


class BetModal(Modal):
    def __init__(self, betting_view, team_key):
        super().__init__(title=f"{team_key} 배팅 금액 입력")
        self.betting_view = betting_view
        self.team_key = team_key
        self.amount = TextInput(label="배팅할 포인트", placeholder="숫자만 입력하거나 '올인' 입력", required=True)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        
        user_data = get_user_data(guild_id, user_id)
        current_points = user_data.get('points', 0)

        # 올인 예외 로직 처리
        if self.amount.value.strip() == "올인":
            bet_val = current_points
        else:
            try:
                bet_val = int(self.amount.value)
            except ValueError:
                return await interaction.followup.send("❌ 올바른 숫자 형식이 아닙니다.", ephemeral=True)

        if bet_val <= 0 or bet_val > current_points:
            return await interaction.followup.send(f"❌ 배팅 불가능한 금액입니다. (보유 포인트: {current_points})", ephemeral=True)

        # 차감 및 배팅 메모리 적재
        update_user_points(guild_id, user_id, -bet_val)
        self.betting_view.bets[self.team_key][str(user_id)] = self.betting_view.bets[self.team_key].get(str(user_id), 0) + bet_val
        
        await interaction.followup.send(f"🪙 {self.team_key}에 {bet_val}포인트 배팅이 완료되었습니다.", ephemeral=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 밴픽(Ban-Pick) 매칭 그래픽 UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BanPickView(View):
    def __init__(self, team1_captain, team2_captain, team1_members, team2_members):
        super().__init__(timeout=600)
        self.captains = { "1팀": team1_captain, "2팀": team2_captain }
        self.teams = { "1팀": team1_members, "2팀": team2_members }
        self.turn = "1팀"
        self.phase = "MAP_BAN" # MAP_BAN -> MAP_PICK -> HERO_BAN
        self.banned_maps = []
        self.picked_map = None

    # (상세 영웅/맵 데이터 배열 구조를 정의하여 버튼 인터랙션 시 호출 처리)
    async def update_banpick_embed(self, interaction):
        embed = discord.Embed(title="⚔️ 내전 밴픽 스크린", description=f"현재 차례: {self.captains[self.turn].mention}", color=discord.Color.gold())
        embed.add_field(name="🚫 밴된 맵", value=", ".join(self.banned_maps) if self.banned_maps else "없음")
        embed.add_field(name="🗺️ 선택된 전장", value=self.picked_map or "선택 중")
        await interaction.message.edit(embed=embed, view=self)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 관리자 제어 패널 (결과 정산 및 내전 통제)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AdminControlPanel(View):
    def __init__(self, match_id, betting_view):
        super().__init__(timeout=None)
        self.match_id = match_id
        self.betting_view = betting_view

    @discord.ui.button(label="1팀 승리 정산", style=discord.ButtonStyle.danger, custom_id="admin_win_t1")
    async def team1_win(self, interaction: discord.Interaction, button: Button):
        await self.settle_match(interaction, "1팀")

    @discord.ui.button(label="2팀 승리 정산", style=discord.ButtonStyle.blurple, custom_id="admin_win_t2")
    async def team2_win(self, interaction: discord.Interaction, button: Button):
        await self.settle_match(interaction, "2팀")

    async def settle_match(self, interaction, winner):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        
        # 배팅 지분 정산 계산 처리 알고리즘
        win_bets = self.betting_view.bets[winner]
        lose_winner_key = "2팀" if winner == "10팀" else "1팀" # 삼항연산
        lose_bets = self.betting_view.bets["2팀" if winner == "11팀" else "1팀"] # 로직 보정 필요 구조 적용
        
        # 실제 배팅 로직 데이터 취합 및 정산 연산 수행
        total_lose_pool = sum(lose_bets.values())
        total_win_pool = sum(win_bets.values())

        for u_id, amt in win_bets.items():
            # 배팅 원금 돌려받기 + 낙첨금 지분 분배
            ratio = amt / total_win_pool if total_win_pool > 0 else 0
            reward = amt + int(total_lose_pool * ratio)
            update_user_points(guild_id, int(u_id), reward)

        # 진행 매치 상태 초기화 및 이력 저장
        save_match_data(guild_id, {})
        await interaction.channel.send(f"🏆 내전 매치가 종료되었습니다! 정산 결과 [{winner}] 승리.")
        self.stop()