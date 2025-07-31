#Created pratik soni 31-07-25
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import  numpy as np

import os
from sqlalchemy import create_engine, text,Column,Integer, String,Date,Text,LargeBinary,or_,Time,DateTime
from sqlalchemy.orm import declarative_base,sessionmaker
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError, ProgrammingError, DataError
import datetime
import threading

# Global Variables
captured_img_path = "captured.jpg"
showing_webcam = False
image_captured = False
ImageSQL = None
cap = None
date_format = None
validation_job = None  # Global or class-level variable
date_format = None
error_shown = False     # Prevent repeated errors


# Load environment variables
load_dotenv()

# TiDB config
host = os.getenv("TIDB_HOST")
port = os.getenv("TIDB_PORT")
user = os.getenv("TIDB_USER")
password = os.getenv("TIDB_PASSWORD")
db_patient = os.getenv("TIDB_DB")
ssl_ca = os.getenv("TIDB_SSL_CA")

Base = declarative_base()
def get_session(db_name):
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?ssl_ca={ssl_ca}"
    engine = create_engine(url, echo=False)
    Session = sessionmaker(bind=engine)
    return Session(),engine


# Define ORM model
class Hospital2(Base):
    __tablename__ = "hospital_name"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    def __repr__(self):
        return (f"<Hospital(id={self.id}, name={self.name}>")
        
class Hospital(Base):
    __tablename__ = "hospital_name"
    __table_args__ = {'extend_existing': True}  # <- Add this line
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    
class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)  # ← Required primary key
    # ⏰ Added fields
    date_added = Column(Date, default=datetime.date.today)
    time_added = Column(Time, default=datetime.datetime.now().time)
    
    full_name = Column(String(50))
    dob = Column(Date)
    gender = Column(String(10))
    aadhar = Column(String(12), unique=True)
    phone = Column(String(15))
    aabha_no = Column(String(15))
    state = Column(String(100))
    address = Column(Text)
    bed_number = Column(String(50))
    patient_id = Column(String(15), unique=True)
    hospital_name = Column(String(50))
    image = Column(LargeBinary)
    additional_info = Column(String(120))
    
    
def init_tables(engine):
    Base.metadata.create_all(engine)

# Add a user
def add_hospital(name):
    session, engine = get_session("hospital")
    init_tables(engine)
    existing_user = session.query(Hospital).filter_by(name=name).first()
    if existing_user:
        print(f"⚠️ Hospital '{name}' already exists: {existing_user}")
    else:
        hospital = Hospital(name=name)
        session.add(hospital)
        session.commit()
        print(f"➕ Added hospital: {hospital}")
        refresh_hospital_list()  # <- Refresh the combobox values
    session.close()
    
def fetch_hospital_names():
    session, engine = get_session("hospital")
    init_tables(engine)
    hospital_list = session.query(Hospital.name).all()
    session.close()
    return [h[0] for h in hospital_list] + ["Other"]
    

def refresh_hospital_list():
    updated_list = fetch_hospital_names()
    hospital_name_entry.config(values=updated_list)


def add_patient(patient_data):
    session, engine = get_session("hospital")
    init_tables(engine)
    # Correct query using filter + or_
    existing = session.query(Patient).filter(
        or_(
            Patient.patient_id == patient_data["patient_id"],
            Patient.aadhar == patient_data["aadhar"]
        )
    ).first()
    if existing:
        # Find out which field(s) are duplicated
        duplicate_fields = []
        if existing.patient_id == patient_data["patient_id"]:
            duplicate_fields.append(f"Patient ID: {patient_data['patient_id']}")
        if existing.aadhar == patient_data["aadhar"]:
            duplicate_fields.append(f"Aadhar: {patient_data['aadhar']}")

        print(f"⚠️ Duplicate entry found for {', '.join(duplicate_fields)}.")
    else:
        # Add date and time automatically
        patient_data["date_added"] = datetime.date.today()
        patient_data["time_added"] = datetime.datetime.now().time()
        patient = Patient(**patient_data)
        session.add(patient)
        session.commit()
        print(f"✅ Added patient: {patient.full_name}")
    session.close()
    


        
