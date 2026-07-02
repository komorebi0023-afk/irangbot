import discord
from discord.ext import commands, tasks
import random
import time
import asyncio
import threading
from db_interface import (
    db, update_user_points, update_user_stats, get_server_config, delete_user_stats,
    get_temp_channel_config, save_temp_channel, delete_temp_channel,
    get_temp_channel, get_user_temp_channel_count, update_temp_channel_owner,
    delete_all_server_data
)
from google.cloud import firestore
import views

chat_cooldowns = {}

# 임시채널 삭제 대기 중인 태스크 관리 {channel_id: asyncio.Task}
_temp_delete_tasks = {}

# ── 멤버 인사 헬퍼 ────────────────────────────────────────────

def _format_welcome_msg(template: str, member: discord.Member) -> str:
    """변수 치환"""
    guild = member.guild
    return (template
        .replace('[user]',        member.mention)
        .replace('[userName]',    member.display_name)
        .replace('[memberCount]', str(guild.member_count))
        .replace('[server]',      guild.name)
        .replace('[inviter]',     '')       # 초대자는 별도 추적 필요
        .replace('[inviterName]', '')
        .replace('[invites]',     '')
    )

async def _send_welcome_msg(bot, member: discord.Member, channel_id: str, msg: str):
    """채널 또는 DM으로 메시지 전송"""
    if not channel_id or not msg: return
    if channel_id == 'dm':
        try: await member.send(msg)
        except Exception: pass
    else:
        channel = member.guild.get_channel(int(channel_id))
        if channel:
            try: await channel.send(msg)
            except Exception: pass

