from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from typing import List, Optional
from datetime import datetime, timedelta

from .database import get_db, User, ChatSession, Message, ReadReceipt # Assuming User model is in database.py
from .schemas import ( # Define these Pydantic schemas in a separate schemas.py if not already present
    ChatMessageCreate, ChatMessageUpdate, ChatSessionMute, 
    UserPublic, MessageResponse, ChatSessionResponse, ChatSessionListResponse, 
    UserStatus, UserOnlineStatus, MessageReadReceipt, 
    MessageEditResponse, MessageDeleteResponse
)
from .auth import get_current_user # Assuming auth.py has get_current_user

# --- Helper Functions (similar to previous version, adjust as needed) ---

def get_or_create_chat_session(db: Session, user_a_id: int, user_b_id: int) -> ChatSession:
    session_obj = db.query(ChatSession).filter(
        or_(
            and_(ChatSession.starter_id == user_a_id, ChatSession.joiner_id == user_b_id),
            and_(ChatSession.starter_id == user_b_id, ChatSession.joiner_id == user_a_id)
        )
    ).first()

    if not session_obj:
        session_obj = ChatSession(starter_id=user_a_id, joiner_id=user_b_id)
        db.add(session_obj)
        db.commit()
        db.refresh(session_obj)
    return session_obj

# NOTE: Friendship/Blocking logic removed for brevity as per new instructions.
# You might need to re-implement if external checks are required. For now, 
# we're assuming any two users can chat if a session is created.

# --- Chat Routers ---

router = APIRouter()

@router.get("/chat/sessions", response_model=ChatSessionListResponse)
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(
        or_(ChatSession.starter_id == current_user.id, ChatSession.joiner_id == current_user.id)
    ).order_by(desc(ChatSession.updated_at)).all()

    result = []
    for session_obj in sessions:
        partner_id = session_obj.joiner_id if session_obj.starter_id == current_user.id else session_obj.starter_id
        partner = db.query(User).filter(User.id == partner_id, User.is_active == True).first()
        if not partner:
            continue

        # Fetch last message and last read message for the session
        last_message = db.query(Message).filter(Message.session_id == session_obj.id, Message.is_deleted == False).order_by(desc(Message.id)).first()
        
        last_read_by_me = db.query(ReadReceipt).filter(
            ReadReceipt.session_id == session_obj.id,
            ReadReceipt.user_id == current_user.id
        ).order_by(desc(ReadReceipt.message_id)).first()

        unread_count = 0
        if last_message and last_read_by_me:
            unread_count = db.query(Message).filter(
                Message.session_id == session_obj.id,
                Message.id > last_read_by_me.message_id,
                Message.sender_id != current_user.id, # Only count unread from partner
                Message.is_deleted == False
            ).count()
        elif last_message and not last_read_by_me:
            unread_count = db.query(Message).filter(
                Message.session_id == session_obj.id,
                Message.sender_id != current_user.id, # All messages from partner are unread
                Message.is_deleted == False
            ).count()
        
        is_muted = session_obj.is_muted_by_starter if session_obj.starter_id == current_user.id else session_obj.is_muted_by_joiner

        result.append(ChatSessionResponse(
            session_id=session_obj.id,
            partner_id=partner.id,
            partner_name=partner.full_name,
            partner_profile_image=partner.profile_image,
            partner_role_label=partner.role_label or partner.role.value,
            last_message_content=last_message.content if last_message else None,
            last_message_at=last_message.sent_at if last_message else None,
            is_muted=is_muted,
            unread_count=unread_count
        ))

    return ChatSessionListResponse(sessions=result)


@router.post("/chat/sessions/with/{user_id}", response_model=ChatSessionResponse)
async def get_or_create_chat_with_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="لا يمكن فتح دردشة مع نفسك")

    partner = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not partner:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    session_obj = get_or_create_chat_session(db, current_user.id, user_id)
    db.commit()
    db.refresh(session_obj)

    is_muted = session_obj.is_muted_by_starter if session_obj.starter_id == current_user.id else session_obj.is_muted_by_joiner

    return ChatSessionResponse(
        session_id=session_obj.id,
        partner_id=partner.id,
        partner_name=partner.full_name,
        partner_profile_image=partner.profile_image,
        partner_role_label=partner.role_label or partner.role.value,
        last_message_content=None, # New session has no last message initially
        last_message_at=None,
        is_muted=is_muted,
        unread_count=0
    )


