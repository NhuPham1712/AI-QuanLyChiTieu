import datetime
from sqlalchemy.orm import Session
from app.models import User, Category, Transaction, SavingGoal, Conversation, Message, AILog
from app.schemas import FinancialSummary

DEFAULT_CATEGORIES = [
    # Hạng mục Chi tiêu (Expense)
    {"name": "Ăn uống", "type": "expense"},
    {"name": "Di chuyển & Xe cộ", "type": "expense"},
    {"name": "Hóa đơn & Tiện ích", "type": "expense"},
    {"name": "Mua sắm & Đồ dùng", "type": "expense"},
    {"name": "Giải trí & Sự kiện", "type": "expense"},
    {"name": "Y tế & Sức khỏe", "type": "expense"},
    {"name": "Học tập & Phát triển", "type": "expense"},
    {"name": "Hiếu hỷ & Biếu tặng", "type": "expense"},
    {"name": "Phí tài chính & Trả nợ", "type": "expense"},
    
    # Hạng mục Thu nhập (Income)
    {"name": "Lương", "type": "income"},
    {"name": "Thưởng & Làm thêm", "type": "income"},
    {"name": "Trợ cấp & Bố mẹ gửi", "type": "income"},
    {"name": "Lãi & Hoàn tiền", "type": "income"},
    {"name": "Thu nhập khác", "type": "income"},
]

def init_default_data(db: Session):
    # 1. Tạo User mặc định
    user = db.query(User).filter(User.email == "nhuy.pham@student.hvnh.edu.vn").first()
    if not user:
        user = User(
            email="nhuy.pham@student.hvnh.edu.vn",
            password_hash="hashed_password_demo",
            full_name="Phạm Như Ý",
            monthly_income=10000000.0 # 10 triệu
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 2. Tạo Danh mục mặc định
    for cat_data in DEFAULT_CATEGORIES:
        exists = db.query(Category).filter(
            Category.name == cat_data["name"],
            (Category.user_id == user.id) | (Category.user_id == None)
        ).first()
        if not exists:
            cat = Category(name=cat_data["name"], type=cat_data["type"], user_id=None)
            db.add(cat)

    db.commit()

    # 3. Tạo Mục tiêu tiết kiệm mặc định nếu chưa có
    goal_exists = db.query(SavingGoal).filter(SavingGoal.user_id == user.id).first()
    if not goal_exists:
        goal = SavingGoal(
            user_id=user.id,
            name="Quỹ Tiết Kiệm Mua Laptop Mới",
            target_amount=15000000.0,
            current_amount=3500000.0,
            deadline=datetime.date(2026, 12, 31)
        )
        db.add(goal)
        db.commit()

    return user

def get_default_user(db: Session) -> User:
    user = db.query(User).first()
    if not user:
        user = init_default_data(db)
    return user

def update_user_monthly_income(db: Session, user_id: int, new_income: float) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.monthly_income = new_income
        db.commit()
        db.refresh(user)
    return user

def get_categories(db: Session, user_id: int):
    return db.query(Category).filter(
        (Category.user_id == user_id) | (Category.user_id == None)
    ).all()

def create_category(db: Session, name: str, cat_type: str, user_id: int):
    cat = Category(name=name, type=cat_type, user_id=user_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

def find_or_create_category(db: Session, name: str, cat_type: str, user_id: int) -> Category:
    cat = db.query(Category).filter(
        Category.name.ilike(f"%{name}%"),
        (Category.user_id == user_id) | (Category.user_id == None)
    ).first()
    if not cat:
        cat = Category(name=name, type=cat_type, user_id=user_id)
        db.add(cat)
        db.commit()
        db.refresh(cat)
    return cat

def create_transaction(db: Session, amount: float, category_name: str, trans_type: str, note: str, user_id: int):
    cat = find_or_create_category(db, category_name, trans_type, user_id)
    trans = Transaction(
        user_id=user_id,
        category_id=cat.id,
        amount=amount,
        note=note,
        transaction_date=datetime.date.today()
    )
    db.add(trans)
    db.commit()
    db.refresh(trans)
    return trans

def get_transactions(db: Session, user_id: int, limit: int = 50):
    return db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.id.desc()).limit(limit).all()

def delete_transaction(db: Session, transaction_id: int, user_id: int):
    trans = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user_id).first()
    if trans:
        db.delete(trans)
        db.commit()
        return True
    return False

