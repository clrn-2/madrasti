"""
SQLAlchemy ORM Models for Attendance System
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, Text, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum as python_enum

Base = declarative_base()


class School(Base):
    """School model"""
    __tablename__ = "schools"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)
    status = Column(String(50), default="active")  # "active" or "under_construction"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    classes = relationship("Class", back_populates="school", cascade="all, delete-orphan")
    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    term_settings = relationship("SchoolTermSettings", back_populates="school", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<School(id={self.id}, name={self.name})>"


class Class(Base):
    """Class model"""
    __tablename__ = "classes"
    
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    school = relationship("School", back_populates="classes")
    students = relationship("Student", back_populates="class_obj", cascade="all, delete-orphan")
    attendance_submissions = relationship("AttendanceSubmission", back_populates="class_obj", cascade="all, delete-orphan")
    
    __table_args__ = (
        # Unique constraint to prevent duplicate classes in same school
        {'sqlite_autoincrement': True},
    )
    
    def __repr__(self):
        return f"<Class(id={self.id}, name={self.name}, school_id={self.school_id})>"


class Student(Base):
    """Student model"""
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    class_obj = relationship("Class", back_populates="students")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Student(id={self.id}, name={self.full_name}, class_id={self.class_id})>"


class RoleEnum(python_enum.Enum):
    """User roles"""
    ADMIN = "admin"
    TEACHER = "teacher"
    GUARDIAN = "guardian"


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    public_id = Column(String(5), nullable=True, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(50), nullable=True, unique=True)
    specialization = Column(String(255), nullable=True)
    profile_image = Column(Text, nullable=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.TEACHER)
    role_label = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    is_super_admin = Column(Boolean, default=False)  # Super admin can access all schools
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = Column(DateTime, nullable=True)
    
    # Relationships
    school = relationship("School", back_populates="users")
    attendance_submissions = relationship("AttendanceSubmission", back_populates="submitted_by_user", foreign_keys="AttendanceSubmission.submitted_by")
    attendance_records = relationship("AttendanceRecord", back_populates="created_by_user", foreign_keys="AttendanceRecord.created_by")
    audit_logs = relationship("AuditLog", back_populates="changed_by_user")

    # New relationships for chat and friends
    friendships_sent = relationship("Friendship", foreign_keys="Friendship.sender_id", back_populates="sender", cascade="all, delete-orphan")
    friendships_received = relationship("Friendship", foreign_keys="Friendship.receiver_id", back_populates="receiver", cascade="all, delete-orphan")
    
    chat_sessions_started = relationship("ChatSession", foreign_keys="ChatSession.starter_id", back_populates="starter", cascade="all, delete-orphan")
    chat_sessions_joined = relationship("ChatSession", foreign_keys="ChatSession.joiner_id", back_populates="joiner", cascade="all, delete-orphan")

    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
    password_reset_requests = relationship("PasswordResetRequest", back_populates="user", cascade="all, delete-orphan")
    blocked_users = relationship("UserBlock", foreign_keys="UserBlock.blocker_id", back_populates="blocker", cascade="all, delete-orphan")
    blocked_by_users = relationship("UserBlock", foreign_keys="UserBlock.blocked_id", back_populates="blocked", cascade="all, delete-orphan")
    muted_chat_settings = relationship("ChatMute", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class AttendanceStatusEnum(python_enum.Enum):
    """Attendance status options"""
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"
    LATE = "late"


class AttendanceRecord(Base):
    """Individual attendance record for a student in a session/date"""
    __tablename__ = "attendance_records"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    submission_id = Column(Integer, ForeignKey("attendance_submissions.id"), nullable=False)
    date = Column(Date, nullable=False)
    session_number = Column(Integer, nullable=True)  # 1-7 for per-session, None for full-day
    status = Column(Enum(AttendanceStatusEnum), nullable=False)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="attendance_records")
    submission = relationship("AttendanceSubmission", back_populates="records")
    created_by_user = relationship("User", back_populates="attendance_records", foreign_keys=[created_by])
    audit_logs = relationship("AuditLog", back_populates="record", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AttendanceRecord(id={self.id}, student_id={self.student_id}, status={self.status}, date={self.date})>"


class SubmissionStatusEnum(python_enum.Enum):
    """Submission workflow status"""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class AttendanceSubmission(Base):
    """Submission containing multiple attendance records for a class on a date"""
    __tablename__ = "attendance_submissions"
    
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    date = Column(Date, nullable=False)
    submission_type = Column(String(20), nullable=False)  # "daily" or "per-session"
    num_sessions = Column(Integer, nullable=True)  # For per-session: 1-7, for daily: None
    academic_year = Column(Integer, nullable=False, default=lambda: datetime.utcnow().year)
    term = Column(String(20), nullable=False, default="first")  # first | second
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(SubmissionStatusEnum), default=SubmissionStatusEnum.DRAFT)
    notes = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    purge_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    class_obj = relationship("Class", back_populates="attendance_submissions")
    submitted_by_user = relationship("User", back_populates="attendance_submissions", foreign_keys=[submitted_by])
    records = relationship("AttendanceRecord", back_populates="submission", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AttendanceSubmission(id={self.id}, class_id={self.class_id}, date={self.date}, status={self.status})>"


class SchoolTermSettings(Base):
    """Current academic year and term per school; used to scope attendance/reporting."""
    __tablename__ = "school_term_settings"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, unique=True)
    current_academic_year = Column(Integer, nullable=False)
    current_term = Column(String(20), nullable=False, default="first")
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school = relationship("School", back_populates="term_settings")

    def __repr__(self):
        return f"<SchoolTermSettings(school_id={self.school_id}, year={self.current_academic_year}, term={self.current_term})>"


class AuditLog(Base):
    """Audit log for tracking changes to attendance records"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, ForeignKey("attendance_records.id"), nullable=False)
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=False)
    field_name = Column(String(100), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    record = relationship("AttendanceRecord", back_populates="audit_logs")
    changed_by_user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, record_id={self.record_id}, field={self.field_name})>"


