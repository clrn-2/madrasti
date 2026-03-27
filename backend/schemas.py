from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class UserPublic(BaseModel):
    id: int
    full_name: str
    profile_image: Optional[str] = None
    role: str
    role_label: Optional[str] = None
    specialization: Optional[str] = None

    class Config:
        orm_mode = True

class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class ChatMessageUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class MessageResponse(BaseModel):
    id: int
    session_id: int
    sender_id: int
    content: str
    sent_at: datetime
    edited_at: Optional[datetime] = None
    is_read: bool = False # If current user has read this specific message
    partner_read: bool = False # If the partner has read this specific message

    class Config:
        orm_mode = True

class MessageEditResponse(BaseModel):
    id: int
    new_content: str
    edited_at: datetime

class MessageDeleteResponse(BaseModel):
    id: int
    message: str

class ChatSessionMute(BaseModel):
    is_muted: bool

class ChatSessionResponse(BaseModel):
    session_id: int
    partner_id: int
    partner_name: str
    partner_profile_image: Optional[str] = None
    partner_role_label: Optional[str] = None
    last_message_content: Optional[str] = None
    last_message_at: Optional[datetime] = None
    is_muted: bool = False
    unread_count: int = 0

    class Config:
        orm_mode = True

class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionResponse]

class UserStatus(BaseModel):
    is_online: bool
    last_seen_at: Optional[datetime] = None
    status_text: str

class UserOnlineStatus(BaseModel):
    user_id: int
    is_online: bool

class ReadReceiptCreate(BaseModel):
    message_id: int
    session_id: int

class ReadReceiptResponse(BaseModel):
    id: int
    user_id: int
    message_id: int
    session_id: int
    read_at: datetime

    class Config:
        orm_mode = True