@router.get("/chat/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_chat_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    mark_read: bool = True # New parameter to control read receipt creation
):
    session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="جلسة الدردشة غير موجودة")

    if current_user.id not in (session_obj.starter_id, session_obj.joiner_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح")
    
    # Mark all messages in this session as read by current_user
    if mark_read:
        latest_message_id = db.query(Message.id).filter(Message.session_id == session_id).order_by(desc(Message.id)).scalar()
        if latest_message_id:
            read_receipt = db.query(ReadReceipt).filter(
                ReadReceipt.user_id == current_user.id,
                ReadReceipt.session_id == session_id
            ).first()
            if read_receipt:
                read_receipt.message_id = latest_message_id
                read_receipt.read_at = datetime.utcnow()
            else:
                read_receipt = ReadReceipt(
                    user_id=current_user.id,
                    session_id=session_id,
                    message_id=latest_message_id
                )
                db.add(read_receipt)
            db.commit()

    messages_query = db.query(Message).options(joinedload(Message.read_receipts)).filter(
        Message.session_id == session_id,
        Message.is_deleted == False
    ).order_by(Message.id.asc())
    
    messages = messages_query.all()
    
    response_messages = []
    for m in messages:
        is_read = any(rr.user_id == current_user.id for rr in m.read_receipts)
        partner_read = False
        if current_user.id == session_obj.starter_id:
            partner_id = session_obj.joiner_id
        else:
            partner_id = session_obj.starter_id
        
        partner_latest_read_receipt = db.query(ReadReceipt).filter(
            ReadReceipt.user_id == partner_id,
            ReadReceipt.session_id == session_id
        ).order_by(desc(ReadReceipt.message_id)).first()

        if partner_latest_read_receipt and m.id <= partner_latest_read_receipt.message_id:
            partner_read = True
        
        response_messages.append(MessageResponse(
            id=m.id,
            session_id=m.session_id,
            sender_id=m.sender_id,
            content=m.content,
            sent_at=m.sent_at,
            edited_at=m.edited_at,
            is_read=is_read, # Indicates if *current user* has read this message
            partner_read=partner_read # Indicates if *partner* has read this message
        ))

    return response_messages


@router.post("/chat/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_chat_message(
    session_id: int,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="جلسة الدردشة غير موجودة")

    if current_user.id not in (session_obj.starter_id, session_obj.joiner_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح")

    content = (message_data.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="نص الرسالة مطلوب")

    message = Message(session_id=session_obj.id, sender_id=current_user.id, content=content)
    session_obj.updated_at = datetime.utcnow() # Update session timestamp
    db.add(message)
    db.commit()
    db.refresh(message)

    # Automatically mark sent message as read by sender
    read_receipt = db.query(ReadReceipt).filter(
        ReadReceipt.user_id == current_user.id,
        ReadReceipt.session_id == session_id
    ).first()
    if read_receipt:
        read_receipt.message_id = message.id
        read_receipt.read_at = datetime.utcnow()
    else:
        read_receipt = ReadReceipt(
            user_id=current_user.id,
            session_id=session_id,
            message_id=message.id
        )
        db.add(read_receipt)
    db.commit()

    return MessageResponse(
        id=message.id,
        session_id=message.session_id,
        sender_id=message.sender_id,
        content=message.content,
        sent_at=message.sent_at,
        edited_at=message.edited_at,
        is_read=True, # Sender always reads their own message
        partner_read=False # Partner hasn't read it yet
    )

@router.put("/chat/messages/{message_id}", response_model=MessageEditResponse)
async def edit_chat_message(
    message_id: int,
    message_data: ChatMessageCreate, # Re-using for content field
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    message = db.query(Message).filter(Message.id == message_id, Message.is_deleted == False).first()
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح لك بتعديل هذه الرسالة")
    
    message.content = (message_data.content or "").strip()
    message.edited_at = datetime.utcnow()
    db.commit()
    db.refresh(message)

    return MessageEditResponse(
        id=message.id,
        new_content=message.content,
        edited_at=message.edited_at
    )

@router.delete("/chat/messages/{message_id}", response_model=MessageDeleteResponse)
async def delete_chat_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    message = db.query(Message).filter(Message.id == message_id, Message.is_deleted == False).first()
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح لك بحذف هذه الرسالة")
    
    # Soft delete
    message.is_deleted = True
    message.content = "[تم حذف الرسالة]"
    message.edited_at = datetime.utcnow()
    db.commit()
    db.refresh(message)

    return MessageDeleteResponse(
        id=message.id,
        message="تم حذف الرسالة"
    )

@router.post("/chat/sessions/{session_id}/mute", response_model=ChatSessionResponse)
async def mute_chat_session(
    session_id: int,
    mute_data: ChatSessionMute,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="جلسة الدردشة غير موجودة")
    
    if session_obj.starter_id == current_user.id:
        session_obj.is_muted_by_starter = mute_data.is_muted
    elif session_obj.joiner_id == current_user.id:
        session_obj.is_muted_by_joiner = mute_data.is_muted
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح")
    
    db.commit()
    db.refresh(session_obj)

    partner_id = session_obj.joiner_id if session_obj.starter_id == current_user.id else session_obj.starter_id
    partner = db.query(User).filter(User.id == partner_id).first()

    return ChatSessionResponse(
        session_id=session_obj.id,
        partner_id=partner.id,
        partner_name=partner.full_name,
        partner_profile_image=partner.profile_image,
        partner_role_label=partner.role_label or partner.role.value,
        last_message_content=None, # Not relevant for mute response
        last_message_at=None,
        is_muted=mute_data.is_muted,
        unread_count=0 # Not relevant for mute response
    )

@router.delete("/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="جلسة الدردشة غير موجودة")
    
    if current_user.id not in (session_obj.starter_id, session_obj.joiner_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح")
    
    # Delete all messages and read receipts associated with the session
    db.query(Message).filter(Message.session_id == session_id).delete()
    db.query(ReadReceipt).filter(ReadReceipt.session_id == session_id).delete()

    db.delete(session_obj)
    db.commit()
    
    return

# --- User Presence/Status Routers ---

last_seen_cache = {}
ONLINE_THRESHOLD_SECONDS = 300 # 5 minutes

@router.post("/users/status/online")
async def set_online_status(current_user: User = Depends(get_current_user)):
    last_seen_cache[current_user.id] = datetime.utcnow()
    return {"message": "Online status updated"}

@router.get("/users/{user_id}/status", response_model=UserStatus)
async def get_user_status(
    user_id: int,
    current_user: User = Depends(get_current_user) # Ensure user is authenticated
):
    last_seen = last_seen_cache.get(user_id)
    if last_seen and (datetime.utcnow() - last_seen) < timedelta(seconds=ONLINE_THRESHOLD_SECONDS):
        return UserStatus(is_online=True, last_seen_at=None, status_text="متصل الآن")
    
    # If not online, get last seen from user's last message or session update (more persistent)
    # This is a simplified approach. A real system might track explicit logins/logouts.
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj: # Handle case where user does not exist
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    latest_activity = None

    # Check last message sent by user
    last_sent_message = db.query(Message).filter(Message.sender_id == user_id).order_by(desc(Message.sent_at)).first()
    if last_sent_message: 
        latest_activity = last_sent_message.sent_at

    # Check last session updated by user (as starter or joiner)
    last_session_update = db.query(ChatSession).filter(
        or_(ChatSession.starter_id == user_id, ChatSession.joiner_id == user_id)
    ).order_by(desc(ChatSession.updated_at)).first()

    if last_session_update:
        if latest_activity:
            latest_activity = max(latest_activity, last_session_update.updated_at)
        else:
            latest_activity = last_session_update.updated_at

    if latest_activity:
        # For simplicity, if activity is within last 24 hours, show 'today', else show date
        if (datetime.utcnow() - latest_activity).total_seconds() < 86400: # 24 hours
            return UserStatus(
                is_online=False,
                last_seen_at=latest_activity,
                status_text=f"آخر ظهور اليوم عند {latest_activity.strftime('%H:%M')}"
            )
        else:
            return UserStatus(
                is_online=False,
                last_seen_at=latest_activity,
                status_text=f"آخر ظهور في {latest_activity.strftime('%Y-%m-%d')}" # Or format as needed
            )
    
    return UserStatus(is_online=False, last_seen_at=None, status_text="غير متاح")

@router.get("/users/status/batch", response_model=List[UserOnlineStatus])
async def get_batch_user_status(
    user_ids: str, # Comma separated user IDs
    current_user: User = Depends(get_current_user) # Ensure user is authenticated
):
    ids = [int(i) for i in user_ids.split(',') if i.strip().isdigit()]
    statuses = []
    for user_id in ids:
        last_seen = last_seen_cache.get(user_id)
        is_online = bool(last_seen and (datetime.utcnow() - last_seen) < timedelta(seconds=ONLINE_THRESHOLD_SECONDS))
        statuses.append(UserOnlineStatus(user_id=user_id, is_online=is_online))
    return statuses
