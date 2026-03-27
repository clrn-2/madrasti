"""
Setup schools and super admin user
"""

from dotenv import load_dotenv
load_dotenv()

import sys
import os
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, School, User, RoleEnum
import bcrypt

# Database setup
DATABASE_URL = "sqlite:///./madrasti.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

db = SessionLocal()

try:
    # المدارس الرسمية الوحيدة المعتمدة + أكواد دائمة وفريدة
    schools_data = [
        {"name": "مدرسة الرمثا الثانوية للبنين", "code": "RMTHA-B-2601", "status": "active"},
        {"name": "مدرسة جمانة للبنات", "code": "JUMANA-G-2602", "status": "active"},
        {"name": "مدرسة الرمثا الثانوية للبنات", "code": "RMTHA-G-2603", "status": "active"},
        {"name": "مدرسة الثروة", "code": "THARWA-2604", "status": "active"},
        {"name": "مدرسة زينب بنت الرسول", "code": "ZAINAB-2605", "status": "active"},
    ]

    target_names = {item["name"] for item in schools_data}
    target_codes = {item["code"] for item in schools_data}

    existing_schools = db.query(School).all()

    # تعطيل أي مدرسة خارج القائمة الرسمية وإلغاء كودها القديم
    for school in existing_schools:
        if school.name not in target_names:
            school.status = "inactive"
            school.code = f"LEGACY-{school.id}-{school.id * 97}"
            print(f"↻ تم تعطيل مدرسة غير معتمدة وإلغاء كودها: {school.name}")

    # إنشاء/تحديث المدارس الرسمية
    for school_data in schools_data:
        existing = db.query(School).filter(School.name == school_data["name"]).first()
        if not existing:
            # تأكد من عدم تكرار الكود على أي سجل سابق
            conflict = db.query(School).filter(School.code == school_data["code"]).first()
            if conflict and conflict.name != school_data["name"]:
                conflict.code = f"LEGACY-{conflict.id}-{conflict.id * 97}"
                conflict.status = "inactive"

            school = School(
                name=school_data["name"],
                code=school_data["code"],
                status=school_data["status"]
            )
            db.add(school)
            print(f"✓ تمت إضافة المدرسة: {school_data['name']}")
        else:
            existing.code = school_data["code"]
            existing.status = school_data["status"]
            print(f"↻ تم تحديث المدرسة: {school_data['name']}")

    db.commit()
    
    # اربط الحسابات بمدرسة الرمثا الثانوية للبنين
    primary_school = db.query(School).filter(School.code == "RMTHA-B-2601").first()
    
    if primary_school:
        existing_admin = db.query(User).filter(User.email == "mfysbw@gmail.com").first()

        if existing_admin:
            existing_admin.school_id = primary_school.id
            existing_admin.password_hash = hash_password(os.getenv("LAUNCH_SUPER_ADMIN_PASSWORD", ""))
            existing_admin.full_name = "مسؤول النظام"
            existing_admin.role = RoleEnum.ADMIN
            existing_admin.is_active = True
            existing_admin.is_super_admin = True
            print("↻ تم تحديث حساب الإدارة الحالي")
        else:
            super_admin = User(
                school_id=primary_school.id,
                email="mfysbw@gmail.com",
                password_hash=hash_password(os.getenv("LAUNCH_SUPER_ADMIN_PASSWORD", "")),
                full_name="مسؤول النظام",
                role=RoleEnum.ADMIN,
                is_active=True,
                is_super_admin=True
            )
            db.add(super_admin)
            print("✓ تم إنشاء حساب الإدارة الجديد")

        db.commit()
        print("\n✓ تم تجهيز حساب الإدارة بنجاح!")
        print(f"  البريد الإلكتروني: mfysbw@gmail.com")
        print(f"  كلمة المرور: من ملف .env")
        print(f"  الصلاحيات: إدارة جميع المدارس")

        # Ensure teacher account exists/updated
        teacher_email = "sosoalzoubi055@gmail.com"
        existing_teacher = db.query(User).filter(User.email == teacher_email).first()
        if existing_teacher:
            existing_teacher.school_id = primary_school.id
            existing_teacher.password_hash = hash_password(os.getenv("LAUNCH_SUPER_ADMIN_PASSWORD", ""))
            existing_teacher.full_name = "معلم النظام"
            existing_teacher.role = RoleEnum.TEACHER
            existing_teacher.is_active = True
            existing_teacher.is_super_admin = False
            print("↻ تم تحديث حساب المعلم الحالي")
        else:
            teacher_user = User(
                school_id=primary_school.id,
                email=teacher_email,
                password_hash=hash_password(os.getenv("LAUNCH_SUPER_ADMIN_PASSWORD", "")),
                full_name="معلم النظام",
                role=RoleEnum.TEACHER,
                is_active=True,
                is_super_admin=False
            )
            db.add(teacher_user)
            print("✓ تم إنشاء حساب المعلم الجديد")

        db.commit()
        print("\n✓ تم تجهيز حساب المعلم بنجاح!")
        print(f"  البريد الإلكتروني: {teacher_email}")
        print(f"  كلمة المرور: من ملف .env")
        print(f"  الصلاحيات: معلم")

    # Display all schools
    print("\n📚 قائمة المدارس:")
    all_schools = db.query(School).order_by(School.id.asc()).all()
    for school in all_schools:
        status_display = "🟢 نشط" if school.status == "active" else "⚪ غير نشط"
        print(f"  • {school.name} ({school.code}) - {status_display}")

    # تحقق إضافي من تفرد الأكواد النشطة
    active_codes = [s.code for s in all_schools if s.status == "active"]
    if len(active_codes) != len(set(active_codes)):
        raise RuntimeError("تم اكتشاف تكرار في أكواد المدارس النشطة")

except Exception as e:
    print(f"❌ خطأ: {e}")
    db.rollback()
finally:
    db.close()
