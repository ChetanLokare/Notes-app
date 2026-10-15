# 📝 My_Notes — Personal Notes Web Application

My_Notes is a personal notes web application built using Python and FastAPI, with MongoDB for data storage and a responsive web interface. It allows users to create, manage, search, and organize their personal notes.

This project demonstrates practical implementation of backend development, database integration, user authentication, API development, and frontend interaction.

## ✨ Features

- **User Authentication:** Register, log in, and log out.
- **Create Notes:** Save personal notes with a title and description.
- **Edit Notes:** Update existing notes.
- **Delete Notes:** Remove notes you no longer need.
- **Important Notes:** Mark and unmark important notes.
- **Search:** Find notes using keywords.
- **Filtering:** Filter notes by creation date, update date, importance, and update status.
- **Sorting:** Organize notes according to available sorting options.
- **Pagination:** Browse notes across multiple pages.
- **Theme Selection:** Choose light mode, dark mode, or follow your system theme.
- **Responsive Design:** Access the interface on desktop and mobile screens.
- **MongoDB Integration:** Store user and note data in a database.

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| FastAPI | Web framework and API endpoints |
| MongoDB Atlas | Database storage |
| PyMongo | MongoDB connectivity |
| Jinja2 | HTML templating |
| HTML5 | Web page structure |
| CSS3 | Styling and responsive layouts |
| Bootstrap 5.3.3 | UI components and responsive design |
| JavaScript | Search, filters, pagination, themes, and interactions |
| Uvicorn | ASGI application server |
| python-dotenv | Environment configuration |

## 📁 Project Structure

```text
My_Notes/
├── index.py
├── config/
│   └── db.py
├── models/
│   └── note.py
├── routes/
│   ├── auth.py
│   └── note.py
├── schemas/
│   └── schemas.py
├── templates/
│   ├── index.html
│   ├── login.html
│   └── register.html
├── static/
│   ├── style.css
│   ├── common.css
│   ├── script.js
│   └── themes/
│       ├── light.css
│       └── dark.css
├── .gitignore
├── requirements.txt
└── README.md
```

## ⚙️ Installation and Setup

### Prerequisites

- Python installed on your computer.
- A MongoDB Atlas account or another accessible MongoDB instance.
- Git installed on your computer.

### 1. Clone the repository

```bash
git clone https://github.com/ChetanLokare/My_Notes.git
cd My_Notes
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate the environment on Windows:

```powershell
venv\Scripts\activate
```

For macOS or Linux:

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
MONGO_URI=your_mongodb_connection_string
SESSION_SECRET=your_long_random_secret
SESSION_HTTPS_ONLY=false
```

Configure the variables as follows:

- `MONGO_URI`: Your MongoDB connection string.
- `SESSION_SECRET`: A strong, randomly generated secret for session security.
- `SESSION_HTTPS_ONLY`: Use `false` for local HTTP development. Set it to `true` when deploying behind HTTPS so cookies are secure.

Make sure MongoDB is accessible and the connection string has the required permissions.

**Security:** Never upload your real `.env` file, database password, or session secret to GitHub.

### 5. Start the application

```bash
uvicorn index:app --reload
```

Open the application at:

http://127.0.0.1:8000

If FastAPI's interactive API documentation is enabled, access it at:

http://127.0.0.1:8000/docs

## 🗄️ Database Structure

The application uses a MongoDB database named `Notes` with the following collections:

| Collection | Purpose |
|---|---|
| `users` | Stores user account data |
| `notes` | Stores personal notes |

Each user's notes are associated with their user ID. All note retrieval and modification operations should enforce ownership so users cannot access or modify other users' notes.

## 🔐 Security Considerations

The project includes password hashing and session-based authentication.

Before deploying the application publicly, verify and strengthen the following:

- Ensure every note operation checks the authenticated user's ownership.
- Add CSRF protection to state-changing requests.
- Implement login rate limiting.
- Use HTTPS and secure session-cookie settings in production.
- Keep secrets and database credentials out of version control.
- Validate input and handle errors safely.

## 🧪 Testing Checklist

Before publishing a release, verify the application manually:

- [ ] User registration and login work correctly.
- [ ] Logout ends the authenticated session.
- [ ] Users can create, edit, and delete their own notes.
- [ ] Important-note functionality works.
- [ ] Search and filters return expected results.
- [ ] Sorting and pagination work correctly.
- [ ] Light, dark, and system themes work correctly.
- [ ] Users cannot access or modify another user's notes.
- [ ] The application starts successfully in a fresh Python environment.

## 🔮 Future Improvements

- Automated tests for API endpoints and authentication.
- CSRF protection and login rate limiting.
- Note categories, tags, and pinned notes.
- Rich-text note editing.
- Export and backup functionality.
- Improved accessibility and error handling.
- Deployment configuration and monitoring.

## 🎯 Project Objective

The objective of My_Notes is to gain practical experience building a web application with Python backend technologies, database operations, authentication, and interactive frontend features.

The project is part of my learning journey in backend and full-stack web development.

## 👨‍💻 Author

**Chetan Lokare**

- GitHub: [ChetanLokare](https://github.com/ChetanLokare)
- LinkedIn: [Chetan Lokare](https://www.linkedin.com/in/chetan-lokare-50ba65175)

---

*Developed as a personal learning project using Python, FastAPI, MongoDB, and modern web technologies.*