def setup_events(bot):

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

    async def dump_guild_data_to_firestore(guild_id):
        guild = bot.get_guild(int(guild_id))
        if not guild: return
        text_channels  = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
        voice_channels = [{"id": str(c.id), "name": c.name} for c in guild.voice_channels]
        roles          = [{"id": str(r.id), "name": r.name} for r in guild.roles if not r.is_default()]
        db.collection('servers').document(str(guild_id)).set({
            'text_channels':  text_channels,
            'voice_channels': voice_channels,
            'discord_roles':  roles,
            'last_sync':      firestore.SERVER_TIMESTAMP
        }, merge=True)

    def on_dashboard_request_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name in ['ADDED', 'MODIFIED']:
                doc  = change.document
                data = doc.to_dict()
                if data.get('sync_requested') == True:
                    bot.loop.create_task(dump_guild_data_to_firestore(doc.id))
                    doc.reference.update({'sync_requested': False})

    def start_firestore_listener():
        db.collection('servers').on_snapshot(on_dashboard_request_snapshot)

    listener_thread = threading.Thread(target=start_firestore_listener, daemon=True)
    listener_thread.start()

    # ── 임시채널 삭제 스케줄러 ────────────────────────────────
    async def schedule_temp_channel_delete(guild_id, channel_id, timeout):
        """timeout초 후 채널이 비어있으면 삭제"""
        await asyncio.sleep(timeout)
        guild   = bot.get_guild(int(guild_id))
        if not guild: return
        channel = guild.get_channel(int(channel_id))
        if not channel: 
            delete_temp_channel(str(guild_id), str(channel_id))
            return
        real_members = [m for m in channel.members if not m.bot]
        if len(real_members) == 0:
            try:
                await channel.delete(reason="임시채널 자동 삭제 (빈 채널)")
            except Exception:
                pass
            delete_temp_channel(str(guild_id), str(channel_id))
        _temp_delete_tasks.pop(channel_id, None)

    def cancel_delete_task(channel_id):
        task = _temp_delete_tasks.pop(channel_id, None)
        if task and not task.done():
            task.cancel()

    # ── 이벤트 핸들러 ─────────────────────────────────────────

    @bot.event
    async def on_ready():
        print(f'✅ {bot.user.name} 로그인 성공!')
        if not voice_reward_loop.is_running():
            voice_reward_loop.start()
        await bot.tree.sync()

        # 현재 참여 중인 서버 목록 public_servers에 동기화
        for guild in bot.guilds:
            try:
                db.collection('public_servers').document(str(guild.id)).set({
                    'guild_id':     str(guild.id),
                    'name':         guild.name,
                    'icon': str(guild.icon.key) if guild.icon else None,
                    'member_count': guild.member_count,
                }, merge=True)
            except Exception as e:
                print(f"❌ [서버 목록 동기화 실패] {guild.name}: {e}")
        print(f"✅ {len(bot.guilds)}개 서버 목록 동기화 완료")

    @bot.event
    async def on_message(message):
        if message.type == discord.MessageType.new_member:
            try: await message.delete()
            except: pass

        if message.author.bot: return  # 봇 메시지 무시 (데이터 저장 방지)

        uid = str(message.author.id)
        now = time.time()
        if uid not in chat_cooldowns or (now - chat_cooldowns[uid]) >= 30:
            if message.guild:
                reward = random.randint(1, 5)
                update_user_points(message.guild.id, uid, reward)
                chat_cooldowns[uid] = now
            if message.guild and not message.author.bot:
                        cfg = get_server_config(message.guild.id)
                        if cfg.get('pubg_system_enabled') == True:
                            pubg_ch_id = cfg.get('pubg_channel_id')
                            if pubg_ch_id and str(message.channel.id) == str(pubg_ch_id):
                                pubg_nick = message.content.strip()
                                if pubg_nick:
                                    # DB 저장
                                    update_user_stats(
                                        message.guild.id,
                                        message.author.id,
                                        {'pubg_nickname': pubg_nick}
                                    )
                                    # 디스코드 닉네임 변경
                                    base_nick = message.author.display_name.split(' (')[0]
                                    new_nick  = f"{base_nick} ({pubg_nick})"
                                    if len(new_nick) > 32:
                                        new_nick = new_nick[:32]
                                    try:
                                        await message.author.edit(nick=new_nick)
                                    except discord.errors.Forbidden:
                                        pass
                                    try:
                                        await message.channel.send(
                                            f"✅ {message.author.mention} 배그 닉네임이 **{pubg_nick}**으로 등록되었습니다!",
                                            delete_after=5
                                        )
                                    except Exception:
                                        pass
        await bot.process_commands(message)

    @bot.event
    async def on_member_join(member):
        """서버 입장 시: 자동역할 부여 + 멤버 인사 메시지"""
        if member.bot: return  # 봇 입장 시 데이터 저장 방지
        guild_id = str(member.guild.id)

        # ── 자동역할 처리 ──────────────────────────────────
        try:
            auto_roles_snap = db.collection('servers').document(guild_id).collection('auto_roles').stream()
            for doc in auto_roles_snap:
                data    = doc.to_dict()
                role_id = data.get('role_id')
                if not role_id: continue
                role = member.guild.get_role(int(role_id))
                if not role: continue
                # 관리자 권한 역할은 절대 부여하지 않음
                if role.permissions.administrator: continue
                if data.get('type') == 'give':
                    try: await member.add_roles(role)
                    except Exception: pass
                elif data.get('type') == 'remove':
                    try: await member.remove_roles(role)
                    except Exception: pass
        except Exception as e:
            print(f"❌ [자동역할 오류] {e}")

        # ── 멤버 인사 메시지 ────────────────────────────────
        try:
            cards_snap = db.collection('servers').document(guild_id).collection('welcome_cards').stream()
            for doc in cards_snap:
                card = doc.to_dict()
                if not card.get('enabled', True): continue
                if card.get('type') != 'join': continue
                msg = _format_welcome_msg(card.get('message', ''), member)
                await _send_welcome_msg(bot, member, card.get('channel', ''), msg)
        except Exception as e:
            print(f"❌ [멤버 인사 오류] {e}")

    @bot.event
    async def on_member_remove(member):
        if member.bot: return
        guild_id = str(member.guild.id)
        user_id  = str(member.id)
        delete_user_stats(guild_id, user_id)
        print(f"🗑️ [데이터 삭제] {member.display_name} 님 정보 제거 완료.")

        # ── 퇴장 인사 메시지 ────────────────────────────────
        try:
            cards_snap = db.collection('servers').document(guild_id).collection('welcome_cards').stream()
            for doc in cards_snap:
                card = doc.to_dict()
                if not card.get('enabled', True): continue
                if card.get('type') != 'leave': continue
                msg = _format_welcome_msg(card.get('message', ''), member)
                await _send_welcome_msg(bot, member, card.get('channel', ''), msg)
        except Exception as e:
            print(f"❌ [퇴장 인사 오류] {e}")

    @bot.event
    async def on_guild_join(guild):
        """봇이 서버에 새로 참여했을 때 기존 멤버 데이터 스캔"""
        print(f"✅ [서버 참여] {guild.name} ({guild.id}) - 기존 멤버 스캔 시작")
        guild_id = str(guild.id)
        # 서버 공개 정보 저장 (홈페이지 서버 리스트용)
        try:
            db.collection('public_servers').document(guild_id).set({
                'guild_id':    guild_id,
                'name':        guild.name,
                'icon': str(guild.icon.key) if guild.icon else None,
                'member_count': guild.member_count,
            }, merge=True)
        except Exception as e:
            print(f"❌ [서버 공개 정보 저장 실패] {e}")

        # 기존 멤버 기본 데이터 생성 (봇 제외)
        count = 0
        for member in guild.members:
            if member.bot: continue
            try:
                from db_interface import get_user_data
                get_user_data(guild_id, str(member.id))  # 없으면 기본값 생성
                count += 1
            except Exception:
                pass
        print(f"✅ [멤버 스캔 완료] {guild.name}: {count}명")

    @bot.event
    async def on_guild_remove(guild):
        """봇이 서버에서 추방/탈퇴 시 해당 서버의 모든 데이터 삭제"""
        try:
            delete_all_server_data(str(guild.id))
            # 공개 서버 목록에서도 제거
            db.collection('public_servers').document(str(guild.id)).delete()
            print(f"🗑️ [서버 추방] {guild.name} ({guild.id}) 데이터 삭제 완료.")
        except Exception as e:
            print(f"❌ [서버 추방 데이터 삭제 실패] {guild.name}: {e}")

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.bot: return
        guild    = member.guild
        guild_id = str(guild.id)

        # 복수 임시채널 설정 로드
        configs_snap = db.collection('servers').document(guild_id).collection('temp_channels_config').stream()
        tc_configs   = [doc.to_dict() for doc in configs_snap]
        if not tc_configs: return

        # 트리거 채널 ID → 설정 매핑
        trigger_map = {str(c.get('trigger_channel_id', '')): c for c in tc_configs if c.get('trigger_channel_id')}

        # ── 트리거 채널 접속 → 임시채널 생성 ──────────────────
        if after.channel and str(after.channel.id) in trigger_map:
            cfg         = trigger_map[str(after.channel.id)]
            category_id = cfg.get('category_id', '')
            timeout     = int(cfg.get('delete_timeout', 30))
            max_ch      = int(cfg.get('max_channels', 0))
            user_limit  = int(cfg.get('default_user_limit', 0))

            # 최대 채널 수 체크
            if max_ch > 0:
                count = get_user_temp_channel_count(guild_id, str(member.id))
                if count >= max_ch:
                    try:
                        await member.send(f"❌ 임시채널은 최대 {max_ch}개까지만 생성할 수 있습니다.")
                    except Exception:
                        pass
                    return

            category = guild.get_channel(int(category_id)) if category_id else None
            nick     = member.display_name.split(' (')[0]
            ch_name  = f"{nick}의 채널"

            try:
                new_channel = await guild.create_voice_channel(
                    name=ch_name,
                    category=category,
                    user_limit=user_limit,
                    reason=f"임시채널 생성 by {member.display_name}"
                )
                await member.move_to(new_channel)
                save_temp_channel(guild_id, str(new_channel.id), str(member.id))
                # 해당 임시채널에 timeout 정보 저장 (삭제 시 필요)
                db.collection('servers').document(guild_id).collection('temp_channels').document(str(new_channel.id)).set(
                    {'delete_timeout': timeout}, merge=True
                )
                await asyncio.sleep(0.5)
                await views.send_temp_channel_panel(new_channel, member)
            except Exception as e:
                print(f"❌ [임시채널 생성 실패] {e}")
            return

        # ── 임시채널에서 유저가 나갔을 때 처리 ───────────────
        if before.channel and str(before.channel.id) not in trigger_map:
            tc = get_temp_channel(guild_id, str(before.channel.id))
            if not tc: return

            timeout      = int(tc.get('delete_timeout', 30))
            real_members = [m for m in before.channel.members if not m.bot]

            if len(real_members) == 0:
                cancel_delete_task(before.channel.id)
                task = asyncio.create_task(
                    schedule_temp_channel_delete(guild_id, before.channel.id, timeout)
                )
                _temp_delete_tasks[before.channel.id] = task
            elif str(member.id) == str(tc.get('owner_id')):
                new_owner = next((m for m in real_members), None)
                if new_owner:
                    update_temp_channel_owner(guild_id, str(before.channel.id), str(new_owner.id))
                    await views.update_temp_channel_panel(before.channel, new_owner)

        # ── 임시채널에 유저가 들어왔을 때 → 삭제 타이머 취소 ──
        if after.channel:
            tc = get_temp_channel(guild_id, str(after.channel.id))
            if tc:
                cancel_delete_task(after.channel.id)