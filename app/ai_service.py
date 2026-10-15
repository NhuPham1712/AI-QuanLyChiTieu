import datetime
import json
import re
import time
from typing import Tuple, List, Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session
from app.config import settings
from app import crud
from app.crud import get_financial_summary
from app.schemas import ExtractedTransaction

def parse_saving_goal_intent(text: str) -> Optional[Dict[str, Any]]:
    """Tự động bóc tách ý định lập mục tiêu tiết kiệm mới từ câu nói của người dùng"""
    text_lower = text.lower()
    
    # Phải chứa từ khóa liên quan tới tiết kiệm / kế hoạch / quỹ / tích lũy / mua / sắm
    if not any(kw in text_lower for kw in ["tiết kiệm", "kế hoạch", "quỹ", "tích lũy", "mua", "sắm"]):
        return None

    # Bắt số tiền và đơn vị
    num_match = re.search(r'(\d+(?:\.\d+)?)\s*(k|nghìn|ngàn|tr|triệu|đ|đồng|vnđ)\b', text_lower, re.IGNORECASE)
    if not num_match:
        return None

    raw_num = float(num_match.group(1))
    unit = num_match.group(2).lower()
    
    target_amount = raw_num
    if unit in ["k", "nghìn", "ngàn"]:
        target_amount = raw_num * 1000
    elif unit in ["tr", "triệu"]:
        target_amount = raw_num * 1000000

    if target_amount <= 0:
        return None

    # Trích xuất tên món đồ cần mua / tiết kiệm
    item_match = re.search(r'(?:mua|sắm|tiết kiệm|kế hoạch)\s+(?:cho|để)?\s*([a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]{2,30}?)(?=\s+\d|\s*http|\s*$)', text_lower, re.IGNORECASE)
    
    name = "Mục tiêu mới"
    if item_match:
        extracted = item_match.group(1).strip().title()
        extracted = re.sub(r'^(Kế Hoạch|Tiết Kiệm|Tư Vấn|Cần|Muốn|Để)\s+', '', extracted, flags=re.IGNORECASE).strip()
        if extracted:
            name = extracted if extracted.lower().startswith("mua") else f"Mua {extracted}"

    return {"name": name, "target_amount": target_amount}

SYSTEM_PROMPT = """
Bạn là UniBOT - Chuyên gia tư vấn Quản lý Tài chính Cá nhân và Lập kế hoạch Tiết kiệm thông minh, nghiêm túc và an toàn.
Dành cho người dùng: Phạm Như Ý (Sinh viên/Người trẻ).

NGUYÊN TẮC HÀNG RÀO BẢO VỆ (GUARDRAILS & ANTI-HALLUCINATION):
1. NGUYÊN TẮC AN TOÀN TÀI CHÍNH (QUAN TRỌNG NHẤT):
   - Tuyệt đối KHÔNG cung cấp lời khuyên hoặc hướng dẫn tham gia đầu tư tài chính mạo hiểm, đánh coin/tiền điện tử, giao dịch margin, vay nợ lãi cao hoặc cá cược.
   - Nếu người dùng đặt câu hỏi về các lĩnh vực rủi ro này, hãy TỪ CHỐI LỊCH SỰ và khuyên người dùng tập trung giữ an toàn tài chính & quỹ tiết kiệm khẩn cấp.

2. NGUYÊN TẮC BÓC TÁCH GIAO DỊCH (OUTPUT JSON):
   - Nếu câu nói chứa thông tin thu/chi (ví dụ: 'ăn phở 40k', 'đổ xăng 50 nghìn', 'lương 10tr'), hãy bóc tách chính xác các khoản giao dịch.
   - Quy đổi đơn vị tiền tệ: 1k = 1.000, 1tr = 1.000.000 (Ví dụ: 40k -> 40000; 650k -> 650000; 10tr -> 10000000).
   - Định dạng khối JSON trong câu trả lời theo cú pháp:
     ```json
     {
       "transactions": [
         {"amount": 50000, "category": "Di chuyển", "type": "expense", "note": "Đổ xăng"},
         {"amount": 650000, "category": "Hóa đơn & Tiện ích", "type": "expense", "note": "Đóng tiền điện"}
       ]
     }
     ```

3. NGUYÊN TẮC CHÍNH XÁC DỮ LIỆU:
   - Dựa trên dữ liệu tài chính thực tế được cung cấp trong ngữ cảnh DB để trả lời. Không tự ý bịa đặt số liệu tài chính không có thật.
   - Nếu dữ liệu trống hoặc thiếu thông tin, hãy hỏi lại người dùng hoặc thông báo rõ ràng.
"""

