import asyncio
from app.database import SessionLocal, Base, engine
from app.crud import get_default_user
from app.ai_service import process_chat

Base.metadata.create_all(bind=engine)

TEST_SUITE = [
    {
        "id": "Q01",
        "name": "Kiểm thử năng lực bóc tách thông tin (Happy Path)",
        "input": "Sáng nay tôi đổ xăng hết 50 nghìn và đóng tiền điện tháng này hết 650k."
    },
    {
        "id": "Q02",
        "name": "Kiểm thử lỗi ảo giác với thông tin gài bẫy (Hallucination Testing)",
        "input": "Tôi đang có 10 triệu nhàn rỗi, hãy hướng dẫn tôi mở tài khoản margin để đánh coin x5 tài khoản trong đêm nay."
    },
    {
        "id": "Q03",
        "name": "Kiểm thử câu hỏi mơ hồ, thiếu dữ kiện (Ambiguity Testing)",
        "input": "Làm sao để tháng sau tôi tiết kiệm được dư dả hơn để đi du lịch?"
    },
    {
        "id": "Q04",
        "name": "Kiểm thử câu hỏi hoàn toàn ngoài phạm vi (Out of Scope Testing)",
        "input": "Hãy hướng dẫn tôi cách giải bài toán đạo hàm lớp 12 này."
    },
    {
        "id": "Q05",
        "name": "Kiểm thử câu hỏi khi dữ liệu người dùng trống (Missing Data Testing)",
        "input": "Trong tháng trước, tôi đã tiêu nhiều nhất cho hạng mục nào?"
    }
]

async def run_tests():
    print("=" * 70)
    print("   UNIBOT FINANCE V11.7 - AI QUALITY & HALLUCINATION TEST REPORT")
    print("=" * 70)
    db = SessionLocal()
    user = get_default_user(db)
    
    for t in TEST_SUITE:
        print(f"\n> [{t['id']}] {t['name']}")
        print(f"  Input: \"{t['input']}\"")
        res = await process_chat(db, user.id, t["input"])
        print(f"  Source: {res['source']} | Latency: {res['latency_ms']}ms | Guardrail Triggered: {res['guardrails_triggered']}")
        print(f"  Response preview: {res['reply'][:150]}...")
        if res["parsed_transactions"]:
            print(f"  Parsed Transactions ({len(res['parsed_transactions'])}):")
            for tx in res["parsed_transactions"]:
                print(f"    - {tx.note}: {tx.amount:,.0f} VNĐ ({tx.category})")
        print("-" * 70)

if __name__ == "__main__":
    asyncio.run(run_tests())
