"""
Initialize database with admin users and schools
"""

import sys
import os
import bcrypt
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.dirname(__file__))

from models import Base, School, User, RoleEnum, Friendship, ChatSession, Message
import datetime

# Database file in parent directory
DATABASE_PATH = os.path.join(parent_dir, 'madrasti.db')
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Create engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def init_database():
    """Initialize database with default data"""
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✓ تم إنشاء جميع الجداول")
    
    # Session
    db = SessionLocal()
    
    try:
        # Check if admin user exists
        admin_user = db.query(User).filter(User.email == "admin@madrasti.com").first()
        
        if not admin_user:
            # Create admin user
            admin_user = User(
                school_id=1,
                email="admin@madrasti.com",
                full_name="Administrator",
                password_hash=hash_password(os.getenv("LAUNCH_SUPER_ADMIN_PASSWORD", "")),
                role=RoleEnum.ADMIN,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("✓ تم إنشاء حساب الإدارة")
            print("   البريد الإلكتروني: admin@madrasti.com")
            print("   كلمة المرور: من ملف .env")
        else:
            print("✓ حساب الإدارة موجود بالفعل")

        # تأكد من وجود مدرسة رسمية بدلاً من المدرسة التجريبية القديمة
        default_school = db.query(School).filter(School.code == "RMTHA-B-2601").first()
        if not default_school:
            default_school = School(
                name="مدرسة الرمثا الثانوية للبنين",
                code="RMTHA-B-2601",
                status="active"
            )
            db.add(default_school)
            db.commit()
            db.refresh(default_school)
            print("✓ تم إنشاء مدرسة الرمثا الثانوية للبنين (RMTHA-B-2601)")
        else:
            print("✓ مدرسة الرمثا الثانوية للبنين (RMTHA-B-2601) موجودة بالفعل")

        # حساب معلم تجريبي مرتبط بالمدرسة الرسمية
        teacher_user = db.query(User).filter(User.email == "teacher@rmtha2601.com").first()
        if not teacher_user:
            teacher_user = User(
                school_id=default_school.id,
                email="teacher@rmtha2601.com",
                full_name="معلم تجريبي",
                password_hash=hash_password(os.getenv("LAUNCH_SUPER_ADMIN_PASSWORD", "")),
                role=RoleEnum.TEACHER,
                is_active=True
            )
            db.add(teacher_user)
            db.commit()
            print("✓ تم إنشاء حساب معلم تجريبي لمدرسة RMTHA-B-2601")
            print("   البريد الإلكتروني: teacher@rmtha2601.com")
            print("   كلمة المرور: من ملف .env")
        else:
            print("✓ حساب معلم تجريبي لمدرسة RMTHA-B-2601 موجود بالفعل")
    
    except Exception as e:
        print(f"✗ خطأ: {str(e)}")
        db.rollback()
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 جاري تهيئة قاعدة البيانات...")
    init_database()
    print("\n✅ تم إكمال تهيئة قاعدة البيانات")
