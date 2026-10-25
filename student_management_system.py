import json
import os

FILE_NAME = "students.json"

# ==================== FILE HANDLING ====================

def load_data():
    """File se purana data load karta hai agar file mojood ho."""
    if not os.path.exists(FILE_NAME):
        return {}  # Agar file nahi hai to empty dictionary
    
    try:
        with open(FILE_NAME, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, IOError):
        return {}

def save_data(students):
    """Data ko JSON file me save karta hai."""
    with open(FILE_NAME, "w") as file:
        json.dump(students, file, indent=4)


# ==================== CRUD OPERATIONS ====================

def add_student(students):
    """1. CREATE: Naya student add karna"""
    roll_no = input("Enter Roll No: ").strip()
    
    if roll_no in students:
        print("Ghalati: Ye Roll No pehle se mojood hai!")
        return

    name = input("Enter Student Name: ").strip()
    if not name:
        print("Ghalati: Naam khali nahi ho sakta.")
        return

    while True:
        try:
            marks = float(input("Enter Marks (0-100): "))
            if 0 <= marks <= 100:
                break
            print("Marks 0 se 100 ke darmiyan hone chahiye.")
        except ValueError:
            print("Ghalati: Marks sirf numbers me hone chahiye.")

    # Dictionary me record save
    students[roll_no] = {
        "name": name,
        "marks": marks
    }
    save_data(students)
    print(f"Student '{name}' kamyabi se add ho gaya aur file me save ho gaya!")


def show_students(students):
    """2. READ: Saare students ki list dekhna"""
    if not students:
        print("Koi student record mojood nahi hai.")
        return

    print("\n" + "=" * 45)
    print(f"{'Roll No':<10} {'Name':<20} {'Marks':<10}")
    print("=" * 45)
    for roll_no, info in students.items():
        print(f"{roll_no:<10} {info['name']:<20} {info['marks']:<10.2f}")
    print("=" * 45)


def find_student(students):
    """2. READ: Kisi aik student ko dhoondna"""
    roll_no = input("Dhoondne ke liye Roll No likhein: ").strip()
    
    if roll_no in students:
        info = students[roll_no]
        print(f"\nRecord Mil Gaya:")
        print(f"Roll No: {roll_no}")
        print(f"Name   : {info['name']}")
        print(f"Marks  : {info['marks']}")
    else:
        print(f"Roll No '{roll_no}' ka koi student nahi mila.")


def update_student(students):
    """3. UPDATE: Purane student ke marks ya naam badalna"""
    roll_no = input("Update karne ke liye Roll No likhein: ").strip()
    
    if roll_no not in students:
        print("Ye Roll No mojood nahi hai.")
        return

    current = students[roll_no]
    print(f"Mojooda data: Naam = {current['name']}, Marks = {current['marks']}")
    
    new_name = input("Naya naam likhein (purana rakhne ke liye Enter dabayein): ").strip()
    if new_name:
        current['name'] = new_name

    new_marks_input = input("Naye marks likhein (purana rakhne ke liye Enter dabayein): ").strip()
    if new_marks_input:
        try:
            new_marks = float(new_marks_input)
            if 0 <= new_marks <= 100:
                current['marks'] = new_marks
            else:
                print("Marks 0-100 nahi the, purane marks hi rahenge.")
        except ValueError:
            print("Ghalat number tha, purane marks hi rahenge.")

    students[roll_no] = current
    save_data(students)
    print("Record update aur save ho gaya!")


def delete_student(students):
    """4. DELETE: Student ko delete karna"""
    roll_no = input("Delete karne ke liye Roll No likhein: ").strip()
    
    if roll_no in students:
        removed_name = students[roll_no]['name']
        del students[roll_no]
        save_data(students)
        print(f"Student '{removed_name}' (Roll No: {roll_no}) ka record delete ho gaya.")
    else:
        print("Ye Roll No mojood nahi hai.")


def calculate_class_average(students):
    """Class ka total average nikalna"""
    if not students:
        print("Data nahi hai, average nahi nikal sakti.")
        return

    total = sum(item['marks'] for item in students.values())
    avg = total / len(students)
    print(f"\nTotal Students: {len(students)}")
    print(f"Class Average: {avg:.2f}")


# ==================== MAIN PROGRAM ====================

def main():
    # Program shuru hote hi purana data load karein
    students = load_data()
    print("Welcome to Student Management System (JSON Enabled)!")

    while True:
        print("\n--- MENU ---")
        print("1. Add Student (Create)")
        print("2. Show All Students (Read)")
        print("3. Find Student (Read)")
        print("4. Update Student (Update)")
        print("5. Delete Student (Delete)")
        print("6. Show Class Average")
        print("7. Exit")
        
        choice = input("Apna intikhab darj karein (1-7): ").strip()
        
        if choice == "1":
            add_student(students)
        elif choice == "2":
            show_students(students)
        elif choice == "3":
            find_student(students)
        elif choice == "4":
            update_student(students)
        elif choice == "5":
            delete_student(students)
        elif choice == "6":
            calculate_class_average(students)
        elif choice == "7":
            print("Khuda Hafiz!")
            break
        else:
            print("Ghalat option, 1 se 7 ke darmiyan number dein.")

if __name__ == "__main__":
    main()