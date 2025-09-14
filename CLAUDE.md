# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a South China Sea public opinion daily report generation system ("南海舆情日报生成系统") that processes CSV data files, cleans and deduplicates them, integrates with Dify AI workflows, and generates Word document reports.

## Tech Stack

- **Frontend**: React + TypeScript + Vite + Tailwind CSS + shadcn/ui components
- **Backend**: Python FastAPI + Supabase (PostgreSQL)
- **AI Integration**: Dify API workflows for data processing and analysis
- **Document Generation**: python-docx with Word templates

## Development Commands

### Frontend (React + Vite)
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Start development server (localhost:5173)
npm run build        # Build for production
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

### Backend (FastAPI + Supabase)
```bash
cd backend
pip install -r requirements.txt  # Install dependencies including Supabase
python start_server.py          # Start FastAPI server (localhost:8000)
# Alternative: python main.py
```

**Environment Setup:**
```bash
# Copy environment template and configure
cp .env.example .env
# Edit .env with your Supabase credentials:
# SUPABASE_URL=your_supabase_project_url
# SUPABASE_ANON_KEY=your_supabase_anon_key
```

**Testing:**
```bash
cd backend
python test_supabase.py  # Test Supabase connection and functionality
```

**Note:** Backend API runs on port 8000, frontend development server on port 5173

## Architecture Overview

### Data Flow
1. **File Upload**: CSV files uploaded via drag-and-drop interface
2. **Data Processing**: Cleaning, deduplication, and Supabase storage
3. **AI Analysis**: Dify workflow processes data into domestic/foreign sources
4. **Report Generation**: Word document created using template.docx
5. **History Management**: Track processing status and download reports

### Database Models (Supabase Tables)
- `upload_records`: File upload metadata and status
- `processing_status`: Real-time processing progress tracking
- `raw_data`: Original CSV data storage
- `processed_data`: Structured data from Dify workflows
- `report_generations`: Generated report metadata

### Key Components

#### Frontend Structure
- `src/components/`: Reusable UI components (drag-drop, status panels, data tables)
- `src/services/`: API communication with backend
- Uses shadcn/ui components with Material Design styling (deep blue theme)

#### Backend Structure
- `main.py`: FastAPI application entry point
- `models.py`: Pydantic data models with async Supabase integration
- `schemas.py`: Request/response schemas
- `database.py`: Supabase client configuration and service layer
- `services/`: Business logic modules
- `templates/`: Word document templates for report generation
- `.env.example`: Environment configuration template

### Dify Integration
- Authenticates with Bearer token (app-cg5qmpzNXybVJwuNR2qgQsMR)
- Uploads CSV files and processes via streaming workflows
- Returns structured data with domestic_sources and foreign_sources
- Sample workflow result structure available in 使用示例.py:225-310

## Database Configuration

**Supabase Setup:**
- Create a Supabase project at https://supabase.com
- Use the Database > SQL Editor to create tables matching the models
- Configure environment variables in `.env`:
  - `SUPABASE_URL`: Your project URL
  - `SUPABASE_ANON_KEY`: Your anon public key

**Required Tables:**
```sql
-- Execute these in Supabase SQL Editor
CREATE TABLE upload_records (
  id SERIAL PRIMARY KEY,
  filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size INTEGER NOT NULL,
  upload_time TIMESTAMP DEFAULT NOW(),
  status VARCHAR(50) DEFAULT 'uploaded',
  error_message TEXT,
  report_path VARCHAR(500)
);

CREATE TABLE processing_status (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id),
  current_step VARCHAR(50) NOT NULL,
  status VARCHAR(50) DEFAULT 'processing',
  progress FLOAT DEFAULT 0.0,
  message TEXT,
  error_message TEXT,
  created_time TIMESTAMP DEFAULT NOW(),
  updated_time TIMESTAMP DEFAULT NOW()
);

CREATE TABLE raw_data (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id),
  url TEXT,
  source_name VARCHAR(255),
  author_username VARCHAR(255),
  title TEXT,
  hit_sentence TEXT,
  language VARCHAR(50),
  original_data JSONB,
  created_time TIMESTAMP DEFAULT NOW()
);

CREATE TABLE processed_data (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id),
  data_type VARCHAR(50) NOT NULL,
  structured_data JSONB NOT NULL,
  created_time TIMESTAMP DEFAULT NOW()
);

CREATE TABLE report_generations (
  id SERIAL PRIMARY KEY,
  upload_id INTEGER REFERENCES upload_records(id),
  report_path VARCHAR(500) NOT NULL,
  report_type VARCHAR(50) DEFAULT 'docx',
  generation_time TIMESTAMP DEFAULT NOW(),
  file_size INTEGER
);
```

## File Structure Notes

- Root template.docx used for Word report generation
- Backend uploads/ directory stores uploaded CSV files
- Backend reports/ directory contains generated Word documents
- Frontend uses Vite dev server with TypeScript and ESLint
- Project uses Chinese filenames and content throughout