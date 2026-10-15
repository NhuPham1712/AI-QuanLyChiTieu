from pydantic import BaseModel
from typing import List, Optional
import datetime

class CategoryBase(BaseModel):
    name: str
    type: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    user_id: Optional[int] = None
    class Config:
        from_attributes = True


class TransactionBase(BaseModel):
    category_id: Optional[int] = None
    amount: float
    note: Optional[str] = None
    transaction_date: Optional[datetime.date] = None

class TransactionCreate(TransactionBase):
    category_name: Optional[str] = None
    type: Optional[str] = "expense"

class TransactionResponse(TransactionBase):
    id: int
    user_id: int
    category_name: Optional[str] = None
    type: Optional[str] = "expense"
    class Config:
        from_attributes = True


class SavingGoalCreate(BaseModel):
    name: str
    target_amount: float
    current_amount: Optional[float] = 0.0
    deadline: Optional[datetime.date] = None

class SavingGoalResponse(SavingGoalCreate):
    id: int
    user_id: int
    class Config:
        from_attributes = True


class ChatMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class ExtractedTransaction(BaseModel):
    amount: float
    category: str
    type: str # 'income' hoặc 'expense'
    note: str


class ChatMessageResponse(BaseModel):
    conversation_id: int
    reply: str
    parsed_transactions: List[ExtractedTransaction] = []
    source: str # 'INTERNAL/DB', 'SYSTEM/LOCAL', 'GEMINI_AI', 'OPENAI_AI', 'FALLBACK'
    confidence: float = 0.95
    debug_log: str = ""
    latency_ms: int = 0
    guardrails_triggered: bool = False


class FinancialSummary(BaseModel):
    monthly_income: float
    total_income: float
    total_expense: float
    net_balance: float
    budget_remaining: float
    category_breakdown: List[dict]
    recent_transactions: List[dict]
    saving_goals: List[dict]
