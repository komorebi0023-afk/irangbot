"""
리액션 역할 시스템
- 대시보드(입장/인사 옆 '리액션 역할' 탭)에서 설정한 내용을 읽어
  메시지에 이모지를 자동으로 달고, 클릭 시 역할을 부여/제거한다.

Firestore 구조:
servers/{guild_id}/reaction_roles/{doc_id}
    channel_id      : "123..."           전송/대상 채널
    message_id      : "456..." | ""      기존 메시지 ID (없으면 새로 생성)
    message_content : "내용"             새 메시지 생성 시 본문
    mode            : "add"|"remove"|"toggle"
    pairs           : [{ emoji, emoji_id, emoji_name, animated, role_id }]
    enabled         : True/False
    synced          : True/False         False면 봇이 이모지 재적용
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands

from db_interface import db, get_server_config

try:
    from google.cloud.firestore_v1.base_query import FieldFilter
    _HAS_FILTER = True
except Exception:                       # 구버전 SDK 호환
    _HAS_FILTER = False

MODE_ADD    = 'add'
MODE_REMOVE = 'remove'
MODE_TOGGLE = 'toggle'


# ── 헬퍼 ──────────────────────────────────────────────────────

def _emoji_key(emoji) -> str:
    """PartialEmoji/Emoji → 비교용 키 (커스텀은 id, 기본은 문자)"""
    if getattr(emoji, 'id', None):
        return str(emoji.id)
    return str(emoji.name)


def _pair_key(pair: dict) -> str:
    """DB 저장 쌍 → 비교용 키"""
    return str(pair.get('emoji_id') or pair.get('emoji') or '')


def _pair_to_reaction(pair: dict):
    """DB 저장 쌍 → message.add_reaction 에 넣을 값"""
    eid = pair.get('emoji_id')
    if eid:
        return discord.PartialEmoji(
            name=pair.get('emoji_name') or 'emoji',
            id=int(eid),
            animated=bool(pair.get('animated')),
        )
    return pair.get('emoji')


def _rr_col(guild_id):
    return db.collection('servers').document(str(guild_id)).collection('reaction_roles')


def _query_unsynced(guild_id):
    col = _rr_col(guild_id)
    if _HAS_FILTER:
        return col.where(filter=FieldFilter('synced', '==', False)).stream()
    return col.where('synced', '==', False).stream()


def _is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    cfg = get_server_config(interaction.guild.id)
    role_id = cfg.get('admin_role_id')
    return bool(role_id and any(r.id == int(role_id) for r in interaction.user.roles))


# ── Cog ──────────────────────────────────────────────────────

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {message_id(str): (guild_id, config dict)} — 반응 처리용 캐시
        self._cache = {}
        self.sync_loop.start()

    def cog_unload(self):
        self.sync_loop.cancel()

    # ── 설정 조회 ────────────────────────────────────────────

    def _find_config(self, guild_id, message_id):
        key = str(message_id)
        cached = self._cache.get(key)
        if cached and str(cached[0]) == str(guild_id):
            return cached[1]

        col = _rr_col(guild_id)
        try:
            if _HAS_FILTER:
                docs = col.where(filter=FieldFilter('message_id', '==', key)).limit(1).stream()
            else:
                docs = col.where('message_id', '==', key).limit(1).stream()
            for doc in docs:
                data = doc.to_dict()
                self._cache[key] = (str(guild_id), data)
                return data
        except Exception as e:
            print(f"❌ [리액션역할] 설정 조회 실패: {e}")
        return None

    # ── 리액션 이벤트 ────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle(payload, is_add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle(payload, is_add=False)

    async def _handle(self, payload: discord.RawReactionActionEvent, is_add: bool):
        if payload.guild_id is None:
            return
        if self.bot.user and payload.user_id == self.bot.user.id:
            return

        cfg = self._find_config(payload.guild_id, payload.message_id)
        if not cfg or not cfg.get('enabled', True):
            return

        key  = _emoji_key(payload.emoji)
        pair = next((p for p in cfg.get('pairs', []) if _pair_key(p) == key), None)
        if not pair or not pair.get('role_id'):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        role = guild.get_role(int(pair['role_id']))
        if not role:
            return

        # 안전장치: 관리자 권한 역할 / 봇보다 높은 역할은 건드리지 않음
        if role.permissions.administrator:
            print(f"⚠️ [리액션역할] 관리자 권한 역할이라 건너뜀: {role.name}")
            return
        if guild.me.top_role <= role:
            print(f"⚠️ [리액션역할] 봇보다 높은 역할이라 건너뜀: {role.name}")
            return

        mode = cfg.get('mode', MODE_TOGGLE)

        try:
            if mode == MODE_ADD:
                if is_add and role not in member.roles:
                    await member.add_roles(role, reason="리액션 역할")
                    print(f"✅ [리액션역할] 부여: {member.display_name} → {role.name}")
            elif mode == MODE_REMOVE:
                if is_add and role in member.roles:
                    await member.remove_roles(role, reason="리액션 역할")
                    print(f"✅ [리액션역할] 제거: {member.display_name} → {role.name}")
            else:  # toggle
                if is_add:
                    await member.add_roles(role, reason="리액션 역할(토글)")
                    print(f"✅ [리액션역할] 부여: {member.display_name} → {role.name}")
                else:
                    await member.remove_roles(role, reason="리액션 역할(토글)")
                    print(f"✅ [리액션역할] 제거: {member.display_name} → {role.name}")
        except discord.Forbidden:
            print(f"❌ [리액션역할] 권한 부족: {role.name}")
        except Exception as e:
            print(f"❌ [리액션역할] 처리 실패: {e}")
            return

        # add/remove 모드는 버튼처럼 반복 사용되도록 유저 반응을 되돌림
        if is_add and mode in (MODE_ADD, MODE_REMOVE):
            try:
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(payload.message_id)
                    await msg.remove_reaction(payload.emoji, member)
            except Exception:
                pass

    # ── 동기화 (메시지 생성 + 이모지 부착) ──────────────────

    @tasks.loop(seconds=45)
    async def sync_loop(self):
        for guild in list(self.bot.guilds):
            try:
                docs = list(_query_unsynced(guild.id))
            except Exception as e:
                print(f"❌ [리액션역할] 동기화 조회 실패({guild.name}): {e}")
                continue
            for doc in docs:
                await self._sync_doc(guild, doc)

    @sync_loop.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()

    async def sync_guild_now(self, guild) -> int:
        """즉시 동기화. 처리한 설정 수 반환"""
        count = 0
        for doc in _rr_col(guild.id).stream():
            if await self._sync_doc(guild, doc):
                count += 1
        return count

    async def _sync_doc(self, guild, doc) -> bool:
        data = doc.to_dict() or {}
        ref  = doc.reference

        channel_id = data.get('channel_id')
        if not channel_id:
            return False
        channel = guild.get_channel(int(channel_id))
        if not channel:
            print(f"⚠️ [리액션역할] 채널을 찾을 수 없음: {channel_id}")
            return False

        message = None
        message_id = data.get('message_id')

        # 1) 기존 메시지 사용
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                print(f"⚠️ [리액션역할] 메시지를 찾을 수 없음: {message_id}")
                ref.set({'synced': True, 'sync_error': '메시지를 찾을 수 없습니다.'}, merge=True)
                return False
            except Exception as e:
                print(f"❌ [리액션역할] 메시지 조회 실패: {e}")
                return False

        # 2) 새 메시지 생성
        else:
            content = (data.get('message_content') or '').strip()
            if not content:
                return False
            try:
                message = await channel.send(content)
                ref.set({'message_id': str(message.id)}, merge=True)
                data['message_id'] = str(message.id)
                print(f"✅ [리액션역할] 새 메시지 생성: {message.id}")
            except Exception as e:
                print(f"❌ [리액션역할] 메시지 전송 실패: {e}")
                return False

        pairs = data.get('pairs', [])
        want  = {_pair_key(p) for p in pairs if p.get('role_id')}

        # 더 이상 설정에 없는 봇 반응 제거
        for reaction in message.reactions:
            if _emoji_key(reaction.emoji) not in want:
                try:
                    await message.remove_reaction(reaction.emoji, guild.me)
                except Exception:
                    pass

        # 필요한 이모지 부착
        existing = {_emoji_key(r.emoji) for r in message.reactions}
        for p in pairs:
            if not p.get('role_id'):
                continue
            if _pair_key(p) in existing:
                continue
            try:
                await message.add_reaction(_pair_to_reaction(p))
            except Exception as e:
                print(f"❌ [리액션역할] 이모지 부착 실패({p.get('emoji')}): {e}")

        ref.set({'synced': True, 'sync_error': ''}, merge=True)
        self._cache[str(data.get('message_id'))] = (str(guild.id), {**data, 'synced': True})
        return True

    # ── 슬래시 명령어 ────────────────────────────────────────

    @app_commands.command(
        name="리액션역할동기화",
        description="[관리자] 대시보드에서 설정한 리액션 역할을 즉시 적용합니다."
    )
    async def sync_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not _is_admin(interaction):
            return await interaction.followup.send("❌ 권한이 없습니다.", ephemeral=True)

        self._cache.clear()
        try:
            count = await self.sync_guild_now(interaction.guild)
        except Exception as e:
            return await interaction.followup.send(f"❌ 동기화 실패: {e}", ephemeral=True)

        await interaction.followup.send(
            f"✅ 리액션 역할 {count}개 설정을 적용했습니다.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