def open_webcam():
    """Opens the webcam and replaces doctor image with live video feed."""
    global cap, showing_webcam, doctor_label
    if showing_webcam:  # If webcam is already open, return
        return

    cap = cv2.VideoCapture(0)  # Open default webcam
    if not cap.isOpened():
        messagebox.showerror("Error", "Could not access the webcam.")
        return

    showing_webcam = True  # Webcam is now active

    def update_frame():
        """Updates the frame from webcam feed."""
        if cap.isOpened() and showing_webcam:
            ret, frame = cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (100, 80))  # Resized to 150x150
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(img)
                doctor_label.config(image=imgtk)
                doctor_label.image = imgtk
                doctor_label.after(10, update_frame)  # Refresh every 10ms

    update_frame()

def capture_image():
    """Captures image from webcam and updates the doctor image."""
    global image_captured, showing_webcam, cap, ImageSQL  # Declare ImageSQL as global

    if cap is not None and cap.isOpened():
        ret, frame = cap.read()
        if ret:
            frame = cv2.resize(frame, (320, 240))  # Resize to match UI
            cv2.imwrite(captured_img_path, frame)  # Save image

            # Convert to NumPy array (for database storage or processing)
            ImageSQL = np.array(frame)

            cap.release()  # Release camera
            showing_webcam = False  # Reset webcam flag
            image_captured = True  # Set flag to indicate image was captured

            # Update the doctor label with the captured image
            update_doctor_image(captured_img_path)
            messagebox.showinfo("Success", "Image captured and saved successfully!")

        else:
            messagebox.showerror("Error", "Failed to capture image.")

def update_doctor_image(image_path):
    """Updates the doctor image label with the given image."""
    global doctor_label

    new_image = Image.open(image_path)
    new_image = new_image.resize((100, 80))  # Ensure it's 150x150
    new_photo = ImageTk.PhotoImage(new_image)

    doctor_label.config(image=new_photo)
    doctor_label.image = new_photo



def create_labeled_field(parent, label_text, row, column, padx=10, pady=5, width=20, 
                         widget_type=tk.Entry, values=None, textvariable=None):
    frame = tk.Frame(parent, bg="#fafafa")
    frame.grid(row=row, column=column, padx=padx, pady=pady, sticky="ew")
    parent.columnconfigure(column, weight=1)

    label = tk.Label(frame, text=label_text, bg="#fafafa", anchor="w",
                     font=("Arial", 12), justify="left")
    label.pack(fill="x")

    if widget_type == ttk.Combobox:
        entry = ttk.Combobox(frame, width=width, values=values, textvariable=textvariable)
    elif widget_type == tk.Text:
        entry = tk.Text(frame, width=width, height=3)
    else:
        entry = widget_type(frame, width=width, textvariable=textvariable)
    
    entry.configure(font=("Arial", 14))
    entry.pack(fill="x", expand=True)
    return entry, frame
        


                