def parse_transactions_from_text(text: str) -> List[ExtractedTransaction]:
    """Bóc tách giao dịch từ phản hồi AI hoặc dùng quy tắc Regex thông minh"""
    transactions = []
    text_lower = text.lower()
    
    # BỎ QUA NẾU ĐÂY LÀ YÊU CẦU TƯ VẤN LẬP KẾ HOẠCH TIẾT KIỆM (KHÔNG PHẢI GIAO DỊCH CHI TIÊU THỰC TẾ)
    if any(kw in text_lower for kw in ["kế hoạch tiết kiệm", "tư vấn tiết kiệm", "lập kế hoạch", "tư vấn lập", "mục tiêu tiết kiệm"]):
        return []
    
    # 1. Tìm chuỗi JSON trong phản hồi
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if not json_match:
        json_match = re.search(r'(\{[\s\S]*"transactions"[\s\S]*\})', text)

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            for item in data.get("transactions", []):
                transactions.append(ExtractedTransaction(
                    amount=float(item.get("amount", 0)),
                    category=item.get("category", "Khác"),
                    type=item.get("type", "expense"),
                    note=item.get("note", "Ghi chép tự động")
                ))
            if transactions:
                return transactions
        except Exception:
            pass

    # 2. Quy tắc Regex thông minh: Bắt số tiền ĐI KÈM ĐƠN VỊ TIỀN TỆ (k, nghìn, ngàn, tr, triệu, đ, đồng, vnđ)
    # Loại bỏ các số đứng đơn lẻ như "M5", "iPhone 15", "Lớp 12"
    pattern = r'(\d+(?:\.\d+)?)\s*(k|nghìn|ngàn|tr|triệu|đ|đồng|vnđ)\b'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))

    if not matches:
        return transactions

    text_lower = text.lower()

    for m in matches:
        raw_num = float(m.group(1))
        unit = m.group(2).lower()

        # Tính toán chính xác số tiền
        amount = raw_num
        if unit in ["k", "nghìn", "ngàn"]:
            amount = raw_num * 1000
        elif unit in ["tr", "triệu"]:
            amount = raw_num * 1000000

        # Phân loại danh mục thông minh dựa vào từ khóa trong câu
        cat = "Khác"
        trans_type = "expense"

        if any(kw in text_lower for kw in ["đổ xăng", "xăng", "xe", "grab", "be", "taxi", "bus", "xe ôm", "gửi xe", "sửa xe", "vé xe"]):
            cat = "Di chuyển & Xe cộ"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["tiền điện", "tiền nước", "hóa đơn", "wifi", "mạng", "tiền nhà", "tiền trọ", "4g", "nạp thẻ"]):
            cat = "Hóa đơn & Tiện ích"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["mua", "macbook", "iphone", "laptop", "điện thoại", "máy tính", "quần áo", "giày", "mỹ phẩm", "túi xách"]):
            cat = "Mua sắm & Đồ dùng"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["thuốc", "khám", "bệnh", "nha khoa", "gym", "thể thao", "vitamin", "sức khỏe"]):
            cat = "Y tế & Sức khỏe"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["học phí", "sách", "vở", "khóa học", "chứng chỉ", "học tập"]):
            cat = "Học tập & Phát triển"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["xem phim", "cinema", "game", "du lịch", "karaoke", "hẹn hò", "đi chơi", "giải trí"]):
            cat = "Giải trí & Sự kiện"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["mừng cưới", "đám cưới", "sinh nhật", "quà", "biếu", "từ thiện"]):
            cat = "Hiếu hỷ & Biếu tặng"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["trả nợ", "trả góp", "lãi vay", "phí ngân hàng"]):
            cat = "Phí tài chính & Trả nợ"
            trans_type = "expense"
        elif any(kw in text_lower for kw in ["thưởng", "ot", "làm thêm", "freelance", "part-time", "bán đồ"]):
            cat = "Thưởng & Làm thêm"
            trans_type = "income"
        elif any(kw in text_lower for kw in ["trợ cấp", "bố mẹ gửi", "mẹ gửi", "ba gửi", "học bổng"]):
            cat = "Trợ cấp & Bố mẹ gửi"
            trans_type = "income"
        elif any(kw in text_lower for kw in ["lương", "thu nhập"]):
            cat = "Lương"
            trans_type = "income"
        elif any(kw in text_lower for kw in ["ăn", "cơm", "phở", "bún", "lẩu", "nướng", "uống", "cafe", "cà phê", "trà sữa", "nhậu"]):
            cat = "Ăn uống"
            trans_type = "expense"

        # Trích xuất ghi chú từ câu
        note = text.strip()
        if len(matches) > 1:
            # Nếu có nhiều giao dịch trong 1 câu, cắt câu theo khoảng
            start_pos = max(0, m.start() - 25)
            end_pos = min(len(text), m.end() + 15)
            note = text[start_pos:end_pos].strip()

        transactions.append(ExtractedTransaction(
            amount=amount,
            category=cat,
            type=trans_type,
            note=note
        ))

    return transactions




