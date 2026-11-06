# IT Help Desk and Incident Management System

## Project Overview
The IT Help Desk and Incident Management System is a web-based application developed using Python and Flask. It helps users report technical issues through tickets while allowing support staff to manage, assign, prioritize, and track incidents.

The system also includes SLA monitoring and visual analytics to help track support performance and identify recurring problems.

## Technologies Used
- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- Chart.js
- Flask-Login
- Flask-WTF

## Key Features

- User registration and login
- Role-based access for users and staff
- Create and manage support tickets
- Ticket assignment and status updates
- Priority-based ticket management
- SLA deadline tracking
- Ticket search and filtering
- Incident reports
- Dashboard with visual analytics and charts
- Tracking of resolved tickets

## Project Structure

```text
IT_Helpdesk_System/
│
├── app.py
├── requirements.txt
├── .gitignore
│
├── static/
│   └── style.css
│
├── templates/
│   ├── create_ticket.html
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   ├── staff_dashboard.html
│   ├── staff_reports.html
│   ├── tickets.html
│   └── update_ticket.html
│
└── instance/
    └── helpdesk.db
```

## SLA Tracking

The system uses different resolution targets based on ticket priority:

| Priority | SLA Target |
|----------|------------|
| Critical | 4 Hours |
| High | 8 Hours |
| Medium | 24 Hours |
| Low | 72 Hours |

## Installation and Setup

1. Clone or download this repository.
2. Create a Python virtual environment.
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project directory and add a secret key:

```text
SECRET_KEY=your_secret_key
```

5. Run the application:

```bash
python app.py
```

6. Open your browser and visit:

```text
http://127.0.0.1:5000
```

## Learning Objectives

This project was developed to gain practical experience in:

- Python web development
- Database management
- Authentication and authorization
- Role-based access control
- Incident and ticket management
- SLA monitoring
- Data visualization

## Future Improvements

- Email notifications
- Advanced reporting
- Improved ticket management features
- Integration with external monitoring tools

---

**Project:** IT Help Desk and Incident Management System  
**Developed using:** Python, Flask and SQLite