from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_mysqldb import MySQL
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
import random
from dotenv import load_dotenv
import qrcode
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
app.config['MAIL_FROM_NAME'] = os.environ.get('MAIL_FROM_NAME', 'Student Dues')

# ---------------- MYSQL CONFIG ----------------
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'student_dues')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))

clear_db_url = os.environ.get('CLEARDB_DATABASE_URL')
if clear_db_url:
    import urllib.parse
    parsed = urllib.parse.urlparse(clear_db_url)
    app.config['MYSQL_HOST'] = parsed.hostname
    app.config['MYSQL_USER'] = parsed.username
    app.config['MYSQL_PASSWORD'] = parsed.password
    app.config['MYSQL_DB'] = parsed.path.lstrip('/')
    app.config['MYSQL_PORT'] = parsed.port or 3306

mysql = MySQL(app)

# ---------------- UPLOAD FOLDER ----------------
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template('index.html')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['name']
            matric_no = request.form['matric_no']
            email = request.form['email']
            level = request.form['level']
            password = request.form['password']
            hashed_password = generate_password_hash(password)

            image = request.files.get('image')

            if image and image.filename:
                filename = image.filename
                upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(upload_path)
            else:
                filename = ""

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO students(name, matric_no, email, level, password, image)
                VALUES(%s,%s,%s,%s,%s,%s)
            """, (name, matric_no, email, level, hashed_password, filename))

            mysql.connection.commit()
            cur.close()

            return "Registration successful"

        except Exception as e:
            return f"ERROR: {str(e)}"

    return render_template('register.html')


# ---------------- STUDENT LOGIN ----------------
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':

        matric_no = request.form['matric_no']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM students WHERE matric_no=%s", (matric_no,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[5], password):
            session['student_id'] = user[0]
            return redirect(url_for('student_dashboard'))
        else:
            return render_template('student_login.html', error="Invalid matric number or password", matric_no=matric_no)

    return render_template('student_login.html')


@app.route('/student_reset_password', methods=['GET', 'POST'])
def student_reset_password():
    if request.method == 'POST':
        stage = request.form.get('stage', 'request')
        matric_no = request.form.get('matric_no', '').strip()
        email = request.form.get('email', '').strip()

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM students WHERE matric_no=%s AND email=%s", (matric_no, email))
        user = cur.fetchone()

        if not user:
            cur.close()
            return render_template(
                'student_reset_password.html',
                error="No matching student found.",
                matric_no=matric_no,
                email=email,
                verify_stage=False
            )

        if stage == 'request':
            reset_code = str(random.randint(100000, 999999))
            session['reset_matric_no'] = matric_no
            session['reset_email'] = email
            session['reset_code'] = reset_code
            session['reset_user_id'] = user[0]

            email_sent = send_verification_email(email, reset_code)
            info = "A verification code was sent to your email."
            if not email_sent:
                info = f"Email sending is not configured. Use verification code: {reset_code}"

            cur.close()
            return render_template(
                'student_reset_password.html',
                success=info,
                matric_no=matric_no,
                email=email,
                verify_stage=True,
                show_code=not email_sent,
                verification_code=reset_code
            )

        verification_code = request.form.get('verification_code', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not verification_code:
            cur.close()
            return render_template(
                'student_reset_password.html',
                error="Enter the verification code sent to your email.",
                matric_no=matric_no,
                email=email,
                verify_stage=True
            )

        if password != confirm_password:
            cur.close()
            return render_template(
                'student_reset_password.html',
                error="Passwords do not match.",
                matric_no=matric_no,
                email=email,
                verify_stage=True
            )

        if session.get('reset_code') != verification_code or session.get('reset_matric_no') != matric_no or session.get('reset_email') != email:
            cur.close()
            return render_template(
                'student_reset_password.html',
                error="Invalid verification code.",
                matric_no=matric_no,
                email=email,
                verify_stage=True
            )

        cur.execute("UPDATE students SET password=%s WHERE id=%s", (generate_password_hash(password), session['reset_user_id']))
        mysql.connection.commit()
        cur.close()

        session.pop('reset_code', None)
        session.pop('reset_matric_no', None)
        session.pop('reset_email', None)
        session.pop('reset_user_id', None)

        return render_template('student_reset_password.html', success="Password reset successfully. You can now login.")

    return render_template('student_reset_password.html', verify_stage=False)


# ---------------- DASHBOARD ----------------
@app.route('/student_dashboard')
def student_dashboard():

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM students WHERE id=%s", (session['student_id'],))
    user = cur.fetchone()
    cur.close()

    return render_template('student_dashboard.html', user=user)


# ---------------- UPDATE LEVEL ----------------
@app.route('/update_level', methods=['GET', 'POST'])
def update_level():

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    if request.method == 'POST':

        level = request.form['level']

        cur = mysql.connection.cursor()
        cur.execute("UPDATE students SET level=%s WHERE id=%s",
                    (level, session['student_id']))
        mysql.connection.commit()
        cur.close()

        return "Level updated successfully"

    return render_template('update_level.html')


# ---------------- BANK DETAILS ----------------
@app.route('/set_bank', methods=['GET', 'POST'])
def set_bank():

    if request.method == 'POST':

        bank_name = request.form['bank_name']
        account_name = request.form['account_name']
        account_number = request.form['account_number']

        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM bank_details")
        cur.execute("""
            INSERT INTO bank_details(bank_name, account_name, account_number)
            VALUES(%s,%s,%s)
        """, (bank_name, account_name, account_number))

        mysql.connection.commit()
        cur.close()

        return "Bank updated"

    return render_template('set_bank_details.html')


def send_verification_email(recipient_email, code):
    """Send verification code by email if mail settings are configured."""
    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        return False

    message = EmailMessage()
    message['Subject'] = 'Password Reset Verification Code'
    message['From'] = f"{app.config['MAIL_FROM_NAME']} <{app.config['MAIL_DEFAULT_SENDER']}>"
    message['To'] = recipient_email
    message.set_content(
        f"Your password reset verification code is: {code}\n\n" 
        "If you did not request this, please ignore this message."
    )

    try:
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        if app.config['MAIL_USE_TLS']:
            server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(message)
        server.quit()
        return True
    except Exception:
        return False
# ---------------- admin dashboard ----------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html')
# ---------------- view students ----------------

def generate_receipt_pdf(student_id, payment_id, amount, level, receipt_number):
    """Generate a PDF receipt for an approved payment"""
    # Ensure receipts folder exists
    if not os.path.exists('receipts'):
        os.makedirs('receipts')
    
    filename = f"receipt_{receipt_number}.pdf"
    filepath = os.path.join("receipts", filename)
    
    # Get student details
    cur = mysql.connection.cursor()
    cur.execute("SELECT name, matric_no, email FROM students WHERE id=%s", (student_id,))
    student = cur.fetchone()
    cur.close()
    
    # Create PDF
    c = canvas.Canvas(filepath, pagesize=letter)

    # Add logos at the top left and top right
    logo_path = os.path.join('static', 'images')
    nacos_logo_path = os.path.join(logo_path, 'nacos.png')
    plasu_logo_path = os.path.join(logo_path, 'plasu.jpg')

    if os.path.exists(nacos_logo_path):
        c.drawImage(nacos_logo_path, 50, 708, width=140, height=60, preserveAspectRatio=True, mask='auto')
    if os.path.exists(plasu_logo_path):
        c.drawImage(plasu_logo_path, 612 - 50 - 140, 708, width=140, height=60, preserveAspectRatio=True, mask='auto')

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(306, 700, "PAYMENT RECEIPT")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 680, "=" * 100)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 655, "Receipt Details")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 645, f"Receipt Number: {receipt_number}")
    c.drawString(50, 625, f"Date: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    
    c.drawString(50, 595, "=" * 100)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 570, "Student Information")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 545, f"Name: {student[0]}")
    c.drawString(50, 525, f"Matric Number: {student[1]}")
    c.drawString(50, 505, f"Email: {student[2]}")
    
    c.drawString(50, 475, "=" * 100)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 450, "Payment Information")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 425, f"Amount Paid: ₦{float(amount):,.2f}")
    c.drawString(50, 405, f"Level: {level}")
    c.drawString(50, 385, f"Status: APPROVED")
    
    c.drawString(50, 355, "=" * 100)
    
    c.setFont("Helvetica", 10)
    c.drawString(50, 320, "Thank you for your payment. Please keep this receipt for your records.")

    # Generate QR code for verification
    qr_data = f"Receipt: {receipt_number} | Student: {student[1]} | Amount: ₦{float(amount):,.2f}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to temporary BytesIO object then draw on PDF
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    qr_image_reader = ImageReader(qr_buffer)
    
    # Add QR code to PDF (top right corner)
    c.drawImage(qr_image_reader, 612 - 50 - 100, 680, width=100, height=100, preserveAspectRatio=True)
    c.setFont("Helvetica", 9)
    c.drawCentredString(612 - 50 - 50, 665, "Scan to Verify")

    # Add signature image in the bottom right
    signature_path = os.path.join(logo_path, 'signature.jpg')
    if os.path.exists(signature_path):
        c.drawImage(signature_path, 612 - 50 - 180, 90, width=180, height=60, preserveAspectRatio=True, mask='auto')
        c.setFont("Helvetica", 10)
        c.drawString(612 - 50 - 180, 80, "Authorized Signature")
    
    c.save()
    qr_buffer.close()
    
    return filepath
@app.route('/view_students')
def view_students():

    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM students")
    students = cur.fetchall()

    return render_template('view_students.html', students=students)


# ---------------- PAY DUES ----------------
@app.route('/pay_dues')
def pay_dues():

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    cur = mysql.connection.cursor()

    # Get student level
    cur.execute("SELECT level FROM students WHERE id=%s", (session['student_id'],))
    level = cur.fetchone()[0]

    # Get bank details
    cur.execute("SELECT * FROM bank_details LIMIT 1")
    bank = cur.fetchone()

    amount = 8000 if level == "100" else 3000

    return render_template('pay_dues.html', amount=amount, bank=bank)

# ---------------- UPLOAD PROOF ----------------
@app.route('/upload_proof', methods=['GET', 'POST'])
def upload_proof():

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    if request.method == 'POST':

        file = request.files.get('proof')
        if not file or not file.filename:
            return render_template('upload_proof.html', error='Please upload a proof file.')

        filename = datetime.now().strftime("%Y%m%d%H%M%S") + file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur = mysql.connection.cursor()

        cur.execute("SELECT level FROM students WHERE id=%s", (session['student_id'],))
        level = cur.fetchone()[0]

        amount = 8000 if level == "100" else 3000

        cur.execute("""
            INSERT INTO payments(student_id, amount, level_paid_for, proof_image, status)
            VALUES(%s,%s,%s,%s,%s)
        """, (session['student_id'], amount, level, filename, "pending"))

        mysql.connection.commit()
        cur.close()

        return "Uploaded successfully"

    return render_template('upload_proof.html')


@app.route('/download_receipt/<int:receipt_id>')
def download_receipt(receipt_id):

    cur = mysql.connection.cursor()
    cur.execute("SELECT receipt_path FROM receipts WHERE id=%s", (receipt_id,))
    receipt = cur.fetchone()
    cur.close()
    
    if not receipt or not receipt[0]:
        return "Receipt not found", 404

    # Normalize path (replace backslashes with forward slashes)
    receipt_path = receipt[0].replace('\\', '/')
    
    if not os.path.exists(receipt_path):
        return "Receipt file not found", 404

    return send_file(receipt_path, as_attachment=True, download_name=os.path.basename(receipt_path))


# ---------------- VIEW PAYMENTS ----------------
@app.route('/view_payments')
def view_payments():

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM payments")
    payments = cur.fetchall()
    cur.close()

    return render_template('view_payments.html', payments=payments)


# ---------------- VIEW RECEIPTS (Student) ----------------
@app.route('/receipts')
def view_receipts():
    
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""SELECT r.id, r.receipt_number, p.amount, p.level_paid_for, r.receipt_path, p.status 
                   FROM receipts r 
                   JOIN payments p ON r.payment_id = p.id 
                   WHERE r.student_id=%s 
                   ORDER BY r.id DESC""", (session['student_id'],))
    receipts = cur.fetchall()
    cur.close()
    
    return render_template('receipts.html', receipts=receipts)


