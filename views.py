import discord
import asyncio
import time
import db_interface
from db_interface import (
    get_user_data, update_user_stats, get_role_id,
    get_all_mapped_role_ids, db
)

OW_HEROES = {
    "돌격": ["D.Va", "둠피스트", "라마트라", "해저드", "도미나", "라인하르트", "레킹볼", "로드호그", "마우가", "시그마", "오리사", "자리야", "정커퀸", "윈스턴"],
    "공격": ["메이", "바스티온", "솔저: 76", "시메트라", "엠레", "정크랫", "토르비욘", "솜브라", "시에라", "에코", "파라", "프레야", "겐지", "리퍼", "벤데타", "벤처", "시온", "안란", "트레이서", "소전", "애쉬", "위도우메이커", "캐서디", "한조"],
    "지원": ["루시우", "바티스트", "아나", "제트팩 캣", "젠야타", "라이프위버", "메르시", "모이라", "키리코", "미즈키", "브리기테", "우양", "일리아리", "주노"]
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 역할 자동 동기화 (Firebase 버전)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_sync_user_roles(guild_id, member, db_data, is_first_entry=False):
    """포지션/티어에 맞는 역할 자동 부여 및 이전 역할 회수"""
    gid = str(guild_id)
    guild = member.guild

    # 1. 입장 시 1회성 처리
    if is_first_entry:
        entry_give_id = get_role_id(gid, "entry_give")
        entry_remove_id = get_role_id(gid, "entry_remove")

        if entry_remove_id:
            role_to_remove = guild.get_role(entry_remove_id)
            if role_to_remove and role_to_remove in member.roles:
                try:
                    await member.remove_roles(role_to_remove)
                except Exception:
                    pass

        if entry_give_id:
            role_to_give = guild.get_role(entry_give_id)
            if role_to_give:
                try:
                    await member.add_roles(role_to_give)
                except Exception:
                    pass

    # 2. 새로 부여할 포지션/티어 역할 ID 파악
    main_pos = db_data.get('main_pos', '-')
    sub_pos = db_data.get('sub_pos', '-')
    current_tier = db_data.get('current_tier', '-')

    new_role_ids = set()
    m_pos_id = get_role_id(gid, f"pos_{main_pos}")
    s_pos_id = get_role_id(gid, f"pos_{sub_pos}")
    tier_id = get_role_id(gid, f"tier_{current_tier}")

    if m_pos_id:
        new_role_ids.add(m_pos_id)
    if s_pos_id and s_pos_id != m_pos_id:
        new_role_ids.add(s_pos_id)
    if tier_id:
        new_role_ids.add(tier_id)

    # 3. 기존 pos_*/tier_* 역할 중 새 목록에 없는 것 제거
    all_mapped = get_all_mapped_role_ids(gid)
    member_role_ids = {r.id for r in member.roles}

    roles_to_remove = [
        guild.get_role(rid)
        for rid in all_mapped
        if rid in member_role_ids and rid not in new_role_ids
    ]
    roles_to_remove = [r for r in roles_to_remove if r is not None]

    if roles_to_remove:
        try:
            await member.remove_roles(*roles_to_remove)
        except Exception:
            pass

    # 4. 새 역할 부여
    for rid in new_role_ids:
        role = guild.get_role(rid)
        if role and role not in member.roles:
            try:
                await member.add_roles(role)
            except Exception:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 포지션 및 티어 선택 뷰
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PositionTierView(discord.ui.View):
    def __init__(self, default_data):
        super().__init__(timeout=120.0)
        self.is_done = False
        self.skipped = False
        self.result = {
            'main_pos': default_data.get('main_pos', '-'),
            'sub_pos': default_data.get('sub_pos', '-'),
            'max_tier': default_data.get('max_tier', '-'),
            'current_tier': default_data.get('current_tier', '-')
        }

        main_pos_select = discord.ui.Select(
            placeholder="⚔️ 주 포지션 선택",
            options=[
                discord.SelectOption(label="돌격", emoji="🛡️"),
                discord.SelectOption(label="공격", emoji="⚔️"),
                discord.SelectOption(label="지원", emoji="💉"),
                discord.SelectOption(label="올라운더", emoji="⭐")
            ],
            custom_id="main_pos", row=0
        )
        main_pos_select.callback = self.select_callback
        self.add_item(main_pos_select)

        sub_pos_select = discord.ui.Select(
            placeholder="🛡️ 부 포지션 선택",
            options=[
                discord.SelectOption(label="돌격", emoji="🛡️"),
                discord.SelectOption(label="공격", emoji="⚔️"),
                discord.SelectOption(label="지원", emoji="💉"),
                discord.SelectOption(label="올라운더", emoji="⭐"),
                discord.SelectOption(label="없음", emoji="❌")
            ],
            custom_id="sub_pos", row=1
        )
        sub_pos_select.callback = self.select_callback
        self.add_item(sub_pos_select)

        max_tier_select = discord.ui.Select(
            placeholder="🏆 최고 티어 선택",
            options=[
                discord.SelectOption(label=t) for t in
                ["언랭", "브론즈", "실버", "골드", "플래티넘", "다이아몬드", "마스터", "그랜드마스터", "챔피언"]
            ],
            custom_id="max_tier", row=2
        )
        max_tier_select.callback = self.select_callback
        self.add_item(max_tier_select)

        curr_tier_select = discord.ui.Select(
            placeholder="🏅 현재 티어 선택",
            options=[
                discord.SelectOption(label=t) for t in
                ["언랭", "브론즈", "실버", "골드", "플래티넘", "다이아몬드", "마스터", "그랜드마스터", "챔피언"]
            ],
            custom_id="current_tier", row=3
        )
        curr_tier_select.callback = self.select_callback
        self.add_item(curr_tier_select)

    async def select_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        self.result[custom_id] = interaction.data["values"][0]
        await interaction.response.defer()

    @discord.ui.button(label="🎮 오버워치 안 함 (입장만 하기)", style=discord.ButtonStyle.secondary, custom_id="btn_skip_ow", row=4)
    async def skip_ow_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = {
            'main_pos': '-', 'sub_pos': '-',
            'max_tier': '-', 'current_tier': '-',
            'main_hero': '-', 'battletag': '-'
        }
        self.is_done = True
        self.skipped = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="✅ 다음 단계로", style=discord.ButtonStyle.success, custom_id="btn_next_pt", row=4)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.result.get('main_pos', '-') == '-' or self.result.get('max_tier', '-') == '-':
            return await interaction.response.send_message(
                "⚠️ 주 포지션과 최고 티어는 반드시 선택해야 다음으로 넘어갈 수 있습니다!", ephemeral=True
            )
        self.is_done = True
        await interaction.response.defer()
        self.stop()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 영웅 다중 선택 뷰
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class HeroSelectView(discord.ui.View):
    def __init__(self, default_data):
        super().__init__(timeout=120.0)
        self.is_done = False
        self.selected_tanks = []
        self.selected_dps = []
        self.selected_sups = []

        tank_opts = [discord.SelectOption(label=h) for h in OW_HEROES["돌격"]]
        dps_opts = [discord.SelectOption(label=h) for h in OW_HEROES["공격"]]
        sup_opts = [discord.SelectOption(label=h) for h in OW_HEROES["지원"]]

        tank_sel = discord.ui.Select(placeholder="🛡️ 돌격 모스트 (다중 선택 가능)", max_values=len(tank_opts), options=tank_opts, custom_id="ht", row=0)
        dps_sel = discord.ui.Select(placeholder="⚔️ 공격 모스트 (다중 선택 가능)", max_values=len(dps_opts), options=dps_opts, custom_id="hd", row=1)
        sup_sel = discord.ui.Select(placeholder="💉 지원 모스트 (다중 선택 가능)", max_values=len(sup_opts), options=sup_opts, custom_id="hs", row=2)

        tank_sel.callback = self.select_callback
        dps_sel.callback = self.select_callback
        sup_sel.callback = self.select_callback

        self.add_item(tank_sel)
        self.add_item(dps_sel)
        self.add_item(sup_sel)

    async def select_callback(self, interaction: discord.Interaction):
        cid = interaction.data["custom_id"]
        if cid == "ht":
            self.selected_tanks = interaction.data["values"]
        elif cid == "hd":
            self.selected_dps = interaction.data["values"]
        elif cid == "hs":
            self.selected_sups = interaction.data["values"]
        await interaction.response.defer()

    @discord.ui.button(label="✅ 영웅 선택 완료", style=discord.ButtonStyle.success, row=3)
    async def done_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_done = True
        await interaction.response.defer()
        self.stop()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 공통 프로필 임베드 생성 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_profile_embed(member: discord.Member, db_data: dict, title_suffix: str = "프로필") -> discord.Embed:
    score_val = db_data.get('score', 0)
    display_score = "미정" if not score_val or float(score_val) == 0 else f"{float(score_val):g} 점"
    wins = int(db_data.get('wins', 0))
    losses = int(db_data.get('losses', 0))
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0.0

    embed = discord.Embed(
        title=f"📋 {member.display_name} {title_suffix}",
        color=discord.Color.green()
    )

    is_ow_player = db_data.get('main_pos', '-') != '-' or db_data.get('battletag', '-') != '-'

    if not is_ow_player:
        embed.description = "🎮 오버워치 미플레이 유저"
        embed.add_field(name="상태", value="일반 소통 유저로 등록되었습니다.", inline=False)
    else:
        embed.add_field(name="🎯 내전 점수", value=f"**{display_score}**", inline=True)
        embed.add_field(name="💰 포인트", value=f"**{db_data.get('points', 0):,} P**", inline=True)
        embed.add_field(name="배틀태그", value=db_data.get('battletag', '-'), inline=False)
        embed.add_field(name="티어 (최고 / 현재)", value=f"{db_data.get('max_tier', '-')} / {db_data.get('current_tier', '-')}", inline=True)
        embed.add_field(name="포지션 (주 / 부)", value=f"{db_data.get('main_pos', '-')} / {db_data.get('sub_pos', '-')}", inline=True)
        embed.add_field(name="주 영웅", value=db_data.get('main_hero', '-'), inline=False)
        embed.add_field(name="🏆 누적 전적", value=f"{wins}승 {losses}패 **(승률 {win_rate:.1f}%)**", inline=False)

    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 공통 셋업 플로우 (입장 & 정보수정 & 유저관리 공용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_setup_flow(
    interaction: discord.Interaction,
    target_member: discord.Member,
    mode: str,
    is_admin: bool,
    is_first_entry: bool = False
):
    """
    mode: "all" | "pos_tier" | "hero" | "battletag" | "score"
    is_first_entry: True이면 entry_give/remove 역할 처리 포함
    """
    guild_id = interaction.guild.id
    uid = target_member.id
    db_data = get_user_data(guild_id, uid)

    async def update_msg(content, view=None):
        """응답 상태에 따라 안전하게 메시지 수정"""
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(content, view=view, ephemeral=True)
            else:
                await interaction.edit_original_response(content=content, view=view)
        except Exception:
            try:
                await interaction.followup.send(content, view=view, ephemeral=True)
            except Exception:
                pass

    # ── 1단계: 포지션 & 티어 ──────────────────────────
    if mode in ["all", "pos_tier"]:
        view1 = PositionTierView(db_data)
        await update_msg(
            f"🔹 **[{target_member.display_name}]** 님, 포지션과 티어를 선택해주세요.\n"
            "*(오버워치를 하지 않으신다면 맨 아래 건너뛰기 버튼을 눌러주세요)*",
            view=view1
        )
        await view1.wait()

        if not view1.is_done:
            return await update_msg("⏳ 2분 초과로 자동 취소되었습니다. 다시 시도해주세요.", view=None)

        db_data.update(view1.result)

        # 건너뛰기(오버워치 미플레이) 처리
        if view1.skipped:
            db_data['nickname'] = target_member.display_name.split(' (')[0]
            update_user_stats(guild_id, uid, db_data)
            await auto_sync_user_roles(guild_id, target_member, db_data, is_first_entry=is_first_entry)
            await update_msg("🎉 오버워치 정보 없이 기본 입장이 완료되었습니다!", view=None)
            embed = build_profile_embed(target_member, db_data, "입장 완료" if is_first_entry else "프로필 업데이트")
            await interaction.channel.send(
                content=f"🎉 **{target_member.mention}** 님의 등록이 완료되었습니다!",
                embed=embed,
                view=EntryButtonView() if is_first_entry else None
            )
            # 데이터 등록 완료 웰컴 카드 메시지 (스킵도 등록 완료로 처리)
            if is_first_entry:
                try:
                    cards_snap = db_interface.db.collection('servers').document(str(guild_id)).collection('welcome_cards').stream()
                    for doc in cards_snap:
                        card = doc.to_dict()
                        if not card.get('enabled', True): continue
                        if card.get('type') != 'register': continue
                        msg = (card.get('message', '')
                            .replace('[user]',        target_member.mention)
                            .replace('[userName]',    target_member.display_name)
                            .replace('[memberCount]', str(interaction.guild.member_count))
                            .replace('[server]',      interaction.guild.name)
                            .replace('[inviter]',     '')
                            .replace('[inviterName]', '')
                            .replace('[invites]',     '')
                        )
                        channel_id = card.get('channel', '')
                        if not channel_id or not msg: continue
                        if channel_id == 'dm':
                            try: await target_member.send(msg)
                            except Exception: pass
                        else:
                            ch = interaction.guild.get_channel(int(channel_id))
                            if ch:
                                try: await ch.send(msg)
                                except Exception: pass
                except Exception as e:
                    print(f"❌ [등록 완료 메시지 오류] {e}")
            return

    # ── 2단계: 모스트 영웅 ───────────────────────────
    if mode in ["all", "hero"]:
        view2 = HeroSelectView(db_data)
        await update_msg("🔹 모스트 영웅을 선택해주세요. (각 포지션별 복수 선택 가능)", view=view2)
        await view2.wait()

        if not view2.is_done:
            return await update_msg("⏳ 2분 초과로 자동 취소되었습니다. 다시 시도해주세요.", view=None)

        selected = view2.selected_tanks + view2.selected_dps + view2.selected_sups
        db_data['main_hero'] = ", ".join(selected) if selected else "-"

    # ── 3단계: 배틀태그 채팅 입력 ────────────────────
    if mode in ["all", "battletag"]:
        await update_msg(
            "⌨️ 현재 채널 채팅창에 **배틀태그**를 입력해주세요.\n"
            "모르거나 건너뛰려면 `스킵` 입력",
            view=None
        )

        def check_msg(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await interaction.client.wait_for('message', check=check_msg, timeout=120.0)
            try:
                await msg.delete()
            except Exception:
                pass

            content = msg.content.strip()
            base_nick = target_member.display_name.split(' (')[0]
            db_data['nickname'] = base_nick

            if content == "스킵":
                db_data['battletag'] = db_data.get('battletag', '-')
            else:
                db_data['battletag'] = content
                ow_nick = content.split('#')[0] if '#' in content else content
                new_nick = f"{base_nick} ({ow_nick})"
                if len(new_nick) > 32:
                    new_nick = new_nick[:32]
                try:
                    await target_member.edit(nick=new_nick)
                except discord.errors.Forbidden:
                    pass

        except asyncio.TimeoutError:
            return await update_msg("⏳ 입력 시간이 초과되었습니다. 다시 시도해주세요.", view=None)

    # ── 4단계: 관리자 전용 점수 수정 ─────────────────
    if mode == "score" and is_admin:
        await update_msg(
            "⌨️ 현재 채널 채팅창에 해당 유저의 **내전 점수**를 숫자로 입력해주세요.\n"
            "*(채팅은 즉시 자동 삭제됩니다)*",
            view=None
        )

        def check_score(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await interaction.client.wait_for('message', check=check_score, timeout=60.0)
            try:
                await msg.delete()
            except Exception:
                pass

            content = msg.content.strip()
            try:
                db_data['score'] = float(content)
            except ValueError:
                return await update_msg("❌ 숫자로만 입력해야 합니다. 다시 시도해주세요.", view=None)

        except asyncio.TimeoutError:
            return await update_msg("⏳ 입력 시간이 초과되었습니다. 다시 시도해주세요.", view=None)

    # ── 최종: DB 저장 & 역할 동기화 & 프로필 출력 ────
    update_user_stats(guild_id, uid, db_data)
    await auto_sync_user_roles(guild_id, target_member, db_data, is_first_entry=is_first_entry)

    suffix = "입장 완료" if is_first_entry else "프로필 업데이트"
    await update_msg(f"🎉 **{target_member.display_name}** 님의 정보 처리가 완료되었습니다!", view=None)
    embed = build_profile_embed(target_member, db_data, suffix)
    await interaction.channel.send(
        content=f"✅ **{target_member.mention}** 님의 정보가 업데이트되었습니다!",
        embed=embed,
        view=EntryButtonView() if is_first_entry else None
    )

    # ── 데이터 등록 완료 웰컴 카드 메시지 전송 ────────
    if is_first_entry:
        try:
            cards_snap = db_interface.db.collection('servers').document(str(guild_id)).collection('welcome_cards').stream()
            for doc in cards_snap:
                card = doc.to_dict()
                if not card.get('enabled', True): continue
                if card.get('type') != 'register': continue
                msg_template = card.get('message', '')
                msg = (msg_template
                    .replace('[user]',        target_member.mention)
                    .replace('[userName]',    target_member.display_name)
                    .replace('[memberCount]', str(interaction.guild.member_count))
                    .replace('[server]',      interaction.guild.name)
                    .replace('[inviter]',     '')
                    .replace('[inviterName]', '')
                    .replace('[invites]',     '')
                )
                channel_id = card.get('channel', '')
                if not channel_id or not msg: continue
                if channel_id == 'dm':
                    try: await target_member.send(msg)
                    except Exception: pass
                else:
                    ch = interaction.guild.get_channel(int(channel_id))
                    if ch:
                        try: await ch.send(msg)
                        except Exception: pass
        except Exception as e:
            print(f"❌ [등록 완료 메시지 오류] {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 정보수정 / 유저관리 드롭다운 셀렉터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EditTargetSelect(discord.ui.Select):
    def __init__(self, target_member: discord.Member, is_admin: bool):
        self.target_member = target_member
        self.is_admin = is_admin
        opts = [
            discord.SelectOption(label="전체 새로 입력", description="모든 정보를 백지부터 다시 기입합니다.", value="all"),
            discord.SelectOption(label="포지션 및 티어 수정", value="pos_tier"),
            discord.SelectOption(label="모스트 영웅 수정", value="hero"),
            discord.SelectOption(label="배틀태그 수정", value="battletag"),
        ]
        if is_admin:
            opts.append(discord.SelectOption(label="내전 점수 수정", description="관리자 전용", value="score"))

        super().__init__(
            placeholder="수정할 항목을 선택해주세요...",
            min_values=1, max_values=1,
            options=opts
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🔄 선택하신 항목의 수정을 시작합니다...", view=None)
        await run_setup_flow(interaction, self.target_member, self.values[0], self.is_admin)


class EditUserView(discord.ui.View):
    def __init__(self, target_member: discord.Member, is_admin: bool):
        super().__init__(timeout=120.0)
        self.add_item(EditTargetSelect(target_member, is_admin))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. 영구 입장 버튼 (EntryButtonView)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EntryButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="서버 프로필 등록", style=discord.ButtonStyle.primary, custom_id="persistent_entry_btn")
    async def entry_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.guild.id, interaction.user.id)

        # 이미 입장 완료한 유저 차단
        already_registered = (
            data.get('main_pos', '-') != '-' or
            data.get('battletag', '-') != '-'
        )
        if already_registered:
            return await interaction.response.send_message(
                "❌ 이미 입장 등록이 완료된 유저입니다.\n"
                "정보 수정을 원하시면 `/정보수정` 명령어를 이용해주세요.",
                ephemeral=True
            )

        await run_setup_flow(
            interaction,
            interaction.user,
            mode="all",
            is_admin=False,
            is_first_entry=True
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. 내전 시작 (밴픽, 배팅, 정산) 뷰
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BanPickView(discord.ui.View):
    def __init__(self, t1_cap, t2_cap, t1_members, t2_members):
        super().__init__(timeout=None)
        self.t1_cap = t1_cap
        self.t2_cap = t2_cap
        self.t1_members = t1_members
        self.t2_members = t2_members

    @discord.ui.button(label="밴픽 완료 / 배팅 시작", style=discord.ButtonStyle.green)
    async def finish_bp(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (interaction.user not in [self.t1_cap, self.t2_cap]
                and not interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message(
                "❌ 주장이나 관리자만 누를 수 있습니다.", ephemeral=True
            )
        self.stop()
        await interaction.response.edit_message(content="✅ 밴픽이 완료되었습니다. 배팅을 시작합니다!", view=None)


class BettingView(discord.ui.View):
    def __init__(self, match_id, t1_name, t2_name):
        super().__init__(timeout=None)
        self.match_id = match_id
        self.t1_name = t1_name
        self.t2_name = t2_name

    @discord.ui.button(label="1팀 승리 예측", style=discord.ButtonStyle.blurple, custom_id="bet_t1")
    async def bet_t1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_bet(interaction, "t1")

    @discord.ui.button(label="2팀 승리 예측", style=discord.ButtonStyle.red, custom_id="bet_t2")
    async def bet_t2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_bet(interaction, "t2")

    async def process_bet(self, interaction: discord.Interaction, team: str):
        await interaction.response.send_modal(BetModal(self.match_id, team))


class BetModal(discord.ui.Modal, title="포인트 배팅"):
    bet_amount = discord.ui.TextInput(label="배팅할 포인트", placeholder="예: 100", required=True)

    def __init__(self, match_id, team):
        super().__init__()
        self.match_id = match_id
        self.team = team

    async def on_submit(self, interaction: discord.Interaction):
        amount_str = self.bet_amount.value
        if not amount_str.isdigit() or int(amount_str) <= 0:
            return await interaction.response.send_message("❌ 올바른 숫자를 입력하세요.", ephemeral=True)
        amount = int(amount_str)

        user_data = db_interface.get_user_data(interaction.guild.id, interaction.user.id)
        pts = user_data.get('points', 0)
        if pts < amount:
            return await interaction.response.send_message(
                f"❌ 포인트가 부족합니다. (보유: {pts}P)", ephemeral=True
            )

        db_interface.update_user_points(interaction.guild.id, interaction.user.id, -amount)

        match_ref = db_interface.db.collection('servers').document(
            str(interaction.guild.id)
        ).collection('active_match').document('main')

        doc = match_ref.get()
        if doc.exists:
            match_data = doc.to_dict()
            bets = match_data.get('bets', {})
            if self.team not in bets:
                bets[self.team] = {}
            uid_str = str(interaction.user.id)
            bets[self.team][uid_str] = bets[self.team].get(uid_str, 0) + amount
            match_ref.update({'bets': bets})

        await interaction.response.send_message(
            f"✅ {self.team}에 {amount}P 배팅 완료!", ephemeral=True
        )


class AdminControlPanel(discord.ui.View):
    def __init__(self, match_id, bet_view: BettingView, t1_members=None, t2_members=None):
        super().__init__(timeout=None)
        self.match_id = match_id
        self.bet_view = bet_view
        self.t1_members = t1_members or []
        self.t2_members = t2_members or []

    @discord.ui.button(label="🏆 1팀 승리 정산", style=discord.ButtonStyle.success)
    async def win_t1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve_match(interaction, "t1", self.t1_members, self.t2_members)

    @discord.ui.button(label="🏆 2팀 승리 정산", style=discord.ButtonStyle.success)
    async def win_t2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve_match(interaction, "t2", self.t2_members, self.t1_members)

    async def resolve_match(
        self,
        interaction: discord.Interaction,
        winner: str,
        winner_members: list,
        loser_members: list
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자만 누를 수 있습니다.", ephemeral=True)

        match_ref = db_interface.db.collection('servers').document(
            str(interaction.guild.id)
        ).collection('active_match').document('main')

        doc = match_ref.get()
        if not doc.exists:
            return await interaction.response.send_message("❌ 배팅 데이터를 찾을 수 없습니다.", ephemeral=True)

        match_data = doc.to_dict()
        bets = match_data.get('bets', {})
        winner_bets = bets.get(winner, {})

        # 배팅 정산 (승리팀 2배 지급)
        payouts = 0
        for uid, amt in winner_bets.items():
            db_interface.update_user_points(interaction.guild.id, int(uid), amt * 2)
            payouts += 1

        # 전적 업데이트
        guild_id = interaction.guild.id
        for m in winner_members:
            data = db_interface.get_user_data(guild_id, m.id)
            data['wins'] = int(data.get('wins', 0)) + 1
            db_interface.update_user_stats(guild_id, m.id, data)

        for m in loser_members:
            data = db_interface.get_user_data(guild_id, m.id)
            data['losses'] = int(data.get('losses', 0)) + 1
            db_interface.update_user_stats(guild_id, m.id, data)

        match_ref.delete()
        self.stop()
        self.bet_view.stop()

        await interaction.response.edit_message(
            content=f"🎉 정산 완료! 승리 팀 배팅자 {payouts}명에게 2배 지급, 전적이 업데이트되었습니다.",
            view=None
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. 임시채널 제어 패널
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TempChannelRenameModal(discord.ui.Modal, title="채널 이름 변경"):
    new_name = discord.ui.TextInput(
        label="새 채널 이름",
        placeholder="예: 즐거운 내전방",
        max_length=100,
        required=True
    )

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.channel.edit(name=self.new_name.value)
            await interaction.response.send_message(
                f"✅ 채널 이름이 **{self.new_name.value}**으로 변경되었습니다.", ephemeral=True
            )
        except discord.errors.Forbidden:
            await interaction.response.send_message("❌ 채널 이름을 변경할 권한이 없습니다.", ephemeral=True)


class TempChannelLimitModal(discord.ui.Modal, title="최대 인원 변경"):
    new_limit = discord.ui.TextInput(
        label="최대 인원 (0 = 무제한)",
        placeholder="예: 5",
        max_length=2,
        required=True
    )

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        if not self.new_limit.value.isdigit():
            return await interaction.response.send_message("❌ 숫자만 입력해주세요.", ephemeral=True)
        limit = int(self.new_limit.value)
        try:
            await self.channel.edit(user_limit=limit)
            msg = "무제한" if limit == 0 else f"{limit}명"
            await interaction.response.send_message(
                f"✅ 최대 인원이 **{msg}**으로 변경되었습니다.", ephemeral=True
            )
        except discord.errors.Forbidden:
            await interaction.response.send_message("❌ 인원을 변경할 권한이 없습니다.", ephemeral=True)


class TempChannelTransferSelect(discord.ui.Select):
    def __init__(self, channel, current_owner_id):
        self.channel          = channel
        self.current_owner_id = current_owner_id

        members = [m for m in channel.members if not m.bot and m.id != current_owner_id]
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in members[:25]
        ] if members else [
            discord.SelectOption(label="채널에 다른 유저가 없습니다.", value="none")
        ]

        super().__init__(
            placeholder="방장을 넘길 유저를 선택하세요",
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ 채널에 다른 유저가 없습니다.", ephemeral=True)

        new_owner_id = int(self.values[0])
        new_owner    = interaction.guild.get_member(new_owner_id)
        if not new_owner:
            return await interaction.response.send_message("❌ 유저를 찾을 수 없습니다.", ephemeral=True)

        db_interface.update_temp_channel_owner(
            str(interaction.guild.id), str(self.channel.id), str(new_owner_id)
        )
        await update_temp_channel_panel(self.channel, new_owner)
        await interaction.response.send_message(
            f"✅ **{new_owner.display_name}** 님에게 방장이 넘어갔습니다.", ephemeral=True
        )


class TempChannelTransferView(discord.ui.View):
    def __init__(self, channel, current_owner_id):
        super().__init__(timeout=60)
        self.add_item(TempChannelTransferSelect(channel, current_owner_id))


class TempChannelControlView(discord.ui.View):
    def __init__(self, channel_id, owner_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.owner_id   = owner_id

    def _check_owner(self, interaction: discord.Interaction) -> bool:
        tc = db_interface.get_temp_channel(str(interaction.guild.id), str(self.channel_id))
        if not tc:
            return False
        return str(interaction.user.id) == str(tc.get('owner_id'))

    @discord.ui.button(label="이름 변경", style=discord.ButtonStyle.primary, custom_id="tc_rename", row=0)
    async def rename_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_owner(interaction):
            return await interaction.response.send_message("❌ 방장만 변경할 수 있습니다.", ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return await interaction.response.send_message("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
        await interaction.response.send_modal(TempChannelRenameModal(channel))

    @discord.ui.button(label="인원 변경", style=discord.ButtonStyle.secondary, custom_id="tc_limit", row=0)
    async def limit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_owner(interaction):
            return await interaction.response.send_message("❌ 방장만 변경할 수 있습니다.", ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return await interaction.response.send_message("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
        await interaction.response.send_modal(TempChannelLimitModal(channel))

    @discord.ui.button(label="방장 넘기기", style=discord.ButtonStyle.secondary, custom_id="tc_transfer", row=0)
    async def transfer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_owner(interaction):
            return await interaction.response.send_message("❌ 방장만 넘길 수 있습니다.", ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            return await interaction.response.send_message("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
        view = TempChannelTransferView(channel, interaction.user.id)
        await interaction.response.send_message(view=view, ephemeral=True)


async def send_temp_channel_panel(channel: discord.VoiceChannel, owner: discord.Member):
    """임시채널 생성 시 제어 패널 임베드 전송"""
    embed = discord.Embed(
        title="🔊 음성채널 제어 패널",
        description=f"현재 방장: {owner.mention}",
        color=discord.Color.blue()
    )
    embed.add_field(name="이름 변경", value="채널 이름을 수정합니다.", inline=True)
    embed.add_field(name="인원 변경", value="최대 인원을 설정합니다.", inline=True)
    embed.add_field(name="방장 넘기기", value="다른 유저에게 방장을 넘깁니다.", inline=True)
    embed.set_footer(text="방장만 제어 패널을 사용할 수 있습니다.")

    view = TempChannelControlView(channel.id, owner.id)
    await channel.send(content=owner.mention, embed=embed, view=view)


async def update_temp_channel_panel(channel: discord.VoiceChannel, new_owner: discord.Member):
    """방장 변경 시 제어 패널 업데이트"""
    embed = discord.Embed(
        title="🔊 음성채널 제어 패널",
        description=f"현재 방장: {new_owner.mention}",
        color=discord.Color.blue()
    )
    embed.add_field(name="이름 변경", value="채널 이름을 수정합니다.", inline=True)
    embed.add_field(name="인원 변경", value="최대 인원을 설정합니다.", inline=True)
    embed.add_field(name="방장 넘기기", value="다른 유저에게 방장을 넘깁니다.", inline=True)
    embed.set_footer(text="방장만 제어 패널을 사용할 수 있습니다.")

    view = TempChannelControlView(channel.id, new_owner.id)
    try:
        async for message in channel.history(limit=20):
            if message.author.bot and message.embeds and "음성채널 제어 패널" in message.embeds[0].title:
                await message.edit(content=new_owner.mention, embed=embed, view=view)
                return
    except Exception:
        pass
    await channel.send(content=new_owner.mention, embed=embed, view=view)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. 내전 시스템 (제외선택 → 조건 → 팀분배 → 배팅 → 정산)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import itertools
from datetime import datetime, timezone, timedelta

# ── 팀 밸런싱 헬퍼 함수 ───────────────────────────────────

def balance_teams(scored, duo_pairs, rival_pairs, used_arrangements=None):
    """
    듀오/라이벌 조건 우선 + 점수 균등 분배 (브루트포스)
    used_arrangements: 이미 사용된 배치 목록 (재분배 시 제외)
    """
    members = [m for m, _ in scored]
    score_map = {m.id: s for m, s in scored}
    n = len(members)
    half = n // 2

    if used_arrangements is None:
        used_arrangements = []

    # 모든 조합 시도 (최대 20명까지 현실적)
    best = None
    best_diff = float('inf')
    best_key = None

    combos = list(itertools.combinations(range(n), half))

    for combo in combos:
        t1 = [members[i] for i in combo]
        t2 = [members[i] for i in range(n) if i not in combo]

        t1_ids = frozenset(m.id for m in t1)
        t2_ids = frozenset(m.id for m in t2)
        arr_key = (t1_ids, t2_ids)

        # 이미 사용된 배치 제외
        if arr_key in used_arrangements:
            continue

        # 듀오 조건 검사 (같은 팀이어야 함)
        valid = True
        for pair in duo_pairs:
            ids = list(pair)
            a, b = ids[0], ids[1]
            in_t1 = (a in t1_ids) and (b in t1_ids)
            in_t2 = (a in t2_ids) and (b in t2_ids)
            if not (in_t1 or in_t2):
                valid = False
                break

        if not valid:
            continue

        # 라이벌 조건 검사 (다른 팀이어야 함)
        for pair in rival_pairs:
            ids = list(pair)
            a, b = ids[0], ids[1]
            if (a in t1_ids and b in t1_ids) or (a in t2_ids and b in t2_ids):
                valid = False
                break

        if not valid:
            continue

        # 점수 차이 계산
        t1_score = sum(score_map.get(m.id, 0) for m in t1)
        t2_score = sum(score_map.get(m.id, 0) for m in t2)
        diff = abs(t1_score - t2_score)

        if diff < best_diff:
            best_diff = diff
            best = (t1, t2)
            best_key = arr_key

    if best is None:
        # 조건 만족 불가 시 그리디로 대체
        sorted_scored = sorted(scored, key=lambda x: x[1], reverse=True)
        t1_data, t2_data = [], []
        t1s = t2s = 0.0
        for m, s in sorted_scored:
            if t1s <= t2s:
                t1_data.append(m); t1s += s
            else:
                t2_data.append(m); t2s += s
        return t1_data, t2_data

    return best


def build_lineup_embed(t1_members, t2_members, scored):
    """대진표 임베드 생성"""
    score_map = {m.id: s for m, s in scored}
    t1_score = sum(score_map.get(m.id, 0) for m in t1_members)
    t2_score = sum(score_map.get(m.id, 0) for m in t2_members)

    embed = discord.Embed(
        title="🔥 내전 대진표",
        description=f"🛡️ 1팀 합산: **{t1_score:g}점** | ⚔️ 2팀 합산: **{t2_score:g}점**\n점수 차이: **{abs(t1_score - t2_score):g}점**",
        color=discord.Color.red()
    )
    t1_text = "\n".join([f"• {m.display_name} ({score_map.get(m.id, 0):g}점)" for m in t1_members]) or "-"
    t2_text = "\n".join([f"• {m.display_name} ({score_map.get(m.id, 0):g}점)" for m in t2_members]) or "-"
    embed.add_field(name="🛡️ 1팀", value=t1_text, inline=True)
    embed.add_field(name="⚔️ 2팀", value=t2_text, inline=True)
    return embed


# ── 1단계: 제외 플레이어 선택 ─────────────────────────────

class ExcludePlayerView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=120)
        self.members     = members
        self.excluded_ids = set()
        self.confirmed   = False

        if members:
            opts = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members[:25]]
            sel  = discord.ui.Select(
                placeholder="제외할 플레이어 선택 (복수 선택 가능)",
                min_values=0, max_values=len(opts),
                options=opts
            )
            sel.callback = self._on_select
            self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        self.excluded_ids = set(int(v) for v in interaction.data['values'])
        await interaction.response.defer()

    @discord.ui.button(label="✅ 확인 (선택한 플레이어 제외)", style=discord.ButtonStyle.success, row=1)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        excluded_names = [m.display_name for m in self.members if m.id in self.excluded_ids]
        msg = f"✅ 제외된 플레이어: **{', '.join(excluded_names)}**" if excluded_names else "✅ 제외된 플레이어 없음"
        await interaction.response.edit_message(content=msg, view=None)
        self.stop()

    @discord.ui.button(label="⏭️ 전원 참여 (건너뛰기)", style=discord.ButtonStyle.secondary, row=1)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.excluded_ids = set()
        self.confirmed    = True
        await interaction.response.edit_message(content="✅ 전원 참여로 진행합니다.", view=None)
        self.stop()

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.danger, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        await interaction.response.edit_message(content="❌ 내전 시작이 취소되었습니다.", view=None)
        self.stop()


# ── 2단계: 듀오/라이벌 조건 설정 ─────────────────────────

class ConditionSetupView(discord.ui.View):
    def __init__(self, members):
        super().__init__(timeout=180)
        self.members     = members
        self.duo_pairs   = []   # [(member_a_id, member_b_id), ...]
        self.rival_pairs = []
        self.confirmed   = False
        self._pending_type = None  # 'duo' or 'rival'
        self._pending_a    = None

    def _get_member(self, uid):
        return next((m for m in self.members if m.id == uid), None)

    def _make_select(self, placeholder, row):
        opts = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in self.members[:25]]
        sel  = discord.ui.Select(placeholder=placeholder, min_values=1, max_values=1, options=opts, row=row)
        return sel

    @discord.ui.button(label="💑 듀오 추가", style=discord.ButtonStyle.primary, row=0)
    async def add_duo(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = _PairSelectView(self.members, "duo")
        await interaction.response.send_message("듀오 조건: 같은 팀으로 묶을 두 플레이어를 선택하세요.", view=view, ephemeral=True)
        await view.wait()
        if view.pair:
            self.duo_pairs.append(view.pair)
            a = self._get_member(view.pair[0])
            b = self._get_member(view.pair[1])
            await interaction.edit_original_response(
                content=self._status_text() + f"\n✅ 듀오 추가: **{a.display_name}** & **{b.display_name}**"
            )

    @discord.ui.button(label="⚔️ 라이벌 추가", style=discord.ButtonStyle.danger, row=0)
    async def add_rival(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = _PairSelectView(self.members, "rival")
        await interaction.response.send_message("라이벌 조건: 다른 팀으로 나눌 두 플레이어를 선택하세요.", view=view, ephemeral=True)
        await view.wait()
        if view.pair:
            self.rival_pairs.append(view.pair)
            a = self._get_member(view.pair[0])
            b = self._get_member(view.pair[1])
            await interaction.edit_original_response(
                content=self._status_text() + f"\n✅ 라이벌 추가: **{a.display_name}** vs **{b.display_name}**"
            )

    @discord.ui.button(label="✅ 조건 확정", style=discord.ButtonStyle.success, row=1)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # member id → member 객체로 변환
        self.duo_pairs   = [(self._get_member(a), self._get_member(b)) for a, b in self.duo_pairs if self._get_member(a) and self._get_member(b)]
        self.rival_pairs = [(self._get_member(a), self._get_member(b)) for a, b in self.rival_pairs if self._get_member(a) and self._get_member(b)]
        # id set으로 변환 (balance_teams에서 사용)
        self.duo_pairs   = [(frozenset([a.id, b.id])) for a, b in self.duo_pairs]
        self.rival_pairs = [(frozenset([a.id, b.id])) for a, b in self.rival_pairs]
        self.confirmed   = True
        await interaction.response.edit_message(content=f"✅ 조건 확정!\n{self._status_text()}", view=None)
        self.stop()

    @discord.ui.button(label="⏭️ 건너뛰기", style=discord.ButtonStyle.secondary, row=1)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.duo_pairs   = []
        self.rival_pairs = []
        self.confirmed   = True
        await interaction.response.edit_message(content="✅ 조건 없이 진행합니다.", view=None)
        self.stop()

    def _status_text(self):
        lines = []
        for pair in self.duo_pairs:
            ids = list(pair)
            a = self._get_member(ids[0])
            b = self._get_member(ids[1])
            if a and b:
                lines.append(f"💑 듀오: {a.display_name} & {b.display_name}")
        for pair in self.rival_pairs:
            ids = list(pair)
            a = self._get_member(ids[0])
            b = self._get_member(ids[1])
            if a and b:
                lines.append(f"⚔️ 라이벌: {a.display_name} vs {b.display_name}")
        return "\n".join(lines) if lines else "현재 설정된 조건 없음"


class _PairSelectView(discord.ui.View):
    """듀오/라이벌 두 명 선택 뷰"""
    def __init__(self, members, pair_type):
        super().__init__(timeout=60)
        self.members   = members
        self.pair_type = pair_type
        self.pair      = None
        self.sel_a     = None
        self.sel_b     = None

        opts = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members[:25]]

        sel_a = discord.ui.Select(placeholder="첫 번째 플레이어", min_values=1, max_values=1, options=opts, row=0)
        sel_b = discord.ui.Select(placeholder="두 번째 플레이어", min_values=1, max_values=1, options=opts, row=1)

        async def on_a(interaction):
            self.sel_a = int(interaction.data['values'][0])
            await interaction.response.defer()

        async def on_b(interaction):
            self.sel_b = int(interaction.data['values'][0])
            await interaction.response.defer()

        sel_a.callback = on_a
        sel_b.callback = on_b
        self.add_item(sel_a)
        self.add_item(sel_b)

    @discord.ui.button(label="✅ 추가", style=discord.ButtonStyle.success, row=2)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.sel_a or not self.sel_b or self.sel_a == self.sel_b:
            return await interaction.response.send_message("❌ 서로 다른 두 명을 선택해주세요.", ephemeral=True)
        self.pair = (self.sel_a, self.sel_b)
        await interaction.response.edit_message(content="✅ 추가됐습니다.", view=None)
        self.stop()


# ── 3단계: 대진표 확정 뷰 ─────────────────────────────────

class LineupConfirmView(discord.ui.View):
    def __init__(self, t1_members, t2_members, match_ctx, admin_ch, announce_ch, announce_msg):
        super().__init__(timeout=300)
        self.t1          = list(t1_members)
        self.t2          = list(t2_members)
        self.match_ctx   = match_ctx
        self.admin_ch    = admin_ch
        self.announce_ch = announce_ch
        self.announce_msg = announce_msg

    @discord.ui.button(label="✅ 대진표 확정", style=discord.ButtonStyle.success, row=0)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            cfg = db_interface.get_server_config(str(interaction.guild.id))
            admin_role_id = cfg.get('admin_role_id')
            if not admin_role_id or not any(r.id == int(admin_role_id) for r in interaction.user.roles):
                return await interaction.response.send_message("❌ 관리자만 확정할 수 있습니다.", ephemeral=True)

        # 공지채널 대진표 업데이트
        scored     = self.match_ctx['scored']
        lineup_embed = build_lineup_embed(self.t1, self.t2, scored)
        if self.announce_msg:
            try:
                await self.announce_msg.edit(content="📋 **내전 대진표 (확정)**", embed=lineup_embed)
            except Exception:
                pass

        await interaction.response.edit_message(content="✅ 대진표가 확정되었습니다! 배팅을 시작합니다.", view=None)
        self.stop()

        # 배팅 시스템 시작
        guild_id  = self.match_ctx['guild_id']
        cfg       = self.match_ctx['cfg']
        match_id  = f"{guild_id}_{int(time.time())}"
        t1_ids    = [str(m.id) for m in self.t1]
        t2_ids    = [str(m.id) for m in self.t2]

        db_interface.db.collection('servers').document(guild_id).collection('active_match').document('main').set({
            'match_id':   match_id,
            'bets':       {'t1': {}, 't2': {}},
            't1_members': t1_ids,
            't2_members': t2_ids,
            'bet_open':   True,
            'bet_close_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        })

        # 배팅 뷰 생성 (공지 채널에 전송)
        bet_view  = MatchBettingView(match_id, self.t1, self.t2, guild_id)
        bet_embed = bet_view.build_embed()
        bet_ch    = self.announce_ch or interaction.channel

        bet_msg = await bet_ch.send(
            content="🪙 **승부 예측 배팅이 시작되었습니다! (5분간)**",
            embed=bet_embed,
            view=bet_view
        )
        bet_view.bet_msg = bet_msg

        # 관리자 패널 (명령어 친 채널에)
        admin_panel = AdminMatchPanel(match_id, self.t1, self.t2, bet_view, cfg, guild_id)
        admin_embed_obj = discord.Embed(
            title="⚙️ 관리자 패널",
            description=f"**1팀:** {', '.join([m.display_name for m in self.t1])}\n**2팀:** {', '.join([m.display_name for m in self.t2])}",
            color=discord.Color.dark_gray()
        )
        await self.admin_ch.send(embed=admin_embed_obj, view=admin_panel)

        # 5분 후 배팅 마감
        import asyncio
        asyncio.create_task(_close_betting(bet_view, bet_msg, guild_id, match_id))

    @discord.ui.button(label="🔄 다시 분배", style=discord.ButtonStyle.primary, row=0)
    async def reshuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        scored       = self.match_ctx['scored']
        duo_pairs    = self.match_ctx['duo_pairs']
        rival_pairs  = self.match_ctx['rival_pairs']
        used         = self.match_ctx['used_arrangements']

        new_t1, new_t2 = balance_teams(scored, duo_pairs, rival_pairs, used)
        arr_key = (frozenset(m.id for m in new_t1), frozenset(m.id for m in new_t2))
        used.append(arr_key)

        self.t1 = new_t1
        self.t2 = new_t2

        new_embed = build_lineup_embed(new_t1, new_t2, scored)

        # 공지채널 업데이트
        if self.announce_msg:
            try:
                await self.announce_msg.edit(embed=new_embed)
            except Exception:
                pass

        await interaction.response.edit_message(embed=new_embed, view=self)

    @discord.ui.button(label="🔀 수동 교체", style=discord.ButtonStyle.secondary, row=0)
    async def manual_swap_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ManualSwapView(self.t1, self.t2)
        await interaction.response.send_message("교체할 팀원을 각각 선택하세요.", view=view, ephemeral=True)
        await view.wait()
        if view.swap_done:
            self.t1 = view.new_t1
            self.t2 = view.new_t2
            scored  = self.match_ctx['scored']
            new_embed = build_lineup_embed(self.t1, self.t2, scored)
            if self.announce_msg:
                try:
                    await self.announce_msg.edit(embed=new_embed)
                except Exception:
                    pass
            try:
                await interaction.edit_original_response(embed=new_embed, view=self)
            except Exception:
                pass


class ManualSwapView(discord.ui.View):
    """1팀에서 1명, 2팀에서 1명 선택해서 교체"""
    def __init__(self, t1, t2):
        super().__init__(timeout=60)
        self.t1        = list(t1)
        self.t2        = list(t2)
        self.new_t1    = list(t1)
        self.new_t2    = list(t2)
        self.sel_t1_id = None
        self.sel_t2_id = None
        self.swap_done = False

        opts1 = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in t1[:25]]
        opts2 = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in t2[:25]]

        sel1 = discord.ui.Select(placeholder="🛡️ 1팀에서 교체할 멤버", min_values=1, max_values=1, options=opts1, row=0)
        sel2 = discord.ui.Select(placeholder="⚔️ 2팀에서 교체할 멤버", min_values=1, max_values=1, options=opts2, row=1)

        async def on_sel1(interaction):
            self.sel_t1_id = int(interaction.data['values'][0])
            await interaction.response.defer()

        async def on_sel2(interaction):
            self.sel_t2_id = int(interaction.data['values'][0])
            await interaction.response.defer()

        sel1.callback = on_sel1
        sel2.callback = on_sel2
        self.add_item(sel1)
        self.add_item(sel2)

    @discord.ui.button(label="✅ 교체", style=discord.ButtonStyle.success, row=2)
    async def swap_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.sel_t1_id or not self.sel_t2_id:
            return await interaction.response.send_message("❌ 두 팀에서 각각 한 명씩 선택해주세요.", ephemeral=True)

        m1 = next((m for m in self.t1 if m.id == self.sel_t1_id), None)
        m2 = next((m for m in self.t2 if m.id == self.sel_t2_id), None)

        if not m1 or not m2:
            return await interaction.response.send_message("❌ 선택한 멤버를 찾을 수 없습니다.", ephemeral=True)

        self.new_t1 = [m2 if m.id == m1.id else m for m in self.t1]
        self.new_t2 = [m1 if m.id == m2.id else m for m in self.t2]
        self.swap_done = True
        await interaction.response.edit_message(
            content=f"✅ **{m1.display_name}** ↔ **{m2.display_name}** 교체 완료!", view=None
        )
        self.stop()


# ── 배팅 시스템 ──────────────────────────────────────────

async def _close_betting(bet_view, bet_msg, guild_id, match_id):
    """5분 후 배팅 마감"""
    import asyncio
    await asyncio.sleep(300)
    bet_view.is_open = False
    # DB 업데이트
    try:
        db_interface.db.collection('servers').document(guild_id).collection('active_match').document('main').set(
            {'bet_open': False}, merge=True
        )
    except Exception:
        pass
    # 패널 업데이트
    try:
        embed = bet_view.build_embed(closed=True)
        await bet_msg.edit(content="🔒 **배팅이 마감되었습니다.**", embed=embed, view=None)
    except Exception:
        pass


class MatchBettingView(discord.ui.View):
    def __init__(self, match_id, t1_members, t2_members, guild_id):
        super().__init__(timeout=None)
        self.match_id   = match_id
        self.t1_members = t1_members
        self.t2_members = t2_members
        self.t1_ids     = set(str(m.id) for m in t1_members)
        self.t2_ids     = set(str(m.id) for m in t2_members)
        self.guild_id   = guild_id
        self.is_open    = True
        self.bet_msg    = None
        self.close_time = datetime.now(timezone.utc) + timedelta(minutes=5)

    def build_embed(self, closed=False):
        doc = db_interface.db.collection('servers').document(self.guild_id).collection('active_match').document('main').get()
        bets = doc.to_dict().get('bets', {'t1': {}, 't2': {}}) if doc.exists else {'t1': {}, 't2': {}}

        t1_total = sum(bets.get('t1', {}).values())
        t2_total = sum(bets.get('t2', {}).values())
        total    = t1_total + t2_total

        if total > 0:
            t1_odds = round(total / t1_total, 2) if t1_total > 0 else '∞'
            t2_odds = round(total / t2_total, 2) if t2_total > 0 else '∞'
        else:
            t1_odds = t2_odds = '-'

        now = datetime.now(timezone.utc)
        remain = max(0, int((self.close_time - now).total_seconds()))
        mins, secs = divmod(remain, 60)

        embed = discord.Embed(
            title="🪙 승부 예측 배팅",
            color=discord.Color.gold() if not closed else discord.Color.greyple()
        )
        embed.add_field(
            name="🛡️ 1팀",
            value=f"총 배팅: **{t1_total:,}P**\n배당률: **{t1_odds}x**\n{', '.join([m.display_name for m in self.t1_members])}",
            inline=True
        )
        embed.add_field(
            name="⚔️ 2팀",
            value=f"총 배팅: **{t2_total:,}P**\n배당률: **{t2_odds}x**\n{', '.join([m.display_name for m in self.t2_members])}",
            inline=True
        )
        if closed:
            embed.set_footer(text="배팅 마감")
        else:
            embed.set_footer(text=f"배팅 마감까지 {mins}분 {secs}초 남음")
        return embed

    @discord.ui.button(label="🛡️ 1팀 배팅", style=discord.ButtonStyle.blurple, custom_id="match_bet_t1")
    async def bet_t1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process_bet(interaction, 't1')

    @discord.ui.button(label="⚔️ 2팀 배팅", style=discord.ButtonStyle.red, custom_id="match_bet_t2")
    async def bet_t2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process_bet(interaction, 't2')

    async def _process_bet(self, interaction: discord.Interaction, team: str):
        if not self.is_open:
            return await interaction.response.send_message("❌ 배팅이 마감되었습니다.", ephemeral=True)

        uid     = str(interaction.user.id)
        is_t1   = uid in self.t1_ids
        is_t2   = uid in self.t2_ids
        my_team = 't1' if is_t1 else ('t2' if is_t2 else None)

        # 참가자는 본인 팀에만 배팅
        if my_team and my_team != team:
            return await interaction.response.send_message("❌ 내전 참가자는 본인 팀에만 배팅할 수 있습니다.", ephemeral=True)

        # 비참가자는 한 팀에만 배팅 가능 (기존 배팅 팀 확인)
        if not my_team:
            doc = db_interface.db.collection('servers').document(self.guild_id).collection('active_match').document('main').get()
            if doc.exists:
                bets = doc.to_dict().get('bets', {'t1': {}, 't2': {}})
                other_team = 't2' if team == 't1' else 't1'
                if uid in bets.get(other_team, {}):
                    return await interaction.response.send_message("❌ 이미 다른 팀에 배팅했습니다. 한 팀에만 배팅할 수 있습니다.", ephemeral=True)

        await interaction.response.send_modal(MatchBetModal(self.match_id, team, self.guild_id, self))


class MatchBetModal(discord.ui.Modal, title="포인트 배팅"):
    bet_amount = discord.ui.TextInput(label="배팅할 포인트", placeholder="예: 500", required=True)

    def __init__(self, match_id, team, guild_id, bet_view):
        super().__init__()
        self.match_id = match_id
        self.team     = team
        self.guild_id = guild_id
        self.bet_view = bet_view

    async def on_submit(self, interaction: discord.Interaction):
        if not self.bet_amount.value.isdigit() or int(self.bet_amount.value) <= 0:
            return await interaction.response.send_message("❌ 올바른 숫자를 입력하세요.", ephemeral=True)

        amount = int(self.bet_amount.value)
        user_data = db_interface.get_user_data(self.guild_id, interaction.user.id)
        pts = user_data.get('points', 0)

        if pts < amount:
            return await interaction.response.send_message(f"❌ 포인트가 부족합니다. (보유: {pts:,}P)", ephemeral=True)

        db_interface.update_user_points(self.guild_id, interaction.user.id, -amount)

        # DB에 배팅 기록
        match_ref = db_interface.db.collection('servers').document(self.guild_id).collection('active_match').document('main')
        doc = match_ref.get()
        if doc.exists:
            data = doc.to_dict()
            bets = data.get('bets', {'t1': {}, 't2': {}})
            uid  = str(interaction.user.id)
            bets[self.team][uid] = bets[self.team].get(uid, 0) + amount
            match_ref.update({'bets': bets})

        team_name = "1팀" if self.team == 't1' else "2팀"
        await interaction.response.send_message(f"✅ **{team_name}**에 **{amount:,}P** 배팅 완료!", ephemeral=True)

        # 패널 업데이트
        if self.bet_view.bet_msg:
            try:
                embed = self.bet_view.build_embed()
                await self.bet_view.bet_msg.edit(embed=embed)
            except Exception:
                pass


# ── 관리자 패널 ──────────────────────────────────────────

class AdminMatchPanel(discord.ui.View):
    def __init__(self, match_id, t1_members, t2_members, bet_view, cfg, guild_id):
        super().__init__(timeout=None)
        self.match_id   = match_id
        self.t1         = t1_members
        self.t2         = t2_members
        self.bet_view   = bet_view
        self.cfg        = cfg
        self.guild_id   = guild_id
        self.resolved   = False

    def _is_admin(self, interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        admin_role_id = self.cfg.get('admin_role_id')
        return bool(admin_role_id and any(r.id == int(admin_role_id) for r in interaction.user.roles))

    @discord.ui.button(label="🔀 팀 채널 분배", style=discord.ButtonStyle.primary, row=0)
    async def move_to_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)

        t1_ch_id = self.cfg.get('t1_id')
        t2_ch_id = self.cfg.get('t2_id')
        guild    = interaction.guild

        moved = 0
        if t1_ch_id:
            t1_ch = guild.get_channel(int(t1_ch_id))
            if t1_ch:
                for m in self.t1:
                    try: await m.move_to(t1_ch); moved += 1
                    except Exception: pass
        if t2_ch_id:
            t2_ch = guild.get_channel(int(t2_ch_id))
            if t2_ch:
                for m in self.t2:
                    try: await m.move_to(t2_ch); moved += 1
                    except Exception: pass

        await interaction.response.send_message(f"✅ {moved}명을 팀 채널로 이동했습니다.", ephemeral=True)

    @discord.ui.button(label="🏠 대기실 복귀", style=discord.ButtonStyle.secondary, row=0)
    async def move_to_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)

        lobby_id = self.cfg.get('lobby_id')
        if not lobby_id:
            return await interaction.response.send_message("❌ 대기실 채널이 설정되지 않았습니다.", ephemeral=True)

        lobby = interaction.guild.get_channel(int(lobby_id))
        if not lobby:
            return await interaction.response.send_message("❌ 대기실 채널을 찾을 수 없습니다.", ephemeral=True)

        moved = 0
        for m in self.t1 + self.t2:
            try: await m.move_to(lobby); moved += 1
            except Exception: pass

        await interaction.response.send_message(f"✅ {moved}명을 대기실로 복귀했습니다.", ephemeral=True)

    @discord.ui.button(label="🏆 1팀 승리", style=discord.ButtonStyle.success, row=1)
    async def t1_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
        if self.resolved:
            return await interaction.response.send_message("❌ 이미 정산된 경기입니다.", ephemeral=True)
        confirm_view = WinConfirmView(self, 't1', interaction)
        embed = discord.Embed(
            title="🏆 1팀 승리 확정?",
            description=f"**1팀 멤버:**\n{chr(10).join([m.display_name for m in self.t1])}\n\n정말로 1팀 승리로 정산하시겠습니까?",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

    @discord.ui.button(label="🏆 2팀 승리", style=discord.ButtonStyle.success, row=1)
    async def t2_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
        if self.resolved:
            return await interaction.response.send_message("❌ 이미 정산된 경기입니다.", ephemeral=True)
        confirm_view = WinConfirmView(self, 't2', interaction)
        embed = discord.Embed(
            title="🏆 2팀 승리 확정?",
            description=f"**2팀 멤버:**\n{chr(10).join([m.display_name for m in self.t2])}\n\n정말로 2팀 승리로 정산하시겠습니까?",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

    @discord.ui.button(label="❌ 경기 취소", style=discord.ButtonStyle.danger, row=1)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
        if self.resolved:
            return await interaction.response.send_message("❌ 이미 정산된 경기입니다.", ephemeral=True)

        # 배팅 환불
        doc_ref = db_interface.db.collection('servers').document(self.guild_id).collection('active_match').document('main')
        doc     = doc_ref.get()
        refund_count = 0
        if doc.exists:
            bets = doc.to_dict().get('bets', {'t1': {}, 't2': {}})
            for team_bets in bets.values():
                for uid, amount in team_bets.items():
                    db_interface.update_user_points(self.guild_id, int(uid), amount)
                    refund_count += 1
            doc_ref.delete()

        self.resolved = True
        await interaction.response.edit_message(
            content=f"❌ 경기가 취소되었습니다. {refund_count}명에게 배팅금 환불 완료.",
            view=None
        )

    async def resolve_match(self, winner_team: str, interaction: discord.Interaction):
        """승리팀 정산 처리"""
        if self.resolved:
            return

        self.resolved = True
        winner_members = self.t1 if winner_team == 't1' else self.t2
        loser_members  = self.t2 if winner_team == 't1' else self.t1
        guild_id       = self.guild_id
        guild          = interaction.guild

        # 전적 업데이트 + 참가 포인트 지급
        for m in winner_members:
            data = db_interface.get_user_data(guild_id, m.id)
            data['wins'] = int(data.get('wins', 0)) + 1
            db_interface.update_user_stats(guild_id, m.id, data)
            db_interface.update_user_points(guild_id, m.id, 150)  # 승리 포인트
        for m in loser_members:
            data = db_interface.get_user_data(guild_id, m.id)
            data['losses'] = int(data.get('losses', 0)) + 1
            db_interface.update_user_stats(guild_id, m.id, data)
            db_interface.update_user_points(guild_id, m.id, 75)   # 패배 포인트

        # 배팅 정산 (트위치 시스템)
        doc_ref = db_interface.db.collection('servers').document(guild_id).collection('active_match').document('main')
        doc     = doc_ref.get()

        now_kst = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
        guild_name = guild.name
        winner_name = "1팀" if winner_team == 't1' else "2팀"

        if doc.exists:
            bets      = doc.to_dict().get('bets', {'t1': {}, 't2': {}})
            win_bets  = bets.get(winner_team, {})
            lose_bets = bets.get('t2' if winner_team == 't1' else 't1', {})

            total_win  = sum(win_bets.values())
            total_lose = sum(lose_bets.values())
            total_pool = total_win + total_lose

            for uid, amount in win_bets.items():
                if total_win > 0:
                    payout  = int(amount * total_pool / total_win)
                    profit  = payout - amount
                    odds    = round(total_pool / total_win, 2)
                else:
                    payout = amount
                    profit = 0
                    odds   = 1.0

                db_interface.update_user_points(guild_id, int(uid), payout)

                # DM 전송
                member = guild.get_member(int(uid))
                if member:
                    try:
                        dm_embed = discord.Embed(
                            title="🪙 배팅 정산 알림",
                            color=discord.Color.gold()
                        )
                        dm_embed.add_field(name="서버", value=guild_name, inline=True)
                        dm_embed.add_field(name="일시", value=now_kst, inline=True)
                        dm_embed.add_field(name="결과", value=f"**{winner_name} 승리**", inline=False)
                        dm_embed.add_field(name="배팅 금액", value=f"{amount:,}P", inline=True)
                        dm_embed.add_field(name="배당률", value=f"{odds}x", inline=True)
                        dm_embed.add_field(name="수령 금액", value=f"**{payout:,}P** (+{profit:,}P)", inline=True)
                        await member.send(embed=dm_embed)
                    except Exception:
                        pass

            # 패배팀 배팅자 DM (잃은 금액 알림)
            for uid, amount in lose_bets.items():
                member = guild.get_member(int(uid))
                if member:
                    try:
                        dm_embed = discord.Embed(
                            title="🪙 배팅 정산 알림",
                            color=discord.Color.red()
                        )
                        dm_embed.add_field(name="서버", value=guild_name, inline=True)
                        dm_embed.add_field(name="일시", value=now_kst, inline=True)
                        dm_embed.add_field(name="결과", value=f"**{winner_name} 승리 (패배)**", inline=False)
                        dm_embed.add_field(name="배팅 금액", value=f"{amount:,}P", inline=True)
                        dm_embed.add_field(name="수령 금액", value="**0P** (-{:,}P)".format(amount), inline=True)
                        await member.send(embed=dm_embed)
                    except Exception:
                        pass

            doc_ref.delete()

        # 배팅 패널 마감 처리
        if self.bet_view and self.bet_view.bet_msg:
            try:
                self.bet_view.is_open = False
                embed = self.bet_view.build_embed(closed=True)
                await self.bet_view.bet_msg.edit(
                    content=f"🏆 **{winner_name} 승리! 배팅 정산 완료.**",
                    embed=embed,
                    view=None
                )
            except Exception:
                pass


# ── 승리 확인 뷰 ──────────────────────────────────────────

class WinConfirmView(discord.ui.View):
    def __init__(self, admin_panel: AdminMatchPanel, winner_team: str, original_interaction):
        super().__init__(timeout=60)
        self.admin_panel          = admin_panel
        self.winner_team          = winner_team
        self.original_interaction = original_interaction

    @discord.ui.button(label="✅ 확정", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✅ 정산을 처리 중입니다...", view=None)
        await self.admin_panel.resolve_match(self.winner_team, self.original_interaction)
        self.stop()

    @discord.ui.button(label="↩️ 되돌리기", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="↩️ 취소되었습니다.", view=None)
        self.stop()