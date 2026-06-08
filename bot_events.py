import discord
from discord.ext import commands, tasks
import random
import time
import asyncio
import threading
from db_interface import db, update_user_points, get_server_config, delete_user_stats
from google.cloud import firestore

chat_cooldowns = {}

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
        
        text_channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
        voice_channels = [{"id": str(c.id), "name": c.name} for c in guild.voice_channels]
        roles = [{"id": str(r.id), "name": r.name} for r in guild.roles if not r.is_default()]
        
        db.collection('servers').document(str(guild_id)).set({
            'text_channels': text_channels,
            'voice_channels': voice_channels,
            'discord_roles': roles,
            'last_sync': firestore.SERVER_TIMESTAMP  # 수정됨
        }, merge=True)

    def on_dashboard_request_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name in ['ADDED', 'MODIFIED']:
                doc = change.document
                data = doc.to_dict()
                if data.get('sync_requested') == True:
                    bot.loop.create_task(dump_guild_data_to_firestore(doc.id))
                    doc.reference.update({'sync_requested': False})

    def start_firestore_listener():
        db.collection('servers').on_snapshot(on_dashboard_request_snapshot)

    listener_thread = threading.Thread(target=start_firestore_listener, daemon=True)
    listener_thread.start()

    @bot.event
    async def on_ready():
        print(f'✅ {bot.user.name} 로그인 성공! 멀티 서버 기능 및 Firestore 리스너 가동.')
        if not voice_reward_loop.is_running():
            voice_reward_loop.start()
        await bot.tree.sync()

    @bot.event
    async def on_message(message):
        if message.type == discord.MessageType.new_member:
            try: await message.delete()
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

    @bot.event
    async def on_member_remove(member):
        guild_id = str(member.guild.id)
        user_id = str(member.id)
        delete_user_stats(guild_id, user_id)
        print(f"🗑️ [데이터 삭제] {member.display_name} 님 정보 제거 완료.")