# ---------------- APPROVE PAYMENT ----------------
@app.route('/approve/<int:id>')
def approve(id):

    cur = mysql.connection.cursor()

    # Get payment details to find student_id
    cur.execute("SELECT student_id, amount, level_paid_for FROM payments WHERE id=%s", (id,))
    payment = cur.fetchone()
    
    if not payment:
        return "Payment not found", 404
    
    student_id, amount, level = payment
    
    # Update payment status to approved
    cur.execute("UPDATE payments SET status='approved' WHERE id=%s", (id,))
    
    # Generate receipt number
    receipt_no = "REC-" + str(random.randint(1000000, 9999999))
    
    # Generate PDF receipt
    receipt_filepath = generate_receipt_pdf(student_id, id, amount, level, receipt_no)
    
    # Insert receipt record in database
    cur.execute("""INSERT INTO receipts(student_id, payment_id, receipt_number, receipt_path) 
                   VALUES(%s,%s,%s,%s)""",
                (student_id, id, receipt_no, receipt_filepath))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('view_payments'))


# ---------------- REJECT PAYMENT ----------------
@app.route('/reject/<int:id>')
def reject(id):

    cur = mysql.connection.cursor()

    # Update payment status to rejected
    cur.execute("UPDATE payments SET status='rejected' WHERE id=%s", (id,))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('view_payments'))

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin WHERE username=%s AND password=%s",
                    (username, password))
        admin = cur.fetchone()

        if admin:
            session['admin'] = admin[1]  # store username
            return redirect(url_for('admin_dashboard'))
        else:
            return "Invalid admin login"

    return render_template('admin_login.html')


#if __name__ == '__main__':
    #from waitress import serve
    #serve(app, host='0.0.0.0', port=3307)
if __name__ == '__main__':
    app.run(debug=True)