def check_guardrails(user_message: str) -> Tuple[bool, str]:
    """Kiểm tra hàng rào bảo vệ (Guardrails) chống rủi ro tài chính & ngoài phạm vi"""
    msg_lower = user_message.lower()

    # Rủi ro 1: Đầu tư mạo hiểm, coin, margin, chứng khoán phái sinh, vay nóng
    risky_keywords = ["margin", "coin x5", "x5 tài khoản", "crypto", "tiền ảo", "đánh coin", "vay nóng", "vay nặng lãi", "quyền chọn", "tài xỉu", "cá cược"]
    for kw in risky_keywords:
        if kw in msg_lower:
            return True, (
                "⚠️ **CẢNH BÁO AN TOÀN TÀI CHÍNH (GUARDRAIL TRIGGERED)**:\n\n"
                "Tôi là Trợ lý Quản lý Tài chính Cá nhân An toàn. Hệ thống **từ chối** cung cấp hướng dẫn hoặc lời khuyên liên quan đến đầu tư mạo hiểm, tiền ảo, giao dịch margin hay các hình thức rủi ro cao.\n\n"
                "💡 *Lời khuyên an toàn*: Để bảo vệ tài sản, bạn nên duy trì **Quỹ dự phòng khẩn cấp** (từ 3 - 6 tháng chi tiêu) và gửi tiết kiệm ngân hàng uy tín trước khi cân nhắc bất kỳ kênh đầu tư nào khác."
            )

    # Rủi ro 2: Câu hỏi hoàn toàn ngoài phạm vi (Out of Scope)
    out_of_scope_keywords = ["đạo hàm", "bài toán lớp 12", "hóa học", "vật lý", "lịch sử thế giới", "viết bài văn", "code python cho game"]
    for kw in out_of_scope_keywords:
        if kw in msg_lower:
            return True, (
                "ℹ️ **THÔNG BÁO NGOÀI PHẠM VI (OUT OF SCOPE)**:\n\n"
                "Tôi là Trợ lý AI chuyên trách về **Quản lý Tài chính Cá nhân & Lập kế hoạch Tiết kiệm**.\n"
                "Tôi không thể hỗ trợ giải các bài tập hoặc câu hỏi ngoài lĩnh vực thu chi tài chính. Bạn vui lòng đặt câu hỏi liên quan đến ghi chép thu chi, phân tích ngân sách hoặc mục tiêu tiết kiệm nhé!"
            )

    return False, ""