def create_gui():
    global doctor_image, doctor_photo, doctor_label,hospital_name_entry
    root = tk.Tk()
    root.title("Patient Registration")
    root.state("zoomed")
    icon = tk.PhotoImage(file="icon.png")
    root.iconphoto(True, icon)
    
    
    # Make full screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}")

    # Configure root grid
    root.rowconfigure(1, weight=1)  # Content
    root.columnconfigure(0, weight=1)

    # ---------------- Header Frame ----------------
    header_frame = tk.Frame(root, bg="#cce7ff", height=100)
    header_frame.grid(row=0, column=0, sticky="nsew")
    header_frame.columnconfigure((0, 1, 2), weight=1)  # Three columns
    header_frame.rowconfigure(0, weight=1)

    # Header sections
    # Doctor photo (left)
    doctor_image = Image.open("photo_image.png").resize((100, 80))
    doctor_photo = ImageTk.PhotoImage(doctor_image)
    doctor_label = tk.Label(header_frame, image=doctor_photo, bg="#cce7ff", cursor="hand2")
    doctor_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
    doctor_label.bind("<Button-1>", lambda e: capture_image() if showing_webcam else open_webcam())
    doctor_label.bind("<Enter>", lambda e: doctor_label.config(bg="lightblue", relief="solid", bd=2))
    doctor_label.bind("<Leave>", lambda e: doctor_label.config(bg="#cce7ff", relief="flat", bd=0))

    # Title (center)
    title_label = tk.Label(header_frame,text="New Patient Registration\nINDORE",font=("Arial", 22, "bold"),bg="#cce7ff",justify="center")
    title_label.grid(row=0, column=1, sticky="nsew", padx=10)

    # Company logo (right)
    logo_image = Image.open("logo1.png").resize((100, 80))
    logo_photo = ImageTk.PhotoImage(logo_image)
    logo_label = tk.Label(header_frame, image=logo_photo, bg="#cce7ff")
    logo_label.grid(row=0, column=2, padx=20, pady=10, sticky="e")

    # ---------------- Content Frame ----------------
    content_frame = tk.Frame(root, bg="#ffffff")
    content_frame.grid(row=1, column=0, sticky="nsew")
    content_frame.columnconfigure((0, 1), weight=1)
    content_frame.rowconfigure((0, 1), weight=1)

    # Content Blocks
    def create_block(master, text):
        block = tk.LabelFrame(master, text=text,fg="#004d99", bg="#fafafa", font=("Arial", 12,"bold"), labelanchor="n")
        block.columnconfigure((0, 1), weight=1)
        block.rowconfigure((0, 1), weight=1)
        return block

    def save_image_on_button_click():
        # Reset highlight for all fields first
        widgets_to_check = [
            full_name_entry, aadhar_entry, phone_entry, aabha_entry,
            hospital_name_entry, other_name_entry, address_text, 
            patient_id_entry, additional_info_text,dob_entry
        ]
        def highlight_widget_border(frame, error=True):
            frame.config(highlightbackground="red" if error else "#fafafa")
        for widget in widgets_to_check:
            try:
                widget.configure(highlightthickness=0)
            except:
                pass
            
        # Create table if it doesn't exist (can be skipped if created earlier)
        #create_table_if_not_exists()
            
        # Extract values from GUI
        a = full_name_entry.get()
        if not a:
            full_name_entry.config(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            full_name_entry.focus_set()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Full_Name")
            return
        global date_format

        text = dob_entry.get().strip()
    
        if not text or len(text) != 10:
            dob_entry.config(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            dob_entry.focus()
            messagebox.showerror("Error", "Date is missing or invalid format!")
            return
        try:
            parts = text.split("/")
            if len(parts) != 3:
                raise ValueError("Date must be in DD/MM/YYYY format.")
            day, month, year = map(int, parts)
            if not (1 <= day <= 31 and 1 <= month <= 12):
                raise ValueError("Invalid day or month range.")
            b = f"{year:04d}-{month:02d}-{day:02d}"  # Reversed format
            print("Formatted date:", b)
            
        except Exception as e:
            dob_entry.config(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            dob_entry.focus()
            messagebox.showerror("Error", f"Invalid date format: {e}")
            return
        

        c = gender_combobox.get()
        if not c or c == "Select gender":
            highlight_widget_border(gender_frame, error=True)
            gender_combobox.focus()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Gender")
            return

        d = aadhar_var.get()
        if not d or len(d) != 12:
            aadhar_entry.configure(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            aadhar_entry.focus()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Aadhar No.")
            return

        e = phone_var.get().strip()
        if not e or len(e) != 10:
            phone_entry.configure(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            phone_entry.focus()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Phone No.")
            return

        f = aabha_entry.get()
        if not f or len(f) != 12:
            aabha_entry.configure(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            aabha_entry.focus()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Aabha No.")
            return

        g = state_combobox.get()
        if not g or g == "Select State":
            state_combobox.configure(style="Red.TCombobox")
            state_combobox.focus()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : State")
            return

        h = address_text.get("1.0", "end-1c")
        if not h:
            address_text.configure(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            address_text.focus()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Address")
            return

        i = bed_number_combobox.get()
        if not i :
            bed_number_combobox.configure(style="Red.TCombobox")
            bed_number_combobox.focus()        
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Bed No.")
            return

        j = patient_id_entry.get().strip()
        if not j:
            patient_id_entry.configure(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            patient_id_entry.focus()        
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Patient ID")
            return
        j = j.zfill(12)

        m = hospital_name_entry.get()
        if not m or m == "Select Hospital name":
            hospital_name_entry.configure(style="Red.TCombobox")
            hospital_name_entry.focus()
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Hospital name.")
            return

        k = other_name_entry.get() if m == "Other" else m
        # Get the actual hospital name
        if m == "Other":
            try:
                # Use appropriate method based on widget type
                k = other_name_entry.get().strip()  # for tk.Entry
            except TypeError:
                k = other_name_entry.get("1.0", "end-1c").strip()  # for tk.Text

            if not k:
                other_name_entry.configure(highlightbackground="red", highlightcolor="red", highlightthickness=2)
                other_name_entry.focus()
                messagebox.showerror("Missing Fields", "Please fill in the following fields: Enter Hospital Name.")
                return
        else:
            k = m  # Use selected hospital name
                
        l = additional_info_text.get("1.0", "end-1c")
        if not l:
            additional_info_text.configure(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            additional_info_text.focus()        
            messagebox.showerror("Missing Fields", "Please fill in the following fields : Additional Infomation")
            return

        if 'ImageSQL' not in globals() or ImageSQL is None:
            doctor_label.config(bg="red", relief="solid", bd=2)           
            messagebox.showerror("Missing Fields", "Please provide an image before saving.")
            return

        success, buffer = cv2.imencode('.jpg', ImageSQL)
        if not success:
            messagebox.showerror("Missing Fields", "Invalid image format. Please provide a valid image.")
            return
        image_binary = buffer.tobytes()
        # Insert hospital name if "Other"
        if m == "Other" and k:
            add_hospital(k)
        
        # Create dictionary for patient record
        patient_data = {
            "full_name": a,
            "dob": b,
            "gender": c,
            "aadhar": d,
            "phone": e,
            "aabha_no": f,
            "state": g,
            "address": h,
            "bed_number": i,
            "patient_id": j,
            "hospital_name": k,
            "additional_info": l,
            "image": image_binary,
        }
        
        try:
            add_patient(patient_data)
            messagebox.showinfo("Success", "{}\nData saved successfully!".format(patient_data['full_name']))
            clear_form()
        except IntegrityError as err:
            #session.rollback()
            messagebox.showerror("Integrity Error", f"Duplicate or constraint error: {str(err)}")

        except ProgrammingError as err:
            #session.rollback()
            messagebox.showerror("SQL Programming Error", str(err))

        except DataError as err:
            #session.rollback()
            messagebox.showerror("Data Error", f"Invalid data (e.g. too long): {str(err)}")

        except Exception as err:
            #session.rollback()
            messagebox.showerror("Error", f"Unexpected error: {str(err)}")

        
    
    personal_info = create_block(content_frame, "Personal Information")
    personal_info.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    contact_info = create_block(content_frame, "Contact Information")
    contact_info.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

    hospital_info = create_block(content_frame, "Hospital Information")
    hospital_info.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    additional_info = create_block(content_frame, "Additional Information")
    additional_info.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
    
    
    #Start---------------- Personal Frame ----------------
    # --- FULL NAME ---
    full_name_entry,_ = create_labeled_field(personal_info, "Full Name:", 0, 0, padx=60, pady=20)

    full_name_entry.configure(validate="key", validatecommand=(
        full_name_entry.register(lambda text: all(c.isalpha() or c in {" ", "."} for c in text)), "%P"))



    # --- DATE OF BIRTH ---
    def format_date_old(event):
        global date_format
        text = dob_entry.get().strip()

        if not text:
            return

        text = "".join(c for c in text if c.isdigit() or c == "/")

        if len(text) > 2 and text[2] != "/":
            text = text[:2] + "/" + text[2:]
        if len(text) > 5 and text[5] != "/":
            text = text[:5] + "/" + text[5:]
        text = text[:10]

        parts = text.split("/")
        if len(parts) == 3:
            day, month, year = parts
            if not (day.isdigit() and month.isdigit() and year.isdigit()):
                return
            day, month = int(day), int(month)
            if not (1 <= day <= 31):
                messagebox.showerror("Invalid Date", "Invalid day.")
                return
            if not (1 <= month <= 12):
                messagebox.showerror("Invalid Date", "Invalid month.")
                return

        dob_entry.delete(0, tk.END)
        dob_entry.insert(0, text)

        if len(text) == 10:
            date_format = text
            print("Final Entered Date of Birth:", text)

    
    def format_date_work(event):
        global validation_job
        if validation_job:
            dob_entry.after_cancel(validation_job)
        validation_job = dob_entry.after(500, validate_dob_entry)  # Delay of 500ms

    def validate_dob_entry_working():
        global date_format, error_shown

        text = dob_entry.get().strip()
        if not text:
            return

        # Format slashes
        text = "".join(c for c in text if c.isdigit() or c == "/")
        if len(text) > 2 and text[2] != "/":
            text = text[:2] + "/" + text[2:]
        if len(text) > 5 and text[5] != "/":
            text = text[:5] + "/" + text[5:]
        text = text[:10]

        # Update field once
        dob_entry.delete(0, tk.END)
        dob_entry.insert(0, text)

        # Validate only when fully entered
        if len(text) != 10:
            error_shown = False  # reset if typing
            return

        try:
            day, month, year = map(int, text.split("/"))
            if not (1 <= day <= 31):
                raise ValueError("Invalid day")
            if not (1 <= month <= 12):
                raise ValueError("Invalid month")
            if not (1900 <= year <= 2100):
                raise ValueError("Invalid year")
            date_format = text
            error_shown = False  # Reset error state
            print("Valid Date:", date_format)
        except ValueError as e:
            if not error_shown:
                messagebox.showerror("Invalid Date", str(e))
                error_shown = True
                # Remove only invalid part
                if "day" in str(e).lower():
                    dob_entry.delete(0, tk.END)
                elif "month" in str(e).lower():
                    dob_entry.delete(3, tk.END)
                elif "year" in str(e).lower():
                    dob_entry.delete(6, tk.END)
       

    def format_date(event):
        entry = dob_entry
        text = entry.get().strip()
        cursor_pos = entry.index(tk.INSERT)

        # Allow deletion without interference
        if event.keysym in ['BackSpace', 'Delete']:
            return

        digits = ''.join(c for c in text if c.isdigit())
        day = month = year = ''
        
        # Day
        if len(digits) >= 2:
            day_val = int(digits[:2])
            if 1 <= day_val <= 31:
                day = f"{day_val:02}"
            else:
                day = ''
        elif len(digits) == 1:
            d = int(digits[0])
            if d > 3:
                day = f"0{d}"
            else:
                day = str(d)

        # Month
        if len(digits) >= 4:
            month_val = int(digits[2:4])
            if 1 <= month_val <= 12:
                month = f"{month_val:02}"
            else:
                month = ''
        elif len(digits) >= 3:
            m = int(digits[2])
            if m > 1:
                month = f"0{m}"
            else:
                month = str(m)

        # Year
        if len(digits) > 4:
            year = digits[4:8]


        # Build final formatted text
        formatted = day
        if month:
            formatted += f"/{month}"
        elif len(day) == 2:
            formatted += "/"

        if year:
            formatted += f"/{year}"
        elif len(month) == 2:
            formatted += "/"
            
            
        #print(f"cursor current {cursor_pos} ,{formatted},{len(formatted)}")

        # Replace and restore cursor
        entry.delete(0, tk.END)
        entry.insert(0, formatted)
        try:
            #entry.icursor(min(cursor_pos, len(formatted)))
            entry.icursor(len(formatted))
            
        except:
            pass

    def validate_dob_entry():
        text = dob_entry.get().strip()
        if not text or len(text) != 10:
            dob_entry.config(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            messagebox.showerror("Error", "Date is missing or incomplete!")
            return False

        try:
            day, month, year = map(int, text.split("/"))
            if not (1 <= day <= 31):
                raise ValueError("Invalid day")
            if not (1 <= month <= 12):
                raise ValueError("Invalid month")
            if not (1900 <= year <= 2100):
                raise ValueError("Invalid year")
        except Exception as e:
            dob_entry.config(highlightbackground="red", highlightcolor="red", highlightthickness=2)
            messagebox.showerror("Invalid Date", str(e))
            return False

        dob_entry.config(highlightthickness=0)
        return True

           
    dob_entry,_ = create_labeled_field(personal_info, "Date of Birth(DD/MM/YYYY):", 0, 1, padx=60, pady=20)
    dob_entry.bind("<KeyRelease>", format_date)


    # --- GENDER ---
    gender_combobox, gender_frame = create_labeled_field(personal_info, "Gender:", 1, 0, padx=60, pady=20,
                                           widget_type=ttk.Combobox, values=["Male", "Female", "Other"])
    gender_combobox.set("Select gender")
    gender_combobox.config(state="readonly")


    # --- AADHAR NUMBER ---
    aadhar_var = tk.StringVar()
    aadhar_entry,_ = create_labeled_field(personal_info, "Aadhar Number:", 1, 1, padx=60, pady=20,
                                        textvariable=aadhar_var)
    aadhar_entry.config(validate="key", validatecommand=(
        aadhar_entry.register(lambda P: P.isdigit() and len(P) <= 12 or P == ""), "%P"))
    aadhar_var.trace_add("write", lambda *args: aadhar_var.set(aadhar_var.get()[:12]))    
    
    #End---------------- Personal Frame ----------------
    
    #Start---------------- Contact Frame ----------------
    contact_info.columnconfigure((0, 1), weight=1)
    
    # Phone Number Field
    phone_var = tk.StringVar()
    phone_entry,_ = create_labeled_field(contact_info, "Phone Number:", 0, 0, padx=10, pady=20, width=15, textvariable=phone_var)
    phone_entry.config(validate="key", validatecommand=(
        phone_entry.register(lambda P: P.isdigit() and len(P) <= 10 or P == ""), "%P"))
    phone_var.trace_add("write", lambda *args: phone_var.set(phone_var.get()[:10]))

    aabha_var = tk.StringVar()
    aabha_entry,_ = create_labeled_field(contact_info, "Aabha Number:", 0, 1, padx=10, pady=20, width=25, textvariable=aabha_var)
    aabha_entry.config(validate="key", validatecommand=(
        aabha_entry.register(lambda P: P.isdigit() and len(P) <= 12 or P == ""), "%P"))
    aabha_var.trace_add("write", lambda *args: aabha_var.set(aabha_var.get()[:12]))

   
    states = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
              "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
              "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
              "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
              "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"]

    state_combobox,state_frame = create_labeled_field(contact_info, "State:", 1, 0, padx=10, pady=20,width=30,
                                          widget_type=ttk.Combobox, values=states)
    state_combobox.set("Select State")
    state_combobox.config(state="readonly")
    
    address_frame = tk.Frame(contact_info, bg="#fafafa")
    address_frame.grid(row=1, column=1, padx=10, pady=20, sticky="nsew")
    tk.Label(address_frame, text="Address:", bg="#fafafa", font=("Arial", 12)).pack(anchor="w")
    address_text = tk.Text(address_frame, width=35, height=2, font=("Arial", 12))
    address_text.pack(fill="both", expand=True)
    # Limit to 50 characters
    def limit_address_length(event=None):
        current_text = address_text.get("1.0", "end-1c")
        if len(current_text) > 50:
            address_text.delete("1.0", "end")
            address_text.insert("1.0", current_text[:50])
            messagebox.showwarning("Limit Reached", "Address can be max 50 characters.")

    address_text.bind("<KeyRelease>", limit_address_length)
    
    # Allow Tab to move focus instead of inserting tab character
    def focus_next_widget(event):
        event.widget.tk_focusNext().focus()
        return "break"

    address_text.bind("<Tab>", focus_next_widget)

    
    #End---------------- Contactl Frame ----------------
    
    #Start---------------- Hospital Frame ----------------
    
    # Dummy hospital names list (replace with your dynamic fetch)
    hospital_names = fetch_hospital_names()

    # --- BED NUMBER ---
    bed_number_combobox,bed_frame = create_labeled_field(
        hospital_info, "Bed Number:", 0, 0, padx=50, pady=20, width=25,
        widget_type=ttk.Combobox, values=["1", "2", "3", "4", "5","6","7","8"]
    )
    bed_number_combobox.config(state="readonly")

    # --- PATIENT ID ---
    patient_id_var = tk.StringVar()

    def validate_patient_id_input(P):
        return P.isdigit() and len(P) <= 12 or P == ""

    def format_patient_id(*args):
        patient_id = patient_id_var.get()
        if len(patient_id) == 12:
            patient_id_var.set(patient_id.zfill(12))
        elif len(patient_id) == 0:
            patient_id_var.set("")

    patient_id_var.trace_add("write", format_patient_id)

    patient_id_entry,_ = create_labeled_field(
        hospital_info, "Patient ID:", 0, 1, padx=60, pady=20, width=25, textvariable=patient_id_var
    )
    validate_command = patient_id_entry.register(validate_patient_id_input)
    patient_id_entry.config(validate="key", validatecommand=(validate_command, "%P"))

    # --- HOSPITAL NAME (Combobox) ---
    hospital_name_entry,hospital_frame = create_labeled_field(
        hospital_info, "Hospital Name:", 1, 0, padx=50, pady=20, width=35,
        widget_type=ttk.Combobox, values=hospital_names
    )
    hospital_name_entry.set("Select Hospital name")
    
    hospital_name_entry.config(state="readonly")
    

    # --- OTHER HOSPITAL (disabled by default) ---
    other_name_entry,_ = create_labeled_field(
        hospital_info, "Other Hospital:", 1, 1, padx=60, pady=20, width=35
    )
    other_name_entry.config(state="readonly")

    # Enable "Other Hospital" field only when "Other" is selected
    def on_hospital_select(event):
        selected = hospital_name_entry.get()
        if selected == "Other":
            other_name_entry.config(state="normal")
            
            # Limit to 50 characters
            def limit_address_length(event=None):
                current_text = other_name_entry.get()
                if len(current_text) > 30:
                    other_name_entry.delete(0, tk.END)
                    other_name_entry.insert(0, current_text[:30])
                    messagebox.showwarning("Limit Reached", "other name hospital can be max 30 characters.")

            other_name_entry.bind("<KeyRelease>", limit_address_length)
            
        else:
            other_name_entry.delete(0, tk.END)
            other_name_entry.config(state="readonly")

    hospital_name_entry.bind("<<ComboboxSelected>>", on_hospital_select)
    
    #End---------------- Hospital Frame ----------------
    

    #Start----------------Other Frame ----------------
    
    def limit_character_input(event=None):
        current_text = additional_info_text.get("1.0", tk.END)
        if len(current_text.strip()) > 30:
            additional_info_text.delete("1.0 + 30 chars", tk.END)  # Remove excess
            messagebox.showwarning("Limit Reached", "Maximum 30 characters allowed.")

    # Create label and Text widget inside a frame
    info_frame = tk.Frame(additional_info, bg="#fafafa")
    info_frame.grid(row=0, column=0, padx=50, pady=40, sticky="w")

    tk.Label(info_frame, text="Information:", bg="#fafafa", font=("Arial", 12)).pack(anchor="w")
    additional_info_text = tk.Text(info_frame, width=68, height=5, font=("Arial", 12))
    additional_info_text.pack()

    # Bind key press to character limit function
    additional_info_text.bind("<KeyRelease>", limit_character_input)
    def focus_next_widget(event):
        event.widget.tk_focusNext().focus()
        return "break"

    additional_info_text.bind("<Tab>", focus_next_widget)
    
    #End----------------Other Frame ----------------
    
    
    # ---------------- Footer Frame ----------------
    footer_frame = tk.Frame(root, bg="#cce7ff", height=60)
    footer_frame.grid(row=2, column=0, sticky="nsew")
    footer_frame.columnconfigure(0, weight=1)
    footer_frame.rowconfigure(0, weight=1)
    def clear_form():
        full_name_entry.delete(0, tk.END)
        dob_entry.delete(0, tk.END)
        gender_combobox.set("Select gender")
        aadhar_entry.delete(0, tk.END)
        phone_entry.delete(0, tk.END)
        aabha_entry.delete(0, tk.END)
        state_combobox.set("Select State")
        address_text.delete("1.0", tk.END)  # Fixed here        
        patient_id_entry.delete(0, tk.END)
        hospital_name_entry.set("Select Hospital name")
        other_name_entry.delete(0, tk.END)
        additional_info_text.delete("1.0", tk.END)
        #doctor_label.config(image="", text="")  # Clear preview image if needed
        # Reset image to default
        doctor_image = Image.open("photo_image.png").resize((100, 80))
        doctor_photo = ImageTk.PhotoImage(doctor_image)
        doctor_label.config(image=doctor_photo)
        doctor_label.image = doctor_photo  # 👈 prevent image from being garbage collected
        bed_number_combobox.set("")  # Since it's a ttk.Combobox
        
    # --- Actual backend processing function ---
    def backend_process():
        try:
            # Simulate a long-running operation (e.g., DB save, image write)
            save_image_on_button_click()
        finally:
            # Re-enable button and update text
            submit_button.config(state=tk.NORMAL, text="Submit Patient Information")
            
    # --- When Submit is clicked ---
    def on_submit():              
        submit_button.config(state=tk.DISABLED, text="Processing...")
        threading.Thread(target=backend_process, daemon=True).start()
        
        
    #submit_button = tk.Button(footer_frame, text="Submit Patient Information", font=("Arial", 14,"bold"), bg="#4CAF50", fg="white",command=save_image_on_button_click).grid(row=0, column=0, pady=10)
    # Submit Button
    submit_button = tk.Button(
        footer_frame,
        text="Submit Patient Information",
        font=("Arial", 14, "bold"),
        bg="#4CAF50",
        fg="white",
        command=on_submit
    )
    submit_button.grid(row=0, column=0, pady=10)

    # --- Bind Enter key to the button manually ---
    def on_enter_key(event):
        on_submit()

    # Bind Enter key to the button
    submit_button.bind("<Return>", on_enter_key)

    # Optional: Set focus so it responds to Enter
    submit_button.focus_set()

    def handle_keypress(event):
        # Gender selection
        if gender_combobox.focus_get() == gender_combobox:
            key = event.char.lower()
            if key == "m":
                gender_combobox.set("Male")
            elif key == "f":
                gender_combobox.set("Female")
            elif key == "o":
                gender_combobox.set("Other")

        # State selection (combobox supports auto-complete by default)

        # Bed number selection
        if bed_number_combobox.focus_get() == bed_number_combobox:
            if event.char in "12345678":
                bed_number_combobox.set(event.char)

    # Bind to root window
    root.bind("<Key>", handle_keypress)
    
    
    
    # Fix minimum size to prevent collapse
    root.update_idletasks()
    root.minsize(800, 600)
    root.mainloop()

create_gui()
