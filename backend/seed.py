import os
import json
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure models import uses package path
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)
from models import Base, School, Class, Student


def get_paths():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    db_path = os.path.join(base, "madrasti.db")
    classes_path = os.path.join(base, "data", "classes.json")
    return db_path, classes_path


def seed(db_path, classes_path, school_name, school_code):
    if not os.path.exists(classes_path):
        raise FileNotFoundError(f"classes.json not found at {classes_path}")

    with open(classes_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Backwards-compatible format handling
    if isinstance(data, dict):
        file_school = data.get("school", {})
        file_school_name = file_school.get("name")
        file_school_code = file_school.get("code")
        classes_list = data.get("classes", [])
    else:
        file_school_name = None
        file_school_code = None
        classes_list = data

    # Remove old DB so SQLAlchemy can create fresh schema (option A)
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted existing DB: {db_path}")

    DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)
    print("Created database schema via SQLAlchemy")

    db = SessionLocal()

    # Determine school info
    school_name = school_name or file_school_name or "المدرسة الرئيسية"
    school_code = school_code or file_school_code or "DEFAULT"

    # Create or get school
    school = db.query(School).filter(School.name == school_name, School.code == school_code).first()
    if not school:
        school = School(name=school_name, code=school_code, status="active")
        db.add(school)
        db.commit()
        db.refresh(school)
        print(f"Created school: {school.name} (id={school.id})")
    else:
        print(f"Using existing school: {school.name} (id={school.id})")

    classes_added = 0
    students_added = 0

    for cls in classes_list:
        class_name = cls.get("class_name") or cls.get("name")
        students = cls.get("students", [])

        existing_cls = db.query(Class).filter(Class.school_id == school.id, Class.name == class_name).first()
        if existing_cls:
            class_obj = existing_cls
            print(f"Class exists, skipping creation: {class_name} (id={class_obj.id})")
        else:
            class_obj = Class(school_id=school.id, name=class_name)
            db.add(class_obj)
            db.commit()
            db.refresh(class_obj)
            classes_added += 1
            print(f"Added class: {class_name} (id={class_obj.id})")

        for sname in students:
            sname = sname.strip()
            if not sname:
                continue
            exists = db.query(Student).filter(Student.class_id == class_obj.id, Student.full_name == sname).first()
            if exists:
                continue
            student = Student(class_id=class_obj.id, full_name=sname, is_active=True)
            db.add(student)
            students_added += 1

    db.commit()
    db.close()

    print("\nSeeding complete:")
    print(f"  Classes added: {classes_added}")
    print(f"  Students added: {students_added}")
    print(f"  Database file: {db_path}")


def main():
    db_path, classes_path = get_paths()
    parser = argparse.ArgumentParser(description="Seed madrasti SQLite DB from data/classes.json (SQLAlchemy)")
    parser.add_argument("--school-name", default=None, help="School name to assign classes to")
    parser.add_argument("--school-code", default=None, help="School code")
    args = parser.parse_args()

    seed(db_path, classes_path, args.school_name, args.school_code)


if __name__ == "__main__":
    main()
