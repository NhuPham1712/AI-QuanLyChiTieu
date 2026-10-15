import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db
from app import models, schemas, crud, ai_service

# Khởi tạo bảng dữ liệu
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Hệ thống Chatbot AI hỗ trợ Quản lý Tài chính Cá nhân và Lập kế hoạch Tiết kiệm"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.on_event("startup")
def startup_event():
    db = next(get_db())
    crud.init_default_data(db)

@app.get("/")
def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "message": "Trang tĩnh index.html chưa khởi tạo."
    }

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": os.getenv("CURRENT_TIME", "")
    }

@app.get("/api/check-gemini")
async def check_gemini():
    return await ai_service.test_gemini_connection()

@app.get("/api/check-chatgpt")
async def check_chatgpt():
    return await ai_service.test_openai_connection()

@app.post("/api/chat", response_model=schemas.ChatMessageResponse)
async def chat_endpoint(req: schemas.ChatMessageRequest, db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    
    # 1. Gọi AI service xử lý hội thoại
    result = await ai_service.process_chat(db, user.id, req.message)
    
    # 2. Tự động lưu các giao dịch bóc tách được vào DB
    for tx in result["parsed_transactions"]:
        crud.create_transaction(
            db=db,
            amount=tx.amount,
            category_name=tx.category,
            trans_type=tx.type,
            note=tx.note,
            user_id=user.id
        )

    # 3. Lưu lịch sử cuộc trò chuyện
    conv_id = crud.save_chat_history(
        db=db,
        user_id=user.id,
        conversation_id=req.conversation_id,
        user_msg=req.message,
        bot_msg=result["reply"],
        latency_ms=result["latency_ms"],
        status="success" if not result["guardrails_triggered"] else "guardrail_blocked"
    )

    return schemas.ChatMessageResponse(
        conversation_id=conv_id,
        reply=result["reply"],
        parsed_transactions=result["parsed_transactions"],
        source=result["source"],
        confidence=result.get("confidence", 0.95),
        debug_log=result.get("debug_log", ""),
        latency_ms=result["latency_ms"],
        guardrails_triggered=result["guardrails_triggered"]
    )

@app.get("/api/financial-summary", response_model=schemas.FinancialSummary)
def get_summary_endpoint(db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    return crud.get_financial_summary(db, user.id)

@app.get("/api/transactions")
def list_transactions(limit: int = 50, db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    txs = crud.get_transactions(db, user.id, limit=limit)
    return [
        {
            "id": t.id,
            "amount": t.amount,
            "category": t.category.name if t.category else "Khác",
            "type": t.category.type if t.category else "expense",
            "note": t.note,
            "date": str(t.transaction_date)
        }
        for t in txs
    ]

@app.post("/api/transactions")
def add_transaction(item: schemas.TransactionCreate, db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    tx = crud.create_transaction(
        db=db,
        amount=item.amount,
        category_name=item.category_name or "Khác",
        trans_type=item.type or "expense",
        note=item.note or "Thủ công",
        user_id=user.id
    )
    return {"status": "ok", "id": tx.id}

@app.delete("/api/transactions/{transaction_id}")
def remove_transaction(transaction_id: int, db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    success = crud.delete_transaction(db, transaction_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
    return {"status": "ok", "message": f"Đã xóa giao dịch #{transaction_id}"}

@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    cats = crud.get_categories(db, user.id)
    return [{"id": c.id, "name": c.name, "type": c.type} for c in cats]

@app.get("/api/saving-goals")
def list_saving_goals(db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    goals = crud.get_saving_goals(db, user.id)
    return [
        {
            "id": g.id,
            "name": g.name,
            "target_amount": g.target_amount,
            "current_amount": g.current_amount,
            "deadline": str(g.deadline) if g.deadline else None
        }
        for g in goals
    ]

@app.post("/api/saving-goals/{goal_id}/deposit")
def deposit_goal_endpoint(goal_id: int, amount: float = 500000.0, db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    g = crud.deposit_saving_goal(db, goal_id, amount, user.id)
    if not g:
        raise HTTPException(status_code=404, detail="Không tìm thấy mục tiêu tiết kiệm")
    return {"status": "ok", "message": f"Đã nạp {amount:,.0f} VNĐ vào quỹ {g.name}"}

@app.post("/api/demo-data")
def load_demo_endpoint(db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    crud.load_demo_transactions(db, user.id)
    return {"status": "ok", "message": "Đã nạp bộ dữ liệu mẫu giao dịch sinh động!"}

@app.post("/api/reset-data")
def reset_data_endpoint(db: Session = Depends(get_db)):
    user = crud.get_default_user(db)
    crud.reset_user_data(db, user.id)
    return {"status": "ok", "message": "Đã dọn dẹp sạch toàn bộ dữ liệu về trạng thái ban đầu!"}

@app.get("/api/export-csv")
def export_csv_endpoint(db: Session = Depends(get_db)):
    import csv
    import io
    from fastapi.responses import Response

    user = crud.get_default_user(db)
    txs = crud.get_transactions(db, user.id, limit=500)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Ngay", "Hang Muc", "Loai Giao Dich", "Ghi Chu", "So Tien (VND)"])
    for t in txs:
        cat_name = t.category.name if t.category else "Khac"
        cat_type = "Thu nhap" if (t.category and t.category.type == "income") else "Chi tieu"
        writer.writerow([t.id, str(t.transaction_date), cat_name, cat_type, t.note or "", f"{t.amount:.0f}"])

    content = output.getvalue()
    return Response(
        content=content.encode("utf-8-sig"), # utf-8 BOM for Excel
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=BaoCaoTaiChinh_UniBOT.csv"}
    )
