import firebase_admin
from firebase_admin import credentials, firestore
import os

# Firebase 초기화
cred = credentials.Certificate('firebase_key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 데이터베이스 헬퍼 함수 (Firestore 기반)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_user_data(guild_id, user_id):
    doc_ref = db.collection('servers').document(str(guild_id)).collection('users').document(str(user_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    # 데이터가 없을 시 기본값 반환
    default = {
        'guild_id': str(guild_id), 'user_id': str(user_id), 'points': 1000,
        'score': 0.0, 'battletag': '-', 'nickname': '-', 'main_pos': '-',
        'sub_pos': '-', 'max_tier': '-', 'current_tier': '-', 'main_hero': '-',
        'wins': '0', 'losses': '0', 'last_daily': '', 'last_relief': ''
    }
    doc_ref.set(default)
    return default

def update_user_points(guild_id, user_id, amount):
    doc_ref = db.collection('servers').document(str(guild_id)).collection('users').document(str(user_id))
    doc = doc_ref.get()
    current = doc.to_dict().get('points', 1000) if doc.exists else 1000
    doc_ref.set({'points': current + amount}, merge=True)

def update_user_stats(guild_id, user_id, update_data):
    doc_ref = db.collection('servers').document(str(guild_id)).collection('users').document(str(user_id))
    doc_ref.set(update_data, merge=True)

def set_role_id(guild_id, role_key, role_id):
    doc_ref = db.collection('servers').document(str(guild_id)).collection('roles').document(role_key)
    if role_id is None:
        doc_ref.delete()
    else:
        doc_ref.set({'role_id': str(role_id)}, merge=True)

def get_role_id(guild_id, role_key):
    doc = db.collection('servers').document(str(guild_id)).collection('roles').document(role_key).get()
    data = doc.to_dict()
    return int(data.get('role_id')) if data and 'role_id' in data else None

def get_all_mapped_role_ids(guild_id):
    """pos_* 및 tier_* 에 해당하는 모든 역할 ID 목록 반환 (역할 동기화용)"""
    roles_ref = db.collection('servers').document(str(guild_id)).collection('roles')
    docs = roles_ref.stream()
    result = []
    for doc in docs:
        key = doc.id
        if key.startswith('pos_') or key.startswith('tier_'):
            data = doc.to_dict()
            if data and 'role_id' in data:
                try:
                    result.append(int(data['role_id']))
                except (ValueError, TypeError):
                    pass
    return result

def get_server_config(guild_id):
    doc = db.collection('servers').document(str(guild_id)).collection('config').document('main').get()
    return doc.to_dict() if doc.exists else {}

def update_server_config(guild_id, key, val):
    db.collection('servers').document(str(guild_id)).collection('config').document('main').set({key: str(val)}, merge=True)

def is_admin(ctx):
    # 1. 서버장 및 관리자 권한 체크
    if ctx.author.guild_permissions.administrator:
        return True
    # 2. 지정된 관리자 역할 체크
    cfg = get_server_config(ctx.guild.id)
    admin_role_id = cfg.get('admin_role_id')
    if admin_role_id:
        if any(role.id == int(admin_role_id) for role in ctx.author.roles):
            return True
    return False

def save_match_data(guild_id, data):
    db.collection('servers').document(str(guild_id)).collection('active_match').document('main').set(data, merge=True)

def load_match_data(guild_id):
    doc = db.collection('servers').document(str(guild_id)).collection('active_match').document('main').get()
    return doc.to_dict() if doc.exists else {}

def save_match_history(guild_id, team1_users, team2_users, winner_team):
    match_ref = db.collection('servers').document(str(guild_id)).collection('match_history').document()
    match_data = {
        'timestamp': firestore.SERVER_TIMESTAMP,
        'team1_users': team1_users,
        'team2_users': team2_users,
        'winner_team': winner_team,
        'score_change': 0.0
    }
    match_ref.set(match_data)
    return match_ref.id

def delete_user_stats(guild_id, user_id):
    db.collection('servers').document(str(guild_id)).collection('users').document(str(user_id)).delete()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 임시채널 관련 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_temp_channel_config(guild_id):
    """임시채널 설정 반환 (대시보드에서 저장한 config에서 읽음)"""
    cfg = get_server_config(guild_id)
    return {
        'enabled':           cfg.get('temp_channel_enabled', False),
        'trigger_channel_id': cfg.get('temp_trigger_channel_id', ''),
        'category_id':        cfg.get('temp_category_id', ''),
        'delete_timeout':     int(cfg.get('temp_delete_timeout', 30)),
        'max_channels':       int(cfg.get('temp_max_channels', 0)),
        'default_user_limit': int(cfg.get('temp_default_user_limit', 0)),
    }

def save_temp_channel(guild_id, channel_id, owner_id):
    """생성된 임시채널 정보 저장"""
    db.collection('servers').document(str(guild_id)).collection('temp_channels').document(str(channel_id)).set({
        'channel_id': str(channel_id),
        'owner_id':   str(owner_id),
        'created_at': firestore.SERVER_TIMESTAMP,
    })

def delete_temp_channel(guild_id, channel_id):
    """임시채널 정보 삭제"""
    db.collection('servers').document(str(guild_id)).collection('temp_channels').document(str(channel_id)).delete()

def get_temp_channel(guild_id, channel_id):
    """임시채널 정보 조회"""
    doc = db.collection('servers').document(str(guild_id)).collection('temp_channels').document(str(channel_id)).get()
    return doc.to_dict() if doc.exists else None

def get_user_temp_channel_count(guild_id, owner_id):
    """유저가 현재 생성한 임시채널 수 조회"""
    docs = db.collection('servers').document(str(guild_id)).collection('temp_channels')\
        .where('owner_id', '==', str(owner_id)).stream()
    return sum(1 for _ in docs)

def update_temp_channel_owner(guild_id, channel_id, new_owner_id):
    """임시채널 방장 변경"""
    db.collection('servers').document(str(guild_id)).collection('temp_channels').document(str(channel_id)).set(
        {'owner_id': str(new_owner_id)}, merge=True
    )