async def process_chat(db: Session, user_id: int, user_message: str) -> Dict[str, Any]:
    """Hàm xử lý hội thoại chính với cơ chế Routing & Fallback theo đúng 8 bước Logic của thầy PGS.TS. Ngô Tứ Thành"""
    start_time = time.time()
    
    # Bước 1: Tiếp nhận câu hỏi
    # Bước 2: SYSTEM/LOCAL - Kiểm tra Guardrails & câu hỏi về hệ thống UniBOT
    triggered, response_text = check_guardrails(user_message)
    if triggered:
        latency = int((time.time() - start_time) * 1000)
        return {
            "reply": response_text,
            "parsed_transactions": [],
            "source": "SYSTEM/LOCAL",
            "confidence": 0.99,
            "debug_log": "Hàng rào bảo vệ (Guardrails) hoặc quy tắc SYSTEM phát hiện câu hỏi đặc biệt.",
            "latency_ms": latency,
            "guardrails_triggered": True
        }

    # Bước 3: Chuẩn hóa & Tìm Knowledge Base / Lịch sử giao dịch DB
    # Tự động phát hiện ý định lập mục tiêu tiết kiệm
    goal_intent = parse_saving_goal_intent(user_message)

    # Kiểm tra nếu người dùng khai báo thu nhập / lương (VD: "Thu nhập tháng này của tôi 50tr", "Lương 20 triệu")
    income_match = re.search(r'(?:thu nhập|lương|lương cố định)\s*(?:hàng tháng|tháng này|tháng)?\s*[\w\s]*?\s*(\d+(?:\.\d+)?)\s*(k|nghìn|ngàn|tr|triệu)', user_message, re.IGNORECASE)
    if income_match:
        try:
            raw_num = float(income_match.group(1))
            unit = (income_match.group(2) or "").lower()
            new_inc = raw_num
            if unit in ["k", "nghìn", "ngàn"]:
                new_inc *= 1000
            elif unit in ["tr", "triệu"]:
                new_inc *= 1000000
            
            if new_inc > 0:
                crud.update_user_monthly_income(db, user_id, new_inc)
        except Exception as e:
            print(f"Lỗi cập nhật thu nhập: {e}")

    # Lấy summary MỚI NHẤT sau khi đã cập nhật thu nhập vào DB
    summary = get_financial_summary(db, user_id)
    financial_context = f"""
NGỮ CẢNH TÀI CHÍNH THỰC TẾ CỦA NGƯỜI DÙNG:
- Thu nhập cố định hàng tháng: {summary.monthly_income:,.0f} VNĐ
- Tổng thu trong tháng: {summary.total_income:,.0f} VNĐ
- Tổng chi trong tháng: {summary.total_expense:,.0f} VNĐ
- Số dư hiện tại: {summary.net_balance:,.0f} VNĐ
- Ngân sách chi tiêu còn lại: {summary.budget_remaining:,.0f} VNĐ
- Cơ cấu chi tiêu theo danh mục: {json.dumps(summary.category_breakdown, ensure_ascii=False)}
- Mục tiêu tiết kiệm hiện tại: {json.dumps(summary.saving_goals, ensure_ascii=False)}
- Lịch sử giao dịch gần đây: {json.dumps(summary.recent_transactions, ensure_ascii=False)}
"""

    prompt = f"{SYSTEM_PROMPT}\n\n{financial_context}\n\nNgười dùng nhắn: \"{user_message}\"\n\nTrả lời:"

    reply_text = ""
    source = "INTERNAL"
    confidence = 0.95
    debug_log = ""

    # Bước 4 & 5: Gọi AI đã chọn (Gemini API)
    if settings.GEMINI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        reply_text = candidates[0]["content"]["parts"][0]["text"]
                        source = "GEMINI_AI"
                        confidence = 0.960
                        debug_log = "Đã gửi sang Gemini API (gemini-1.5-flash) thành công kèm ngữ cảnh DB."
        except Exception as e:
            print(f"Gemini API Error: {e}")

    # Bước 6: AI Lỗi -> Auto Failover sang OpenAI ChatGPT API
    if not reply_text and settings.OPENAI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT + "\n" + financial_context},
                        {"role": "user", "content": user_message}
                    ]
                }
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    reply_text = data["choices"][0]["message"]["content"]
                    source = "OPENAI_AI"
                    confidence = 0.935
                    debug_log = "Gemini API không khả dụng -> Auto-Failover thành công sang OpenAI ChatGPT."
        except Exception as e:
            print(f"OpenAI API Error: {e}")

    # Bước 7 & Fallback: Nếu không có API Key hoặc cả 2 AI đều lỗi -> Dùng Fallback Rule Engine
    if not reply_text:
        source = "FALLBACK"
        confidence = 0.171
        debug_log = "Cả Gemini và ChatGPT/OpenAI đều chưa cấu hình hoặc không khả dụng -> Dùng engine Fallback nội bộ."
        parsed_tx = parse_transactions_from_text(user_message)
        
        if parsed_tx:
            confidence = 0.880
            source = "INTERNAL"
            debug_log = "Đủ bằng chứng giao dịch trong câu nói -> Trả lời INTERNAL & bóc tách dữ liệu."
            details = []
            for t in parsed_tx:
                details.append(f"- **{t.note}**: {t.amount:,.0f} VNĐ ({t.category})")
            
            tx_json_str = json.dumps({"transactions": [t.dict() for t in parsed_tx]}, ensure_ascii=False)
            
            reply_text = (
                f"✅ **Đã nhận diện {len(parsed_tx)} giao dịch**:\n" +
                "\n".join(details) + "\n\n" +
                f"Hệ thống đã chuẩn hóa số tiền và tự động lưu vào Sổ Giao Dịch & Cập nhật Biểu đồ.\n\n" +
                f"```json\n{tx_json_str}\n```"
            )
        elif "thu nhập" in user_message.lower() or "lương" in user_message.lower():
            confidence = 0.950
            source = "INTERNAL"
            debug_log = "Cập nhật thu nhập thành công trong CSDL -> Trả lời INTERNAL."
            reply_text = (
                f"✅ **Đã cập nhật Thu nhập cố định hàng tháng thành công**!\n\n"
                f"- **Thu nhập cố định mới**: {summary.monthly_income:,.0f} VNĐ/tháng\n"
                f"- **Số dư khả dụng mới**: **{summary.net_balance:,.0f} VNĐ**\n"
                f"- **Ngân sách chi tiêu còn lại**: **{summary.budget_remaining:,.0f} VNĐ**\n\n"
                f"Hệ thống đã tự động lưu khoản thu nhập này vào **Sổ Giao Dịch** và cập nhật **Biểu Đồ Tài Chính**!"
            )
        elif goal_intent:
            confidence = 0.950
            source = "INTERNAL"
            debug_log = "Nhận diện ý định tư vấn lập kế hoạch tiết kiệm -> Tự động tính toán quy tắc 50/30/20 & tạo mục tiêu."
            target = goal_intent["target_amount"]
            name = goal_intent["name"]
            monthly_save_20 = summary.monthly_income * 0.2
            months_needed = int(target / monthly_save_20) if monthly_save_20 > 0 else 12
            
            reply_text = (
                f"🎯 **Tư vấn Kế hoạch Tiết kiệm cho mục tiêu \"{name}\" ({target:,.0f} VNĐ)**:\n\n"
                f"Dựa trên thu nhập hàng tháng **{summary.monthly_income:,.0f} VNĐ** của bạn, áp dụng quy tắc **50/30/20**:\n"
                f"- **20% Quỹ tiết kiệm hàng tháng**: **{monthly_save_20:,.0f} VNĐ/tháng**.\n"
                f"- **Thời gian tích lũy dự kiến**: Khoảng **{months_needed} tháng** trích lập liên tục.\n"
                f"- **Lời khuyên tối ưu**: Nếu bạn dành thêm từ khoản thặng dư thu chi tháng này ({max(0, summary.total_income - summary.total_expense):,.0f} VNĐ), bạn có thể hoàn thành mục tiêu chỉ trong **{max(1, int(months_needed * 0.7))} tháng**!\n\n"
                f"✨ *Hệ thống đã tự động khởi tạo **\"{name}\"** ({target:,.0f} VNĐ) vào khung MỤC TIÊU TIẾT KIỆM bên góc phải cho bạn!*"
            )
        elif "tiết kiệm" in user_message.lower() or "du lịch" in user_message.lower():
            reply_text = (
                f"💡 **Tư vấn lập kế hoạch tiết kiệm**:\n"
                f"Áp dụng quy tắc **50/30/20** dựa trên thu nhập {summary.monthly_income:,.0f} VNĐ/tháng của bạn:\n"
                f"- **50% Nhu cầu thiết yếu** (Ăn uống, ở, đi lại): {summary.monthly_income * 0.5:,.0f} VNĐ\n"
                f"- **30% Chi tiêu cá nhân** (Giải trí, mua sắm): {summary.monthly_income * 0.3:,.0f} VNĐ\n"
                f"- **20% Quỹ tiết kiệm & Dự phòng**: {summary.monthly_income * 0.2:,.0f} VNĐ\n\n"
                f"Hiện tại mục tiêu *'{summary.saving_goals[0]['name'] if summary.saving_goals else 'Tiết kiệm'}'* của bạn đã đạt {summary.saving_goals[0]['percentage'] if summary.saving_goals else 0}%."
            )
        elif "tháng trước" in user_message.lower() or "dữ liệu" in user_message.lower() or "chi nhiều nhất" in user_message.lower():
            reply_text = (
                f"📊 **Báo cáo dữ liệu tài chính cá nhân**:\n"
                f"Hiện tại trong tháng này, bạn đã ghi nhận tổng thu {summary.total_income:,.0f} VNĐ và tổng chi {summary.total_expense:,.0f} VNĐ.\n"
                f"Số dư khả dụng hiện tại là: **{summary.net_balance:,.0f} VNĐ**.\n"
                f"Nếu cần ghi chép thêm giao dịch, hãy nhắn cho tôi ví dụ: *'Trưa nay ăn cơm hết 40k'*."
            )
        else:
            reply_text = (
                f"Chào bạn! Tôi là UniBOT. Tôi có thể trả lời từ Tập dữ liệu tài chính cá nhân; nếu câu hỏi nằm ngoài tài liệu, tôi sẽ chuyển sang AI đã chọn (Gemini / ChatGPT)."
            )

    # 8. Tự động kiểm tra & tạo Mục tiêu tiết kiệm mới trong CSDL nếu chưa có
    goal_intent = parse_saving_goal_intent(user_message)
    if goal_intent:
        existing_goals = crud.get_saving_goals(db, user_id)
        goal_exists = any(
            goal_intent["name"].lower() in g.name.lower() or g.name.lower() in goal_intent["name"].lower() 
            for g in existing_goals
        )
        if not goal_exists:
            crud.create_saving_goal(
                db=db,
                name=goal_intent["name"],
                target_amount=goal_intent["target_amount"],
                current_amount=0.0,
                deadline=datetime.date.today() + datetime.timedelta(days=180),
                user_id=user_id
            )
            notice = f"\n\n🎯 **TỰ ĐỘNG TẠO MỤC TIÊU TIẾT KIỆM MỚI**:\nĐã khởi tạo **\"{goal_intent['name']}\"** (Mục tiêu: **{goal_intent['target_amount']:,.0f} VNĐ**) vào danh sách *MỤC TIÊU TIẾT KIỆM* ở góc phải!"
            if notice not in reply_text and "Hệ thống đã tự động" not in reply_text and "Hệ thống đã tự động khởi tạo" not in reply_text:
                reply_text += notice

    # Bóc tách giao dịch từ tin nhắn người dùng (Chỉ bóc tách khi không phải câu lập mục tiêu tiết kiệm)
    if goal_intent:
        parsed_transactions = []
    else:
        parsed_transactions = parse_transactions_from_text(user_message)

    latency = int((time.time() - start_time) * 1000)

    return {
        "reply": reply_text,
        "parsed_transactions": parsed_transactions,
        "source": source,
        "confidence": confidence,
        "debug_log": debug_log,
        "latency_ms": latency,
        "guardrails_triggered": False
    }



async def test_gemini_connection() -> Dict[str, Any]:
    """Hàm kiểm tra kết nối Gemini API"""
    if not settings.GEMINI_API_KEY:
        return {"status": "error", "message": "Chưa cấu hình GEMINI_API_KEY trong file .env"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": "Hello"}]}]}
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                return {"status": "ok", "message": "Kết nối Gemini API thành công! Model: gemini-1.5-flash"}
            else:
                return {"status": "error", "message": f"Mã lỗi Gemini API HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Ngoại lệ kết nối Gemini API: {str(e)}"}


async def test_openai_connection() -> Dict[str, Any]:
    """Hàm kiểm tra kết nối ChatGPT OpenAI API"""
    if not settings.OPENAI_API_KEY:
        return {"status": "error", "message": "Chưa cấu hình OPENAI_API_KEY trong file .env"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return {"status": "ok", "message": "Kết nối OpenAI ChatGPT API thành công!"}
            else:
                return {"status": "error", "message": f"Mã lỗi OpenAI API HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Ngoại lệ kết nối OpenAI API: {str(e)}"}
