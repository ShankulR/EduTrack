EDUTRACK STUDENT MANAGEMENT SYSTEM
===================================

Requirements:
- Python 3.10 or newer
- Internet connection for Bootstrap, Bootstrap Icons and Chart.js CDN assets

Windows / VS Code:
1. Extract this ZIP to your Desktop.
2. Open the extracted Educanize_School_Management folder in VS Code.
3. Open Terminal > New Terminal.
4. Run:
   python -m venv venv
   .\venv\Scripts\Activate
   pip install -r requirements.txt
   python app.py
5. Open http://127.0.0.1:5000

The database file school.db is created automatically.
Features:
- Dashboard with live student, teacher, course, attendance and fee summaries
- Student CRUD and search
- Teacher registration and deletion
- Daily attendance marking
- Fee payment records
- Reports and student CSV export

This is a local educational demo. It does not include user authentication or production security.
Change the Flask secret key and add authentication/CSRF protection before any public deployment.
