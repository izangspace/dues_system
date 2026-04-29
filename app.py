from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import os
from datetime import datetime
from reportlab.pdfgen import canvas
import random
app = Flask(__name__)
app.secret_key = "secret_key_123"

# ---------------- MYSQL CONFIG ----------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Geo@09033008658'
app.config['MYSQL_DB'] = 'student_dues'
app.config['MYSQL_PORT'] = 3307
mysql = MySQL(app)

# ---------------- UPLOAD FOLDER ----------------
UPLOAD_FOLDER = 'static/uploads'
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

            image = request.files['image']

            if image.filename == "":
                return "No image selected"

            filename = image.filename

            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(upload_path)

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO students(name, matric_no, email, level, password, image)
                VALUES(%s,%s,%s,%s,%s,%s)
            """, (name, matric_no, email, level, password, filename))

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
        cur.execute("SELECT * FROM students WHERE matric_no=%s AND password=%s",
                    (matric_no, password))
        user = cur.fetchone()

        if user:
            session['student_id'] = user[0]
            return redirect(url_for('student_dashboard'))
        else:
            return "Invalid login"

    return render_template('student_login.html')


# ---------------- DASHBOARD ----------------
@app.route('/student_dashboard')
def student_dashboard():

    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM students WHERE id=%s", (session['student_id'],))
    user = cur.fetchone()

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
# ---------------- admin dashboard ----------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html')
# ---------------- view students ----------------
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

        file = request.files['proof']
        filename = datetime.now().strftime("%Y%m%d%H%M%S") + file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur = mysql.connection.cursor()

        cur.execute("SELECT level FROM students WHERE id=%s", (session['student_id'],))
        level = cur.fetchone()[0]

        amount = 5000 if level == "100" else 3000

        cur.execute("""
            INSERT INTO payments(student_id, amount, level_paid_for, proof_image, status)
            VALUES(%s,%s,%s,%s,%s)
        """, (session['student_id'], amount, level, filename, "pending"))

        mysql.connection.commit()
        cur.close()

        return "Uploaded successfully"

    return render_template('upload_proof.html')


# ---------------- VIEW PAYMENTS ----------------
@app.route('/view_payments')
def view_payments():

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM payments")
    payments = cur.fetchall()

    return render_template('view_payments.html', payments=payments)


# ---------------- APPROVE PAYMENT ----------------
@app.route('/approve/<int:id>')
def approve(id):

    cur = mysql.connection.cursor()

    cur.execute("UPDATE payments SET status='approved' WHERE id=%s", (id,))

    receipt_no = "REC-" + str(random.randint(100000, 999999))

    cur.execute("INSERT INTO receipts(student_id, payment_id, receipt_number) VALUES(%s,%s,%s)",
                (1, id, receipt_no))

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