def get_saving_goals(db: Session, user_id: int):
    return db.query(SavingGoal).filter(SavingGoal.user_id == user_id).all()

def create_saving_goal(db: Session, name: str, target_amount: float, current_amount: float, deadline: datetime.date, user_id: int):
    goal = SavingGoal(
        user_id=user_id,
        name=name,
        target_amount=target_amount,
        current_amount=current_amount,
        deadline=deadline
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal

def get_financial_summary(db: Session, user_id: int) -> FinancialSummary:
    user = db.query(User).filter(User.id == user_id).first()
    monthly_income = user.monthly_income if user else 10000000.0

    transactions = db.query(Transaction).filter(Transaction.user_id == user_id).all()

    total_income = 0.0
    total_expense = 0.0
    cat_totals = {}

    for t in transactions:
        cat_name = t.category.name if t.category else "Khác"
        cat_type = t.category.type if t.category else "expense"
        
        if cat_type == "income":
            total_income += t.amount
        else:
            total_expense += t.amount
        
        cat_totals[cat_name] = cat_totals.get(cat_name, 0.0) + t.amount

    net_balance = (monthly_income + total_income) - total_expense
    budget_remaining = (monthly_income + total_income) - total_expense

    total_all = total_income + total_expense
    if total_all == 0:
        total_all = 1.0

    category_breakdown = [
        {"category": k, "amount": v, "percentage": round((v / total_all * 100), 1)}
        for k, v in cat_totals.items()
    ]

    recent_tx = [
        {
            "id": t.id,
            "amount": t.amount,
            "category": t.category.name if t.category else "Khác",
            "type": t.category.type if t.category else "expense",
            "note": t.note,
            "date": str(t.transaction_date)
        }
        for t in get_transactions(db, user_id, limit=10)
    ]

    goals = [
        {
            "id": g.id,
            "name": g.name,
            "target_amount": g.target_amount,
            "current_amount": g.current_amount,
            "percentage": round((g.current_amount / g.target_amount * 100), 1) if g.target_amount > 0 else 0,
            "deadline": str(g.deadline) if g.deadline else None
        }
        for g in get_saving_goals(db, user_id)
    ]

    return FinancialSummary(
        monthly_income=monthly_income,
        total_income=total_income,
        total_expense=total_expense,
        net_balance=net_balance,
        budget_remaining=budget_remaining,
        category_breakdown=category_breakdown,
        recent_transactions=recent_tx,
        saving_goals=goals
    )

def deposit_saving_goal(db: Session, goal_id: int, amount: float, user_id: int):
    goal = db.query(SavingGoal).filter(SavingGoal.id == goal_id, SavingGoal.user_id == user_id).first()
    if goal:
        goal.current_amount += amount
        db.commit()
        db.refresh(goal)
    return goal

def reset_user_data(db: Session, user_id: int):
    db.query(Transaction).filter(Transaction.user_id == user_id).delete()
    db.query(SavingGoal).filter(SavingGoal.user_id == user_id).delete()
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.monthly_income = 10000000.0
    db.commit()
    init_default_data(db)

def load_demo_transactions(db: Session, user_id: int):
    import random

    reset_user_data(db, user_id)

    demo_templates = [
        # Mẫu 1: Sinh viên K11 CNTT (Thu nhập 12 triệu)
        {
            "monthly_income": 12000000.0,
            "template_name": "Sinh viên K11 CNTT (Thu nhập 12tr)",
            "transactions": [
                {"amount": 1500000.0, "category": "Thưởng & Làm thêm", "type": "income", "note": "Học bổng sinh viên & Làm thêm làm bài"},
                {"amount": 2000000.0, "category": "Hóa đơn & Tiện ích", "type": "expense", "note": "Tiền nhà trọ & điện nước tháng này"},
                {"amount": 300000.0, "category": "Di chuyển & Xe cộ", "type": "expense", "note": "Đổ xăng xe máy & gửi xe trường"},
                {"amount": 2200000.0, "category": "Ăn uống", "type": "expense", "note": "Cơm sinh hoạt & cafe học nhóm"},
                {"amount": 850000.0, "category": "Mua sắm & Đồ dùng", "type": "expense", "note": "Mua chuột máy tính & tai nghe học online"},
                {"amount": 450000.0, "category": "Học tập & Phát triển", "type": "expense", "note": "Mua sách Kỹ nghệ phần mềm & giáo trình"},
                {"amount": 350000.0, "category": "Giải trí & Sự kiện", "type": "expense", "note": "Xem phim cuối tuần cùng bạn học"},
            ]
        },
        # Mẫu 2: Người trẻ mới đi làm FinTech (Thu nhập 20 triệu)
        {
            "monthly_income": 20000000.0,
            "template_name": "Người trẻ đi làm FinTech (Thu nhập 20tr)",
            "transactions": [
                {"amount": 3500000.0, "category": "Thưởng & Làm thêm", "type": "income", "note": "Thưởng KPI Sprint & Dự án Freelance"},
                {"amount": 3500000.0, "category": "Hóa đơn & Tiện ích", "type": "expense", "note": "Tiền thuê chung cư mini & Internet 4G"},
                {"amount": 800000.0, "category": "Di chuyển & Xe cộ", "type": "expense", "note": "Đổ xăng & Grabcar đi gặp đối tác"},
                {"amount": 4200000.0, "category": "Ăn uống", "type": "expense", "note": "Ăn trưa văn phòng, ăn tối & trà sữa"},
                {"amount": 2500000.0, "category": "Mua sắm & Đồ dùng", "type": "expense", "note": "Mua trang phục công sở & mỹ phẩm"},
                {"amount": 1200000.0, "category": "Giải trí & Sự kiện", "type": "expense", "note": "Đi chill cuối tuần & hát karaoke"},
                {"amount": 600000.0, "category": "Y tế & Sức khỏe", "type": "expense", "note": "Đăng ký thẻ tập Gym & mua Vitamin"},
            ]
        },
        # Mẫu 3: Sinh viên xa nhà nhận trợ cấp (Thu nhập 8 triệu)
        {
            "monthly_income": 5000000.0,
            "template_name": "Sinh viên xa nhà (Trợ cấp & Part-time 8tr)",
            "transactions": [
                {"amount": 3000000.0, "category": "Trợ cấp & Bố mẹ gửi", "type": "income", "note": "Tiền làm thêm quán cafe & bố mẹ hỗ trợ"},
                {"amount": 1800000.0, "category": "Hóa đơn & Tiện ích", "type": "expense", "note": "Tiền ký túc xá & đóng tiền điện"},
                {"amount": 250000.0, "category": "Di chuyển & Xe cộ", "type": "expense", "note": "Vé xe bus tháng & nạp thẻ xe điện"},
                {"amount": 1900000.0, "category": "Ăn uống", "type": "expense", "note": "Đi chợ tự nấu ăn & ăn sáng"},
                {"amount": 400000.0, "category": "Mua sắm & Đồ dùng", "type": "expense", "note": "Mua văn phòng phẩm & vở viết"},
                {"amount": 300000.0, "category": "Giải trí & Sự kiện", "type": "expense", "note": "Sinh nhật bạn cùng lớp K11"},
            ]
        },
        # Mẫu 4: Chuyên viên Công nghệ Phần mềm (Thu nhập 35 triệu)
        {
            "monthly_income": 35000000.0,
            "template_name": "Chuyên viên CNPM (Thu nhập 35tr)",
            "transactions": [
                {"amount": 5000000.0, "category": "Thưởng & Làm thêm", "type": "income", "note": "Dự án gia công phần mềm ngoài giờ"},
                {"amount": 5000000.0, "category": "Phí tài chính & Trả nợ", "type": "expense", "note": "Trả góp Macbook Pro M5"},
                {"amount": 4000000.0, "category": "Hóa đơn & Tiện ích", "type": "expense", "note": "Tiền thuê nhà & phí dịch vụ tòa nhà"},
                {"amount": 6000000.0, "category": "Ăn uống", "type": "expense", "note": "Ăn uống nhà hàng & gặp đối tác"},
                {"amount": 3000000.0, "category": "Mua sắm & Đồ dùng", "type": "expense", "note": "Mua màn hình máy tính 4K chuyên đồ họa"},
                {"amount": 1500000.0, "category": "Y tế & Sức khỏe", "type": "expense", "note": "Khám răng định kỳ & mua bảo hiểm"},
                {"amount": 2000000.0, "category": "Học tập & Phát triển", "type": "expense", "note": "Mua khóa học AI AWS & Google Cloud"},
            ]
        },
        # Mẫu 5: Cân đối tài chính tích lũy mua Laptop (Thu nhập 15 triệu)
        {
            "monthly_income": 15000000.0,
            "template_name": "Chi tiêu tối ưu tích lũy (Thu nhập 15tr)",
            "transactions": [
                {"amount": 1000000.0, "category": "Thưởng & Làm thêm", "type": "income", "note": "Tiền thưởng chuyên cần & làm thêm"},
                {"amount": 2200000.0, "category": "Hóa đơn & Tiện ích", "type": "expense", "note": "Tiền nhà & tiền điện nước"},
                {"amount": 400000.0, "category": "Di chuyển & Xe cộ", "type": "expense", "note": "Đổ xăng xe máy sinh hoạt"},
                {"amount": 2800000.0, "category": "Ăn uống", "type": "expense", "note": "Tiền ăn 30 ngày tự nấu ăn"},
                {"amount": 700000.0, "category": "Mua sắm & Đồ dùng", "type": "expense", "note": "Đồ dùng cá nhân thiết yếu"},
                {"amount": 500000.0, "category": "Hiếu hỷ & Biếu tặng", "type": "expense", "note": "Mừng sinh nhật bạn thân"},
            ]
        }
    ]

    # Chọn ngẫu nhiên 1 trong 5 mẫu
    selected = random.choice(demo_templates)

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.monthly_income = selected["monthly_income"]
        db.commit()

    for item in selected["transactions"]:
        create_transaction(
            db=db,
            amount=item["amount"],
            category_name=item["category"],
            trans_type=item["type"],
            note=item["note"],
            user_id=user_id
        )

    return selected["template_name"]


def get_or_create_conversation(db: Session, user_id: int, conversation_id: int = None) -> Conversation:
    if conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == user_id).first()
        if conv:
            return conv
    
    conv = Conversation(user_id=user_id, title="Hội thoại tư vấn tài chính")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def save_chat_history(db: Session, user_id: int, conversation_id: int, user_msg: str, bot_msg: str, latency_ms: int = 0, status: str = "success"):
    conv = get_or_create_conversation(db, user_id, conversation_id)
    
    m1 = Message(conversation_id=conv.id, sender="user", content=user_msg)
    m2 = Message(conversation_id=conv.id, sender="bot", content=bot_msg)
    db.add(m1)
    db.add(m2)

    log = AILog(conversation_id=conv.id, prompt_tokens=len(user_msg.split()), response_tokens=len(bot_msg.split()), latency_ms=latency_ms, status=status)
    db.add(log)
    db.commit()
    return conv.id