class SchoolApplication(Base):
    """Represents a school's application/request to join the system"""
    __tablename__ = "school_applications"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SchoolApplication(id={self.id}, name={self.name}, status={self.status})>"


class FriendshipStatusEnum(python_enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class Friendship(Base):
    """Represents a friendship request and its status between two users."""
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(FriendshipStatusEnum), default=FriendshipStatusEnum.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="friendships_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="friendships_received")

    def __repr__(self):
        return f"<Friendship(id={self.id}, sender={self.sender_id}, receiver={self.receiver_id}, status={self.status})>"


class ChatSession(Base):
    """Represents a chat session between two users (or potentially more in future)."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True)
    starter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joiner_id = Column(Integer, ForeignKey("users.id"), nullable=False) # The other participant
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    starter = relationship("User", foreign_keys=[starter_id], back_populates="chat_sessions_started")
    joiner = relationship("User", foreign_keys=[joiner_id], back_populates="chat_sessions_joined")
    messages = relationship("Message", back_populates="chat_session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, starter={self.starter_id}, joiner={self.joiner_id})>"


class Message(Base):
    """Represents a single message within a chat session."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)

    chat_session = relationship("ChatSession", back_populates="messages")
    sender = relationship("User", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, sender={self.sender_id}, session={self.session_id})>"


class PasswordResetRequest(Base):
    """One-time password reset request via email link or phone OTP."""
    __tablename__ = "password_reset_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel = Column(String(20), nullable=False)  # email or phone
    token_hash = Column(String(255), nullable=True)
    otp_hash = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="password_reset_requests")

    def __repr__(self):
        return f"<PasswordResetRequest(id={self.id}, user_id={self.user_id}, channel={self.channel})>"


class UserBlock(Base):
    __tablename__ = "user_blocks"

    id = Column(Integer, primary_key=True)
    blocker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    blocked_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    blocker = relationship("User", foreign_keys=[blocker_id], back_populates="blocked_users")
    blocked = relationship("User", foreign_keys=[blocked_id], back_populates="blocked_by_users")


class ChatMute(Base):
    __tablename__ = "chat_mutes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    is_muted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="muted_chat_settings")
    chat_session = relationship("ChatSession")


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(Integer, primary_key=True)
    caller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    callee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(30), default="ringing")  # ringing|answered|rejected|ended|missed
    offer_sdp = Column(Text, nullable=True)
    answer_sdp = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)


class CallIceCandidate(Base):
    __tablename__ = "call_ice_candidates"

    id = Column(Integer, primary_key=True)
    call_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    candidate = Column(Text, nullable=False)
    sdp_mid = Column(String(255), nullable=True)
    sdp_mline_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
