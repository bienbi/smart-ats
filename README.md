# Smart ATS — AI-Powered Applicant Tracking System

Smart ATS is an enterprise-grade recruitment and resume optimization platform powered by Large Language Models (LLMs) designed to streamline candidate screening, interview preparation, and talent acquisition processes. Built with modern AI capabilities, a ReactJS frontend, a FastAPI backend, MongoDB, and professional deployment standards.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Frontend Interface](#frontend-interface)
- [Deployment](#deployment)
- [Screenshots](#screenshots)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Overview

Smart ATS transforms traditional HR recruitment workflows by providing intelligent automation for:
- Automated resume parsing and structured data extraction
- Multi-tiered candidate skill evaluation and semantic matching
- Accurate experience timeline deduplication on a monthly grid
- Dynamic AI mock interview generation based on identified skill gaps
- Printable candidate evaluation report generation in HTML/Markdown formats

The system integrates a React-based single page application for direct HR and candidate usage, backed by a high-performance FastAPI server communicating with MongoDB and external LLM APIs.

## Key Features

- **Intelligent Candidate Screening**: Asynchronous batch resume parsing and candidate evaluation against target Job Descriptions (JDs).
- **Multi-tiered Skill Analysis**: Core (60%), Supporting (30%), and Tool (10%) skill classification combined with semantic equivalent mapping (VueJS vs. ReactJS) using LLMs.
- **Experience Deduplication**: Month-grid timeline merging algorithm to eliminate inflated years of experience caused by parallel or overlapping jobs.
- **AI Mock Interview Chatbot**: A state-machine controlled interactive room limited to 5 technical questions targeting the candidate's skill gaps, with real-time feedback.
- **Resume Tailoring & Cover Letter Generator**: Custom resume adjustment and professional cover letter creation following a strict no-emoji policy.
- **Docker Deployment**: Fully containerized multi-service setup behind Nginx serving as reverse proxy and managing SSL termination.
- **NoSQL Caching**: MD5/SHA-256 hash caching in MongoDB to prevent redundant LLM API calls and reduce system latency.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- At least 4GB RAM available
- Internet connection for external LLM API access (Groq or Deepseek)


### First Use

1. Open the web interface at http://localhost:8080
2. Configure your API keys in the `.env` file or backend settings
3. Go to **Manage JDs** and create a target Job Description
4. Upload one or more candidate resumes in the **Dashboard** to run analysis
5. Go to the **Candidate Portal** to test CV Tailoring and the AI Chatbot Interview

## Installation

### Option 1: Docker Deployment (Recommended)

```powershell
# Clone repository
git clone https://github.com/yourusername/smart-ats.git
cd smart-ats

# Build and start services using Docker Compose
docker-compose up -d --build

# View real-time container logs
docker-compose logs -f
```

### Option 2: Local Development Setup

```powershell
# Clone repository
git clone https://github.com/yourusername/smart-ats.git
cd smart-ats

# --- Set up Backend ---
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install Python backend dependencies
pip install -r backend/requirements.txt

# Copy configuration
cp .env.example .env

# Edit .env file with your API keys (e.g. GROQ_API_KEY)
# Start the FastAPI API server
python backend/main.py

# --- Set up Frontend (in another terminal) ---
cd frontend
npm install
npm run dev
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# LLM API Keys
GROQ_API_KEY=gsk_your_groq_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Database Settings
MONGODB_URI=mongodb://localhost:27017
# Or Atlas URI: mongodb+srv://username:password@cluster.mongodb.net/ats_db

# Application Configuration
APP_ENV=production
DEBUG=false
HOST=0.0.0.0
PORT=8000
```

## Usage

### Web Interface

1. **Dashboard (HR Portal)**
   - View recent candidate analyses, overall match scores, and analysis status.
   - Upload new resumes (PDF/DOCX) and match them against active JDs with adjustable criterion weights.
   - View detailed applicant breakdowns, AI recruiter notes, strengths, and risks.

2. **Manage JDs (HR Portal)**
   - Enter new job postings. AI automatically parses and structures the JD into core/supporting/tool skills and requirements.

3. **Analysis History (HR Portal)**
   - Filter applicants dynamically by university, degree level, experience, or mandatory skills.
   - Download printable reports in HTML or Markdown formats.

4. **Interactive Mock Interview (Candidate Portal)**
   - Candidates enter the AI interview room to answer 5 dynamic questions based on missing skills.
   - Receive immediate scores (out of 10) and suggested answers for each response.

5. **CV Tailoring (Candidate Portal)**
   - Upload a resume and select a JD to generate an optimized CV text and a tailored cover letter (no emoji).


## Frontend Interface

The web interface is built in React JS with a dark theme and custom components:

- **HR Dashboard**: Overall analysis dashboard, resume upload zone, and detailed drawer drawer.
- **JD Manager**: Interface to create, view, and delete structured job postings.
- **History View**: Search and filter pipeline for all parsed resumes with Excel/HTML export.
- **AI Mock Interview**: Interactive chat console with a progress tracking bar and real-time score indicators.
- **CV Tailoring**: Split-panel layout showing the optimized resume next to the generated cover letter.



## Screenshots

### Main Dashboard
![Main Dashboard](assets/images/dashboard.png)
*HR dashboard listing analyzed candidates, scores, and status*

### Resume Analysis Detail
![Resume Analysis](assets/images/resume_analysis.png)
*Detailed drawer showing skill gaps, AI recruiter notes, and weighting factors*

### AI Mock Interview Room
![Interview Chat](docs/images/frontend.png)
*Interactive chat room showing candidate answer inputs and AI evaluation scores*

## Development

### Project Structure

```
ats/
├── backend/                     # Asynchronous API and Algorithms
│   ├── main.py                  # FastAPI application entrypoint
│   ├── database.py              # MongoDB connection & CRUD queries
│   ├── auth.py                  # Token-based authentication
│   ├── core/                    # Algorithms and LLM parsing
│   │   ├── extract_cv.py        # PDF/DOCX text bóc tách & structured Pydantic schemas
│   │   ├── scoring_cv.py        # Multi-tiered skill match & grid union experience math
│   │   ├── chatbot.py           # State machine chatbot session controller
│   │   └── cv_tailor.py         # Resume optimization & cover letter writer
│   ├── Dockerfile               # Backend Dockerfile
│   └── requirements.txt         # Backend Python requirements
│
├── frontend/                    # Single Page Application
│   ├── vite.config.js           # Build settings
│   ├── nginx.conf               # Reverse proxy routing settings
│   ├── Dockerfile               # Multi-stage production build Dockerfile
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── App.jsx              # Main routing
│       ├── Login.jsx            # HR authorization panel
│       ├── index.css            # Stylesheets and colors
│       ├── hr/                  # HR modules
│       │   ├── HrDashboard.jsx  # Candidate upload and score aggregation
│       │   ├── CvAnalysis.jsx   # Evaluation reports and charts
│       │   ├── JdManager.jsx    # JD creator
│       │   └── AnalysisHistory.jsx # Filtering and history lists
│       └── candidate/           # Job Seeker modules
│           ├── CvTailor.jsx     # Cover Letter generator
│           └── InterviewChatbot.jsx # Virtual interview room
│
├── docker-compose.yml           # Local orchestration file
├── deploy.sh                    # Production VM bootstrap script
└── README.md                    # Project documentation
```

