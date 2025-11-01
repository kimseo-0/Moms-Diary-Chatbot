#!/usr/bin/env python
"""
가장 최근 채팅 메시지를 삭제하는 테스트 스크립트

Usage:
    python test_delete_last.py <session_id>
    
Example:
    python test_delete_last.py user-123
"""

import sys
from app.services.chat_repo import ChatRepository

def main():
    if len(sys.argv) < 2:
        print("❌ 사용법: python test_delete_last.py <session_id>")
        print("   예시: python test_delete_last.py user-123")
        sys.exit(1)
    
    session_id = sys.argv[1]
    repo = ChatRepository()
    
    # 삭제 전 최근 메시지 확인
    print(f"\n📋 [{session_id}] 삭제 전 최근 메시지 5개:")
    recent = repo.get_recent_messages(session_id, limit=5)
    if not recent:
        print("   (메시지 없음)")
    else:
        for i, msg in enumerate(reversed(recent), 1):
            print(f"   {i}. [{msg.role}] {msg.text[:50]}... (at: {msg.created_at})")
    
    # 최근 메시지 삭제
    print(f"\n🗑️  가장 최근 메시지 삭제 중...")
    deleted = repo.delete_last_message(session_id)
    
    if deleted:
        print("✅ 삭제 성공!")
    else:
        print("⚠️  삭제할 메시지가 없습니다.")
        sys.exit(0)
    
    # 삭제 후 최근 메시지 확인
    print(f"\n📋 [{session_id}] 삭제 후 최근 메시지 5개:")
    recent = repo.get_recent_messages(session_id, limit=5)
    if not recent:
        print("   (메시지 없음)")
    else:
        for i, msg in enumerate(reversed(recent), 1):
            print(f"   {i}. [{msg.role}] {msg.text[:50]}... (at: {msg.created_at})")
    
    print("\n✨ 완료!")

if __name__ == "__main__":
    main()
