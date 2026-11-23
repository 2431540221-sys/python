"""
Task 5 - bộ lọc an toàn: từ khóa nhạy cảm + câu từ chối chẩn đoán y tế.

Áp dụng ở 2 chỗ:
  1. screen_text(): câu hỏi người dùng nhập. Nếu nhạy cảm thì KHÔNG gửi cho AI, trả lời bằng câu cố định.
  2. sanitize_report(): đầu ra của AI. Câu nào có nội dung chẩn đoán/thuốc thì bị thay bằng câu an toàn.
"""
import re
import unicodedata

DISCLAIMER = (
    "Đây là gợi ý tự theo dõi dựa trên số liệu bạn đã nhập, không phải chẩn đoán hay lời khuyên y tế. "
    "Nếu bạn thấy khó chịu kéo dài, hãy trao đổi với bác sĩ hoặc chuyên gia tâm lý."
)

MEDICAL_REFUSAL = (
    "Mầm không thể chẩn đoán bệnh, đánh giá sức khỏe tâm thần hay tư vấn thuốc. "
    "Nếu bạn lo lắng về sức khỏe, hãy trao đổi với bác sĩ hoặc chuyên gia tâm lý. "
    "Mầm có thể giúp bạn nhìn lại giờ ngủ, tâm trạng và thói quen mà bạn đã ghi lại."
)

CRISIS_RESPONSE = (
    "Mình rất tiếc khi nghe điều này, và cảm ơn bạn đã nói ra. Mầm chỉ là công cụ tự theo dõi nên không đủ để "
    "hỗ trợ lúc này. Nếu bạn đang nghĩ đến việc làm hại bản thân hoặc thấy không an toàn, hãy gọi 115 hoặc đến "
    "cơ sở y tế gần nhất ngay, và nhắn cho một người thân hoặc bạn bè tin cậy để họ ở bên bạn."
)

SUPPORT_CHECK_RESPONSE = (
    "Nghe như bạn đang phải chịu nhiều áp lực. Mầm không thể đánh giá mức độ an toàn qua tin nhắn. "
    "Bạn có đang an toàn ngay lúc này không? Nếu bạn có nguy cơ trước mắt, hãy gọi 115 hoặc đến cơ sở y tế "
    "gần nhất, đồng thời nhờ một người bạn tin cậy ở bên."
)

SAFE_FALLBACK = "Hãy chọn một việc nhỏ, dễ làm và nghỉ ngơi đủ; nếu cần, hãy chia sẻ với người bạn tin tưởng."

# Từ khóa đã bỏ dấu, viết thường. Cụm từ được so khớp theo ranh giới từ.
CRISIS_TERMS = [
    "tu tu", "tu sat", "muon chet", "khong muon song", "ket thuc cuoc song", "ket lieu doi minh",
    "tu lam dau", "tu hai", "tu gay ton thuong", "cat tay", "nhay lau", "treo co", "het muon song",
    "khong con ly do de song", "khong muon tinh day nua", "muon ngu mai mai", "gui loi tam biet",
    "sap bien mat", "gia nhu minh chua tung ton tai", "ket thuc tat ca", "muon tu ket lieu",
    "kill myself", "end my life", "want to die", "self harm",
]
SUPPORT_TERMS = [
    "vo vong", "be tac", "ganh nang", "khong thay loi thoat", "khong con y nghia",
    "khong ai can minh", "khong con muon co gang", "khong muon tiep tuc nua",
    "khong the tiep tuc nua", "khong muon lam phien ai", "gia nhu minh khong ton tai",
    "do vat va neu khong co minh", "se tot hon neu khong co minh",
    "better off without me", "no reason to live", "burden to everyone", "feel like a burden", "cant go on",
    "can't go on", "cant keep going", "can't keep going", "want to disappear",
]
MEDICAL_TERMS = [
    "chan doan", "tram cam", "lo au", "roi loan", "benh tam than", "tam than phan liet", "luong cuc",
    "adhd", "tu ky", "ptsd", "hoang loan", "uong thuoc", "thuoc ngu", "thuoc an than", "thuoc tram cam",
    "ke don", "lieu thuoc", "lieu luong", "dieu tri", "chua benh", "mat ngu kinh nien", "co bi benh",
    "toi bi benh", "benh gi", "xet nghiem",
]


def normalize(text):
    """Chữ thường, bỏ dấu tiếng Việt, gom khoảng trắng."""
    text = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _contains(text, terms):
    plain = normalize(text)
    return any(re.search(rf"\b{re.escape(term)}\b", plain) for term in terms)


def is_crisis(text):
    return _contains(text, CRISIS_TERMS)


def is_medical(text):
    return _contains(text, MEDICAL_TERMS)


def screen_text(text):
    """Phân loại câu người dùng nhập; nội dung cần hỗ trợ được trả lời cục bộ, không gửi tới AI."""
    if is_crisis(text):
        return {"level": "crisis", "reply": CRISIS_RESPONSE}
    if _contains(text, SUPPORT_TERMS):
        return {"level": "support", "reply": SUPPORT_CHECK_RESPONSE}
    if is_medical(text):
        return {"level": "medical", "reply": MEDICAL_REFUSAL}
    return {"level": "ok", "reply": None}


def _clean(text, limit=300):
    return str(text).strip()[:limit]


def sanitize_report(report):
    """Làm sạch đầu ra của AI: bỏ/thay mọi câu có từ khóa chẩn đoán hay thuốc, giới hạn độ dài."""
    flagged = False

    def safe(text):
        nonlocal flagged
        text = _clean(text)
        if is_medical(text) or is_crisis(text):
            flagged = True
            return None
        return text

    summary = safe(report.get("summary", "")) or SAFE_FALLBACK
    result = {"summary": summary}
    for key in ("patterns", "goals", "actions"):
        items = report.get(key) or []
        if not isinstance(items, list):
            items = [items]
        cleaned = [s for s in (safe(i) for i in items[:4]) if s]
        result[key] = cleaned
    if not result["goals"]:
        result["goals"] = [SAFE_FALLBACK]
    result["flagged"] = flagged
    return result
