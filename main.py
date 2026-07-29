import discord
from discord.ext import commands
import os
import db_interface
import bot_events
import slashes  # 이름이 변경된 명령어 파일 로드
import views    # 영구 버튼 유지를 위해 UI 파일 로드
import reaction_roles

class IrangBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!', 
            intents=discord.Intents.all(),
            help_command=None
        )

    async def setup_hook(self):
        # 1. 이벤트 리스너 등록
        bot_events.setup_events(self)
        
        # 2. 명령어 Cog 로드
        await slashes.setup(self)
        await reaction_roles.setup(self)
        
        # 3. 영구 뷰(Persistent View) 등록
        self.add_view(views.EntryButtonView()) 
        
        # 4. 슬래시 명령어 전역 동기화
        print("⏳ 슬래시 명령어를 동기화하는 중...")
        await self.tree.sync()
        print("✅ 슬래시 명령어 동기화 완료!")

bot = IrangBot()

if __name__ == "__main__":
    token = os.environ.get('BOT_TOKEN')
    if not token and os.path.exists('token.txt'):
        with open('token.txt', 'r', encoding='utf-8') as f:
            token = f.read().strip()
    
    if token:
        bot.run(token)
    else:
        print("❌ 토큰을 찾을 수 없습니다. 환경변수 BOT_TOKEN 또는 token.txt를 확인하세요.")