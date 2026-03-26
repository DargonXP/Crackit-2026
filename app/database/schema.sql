-- Core schema for the Crackit onboarding MVP.
-- Note: the provided team schema didn't include `users.name` nor `messages.is_read`.
-- This file includes MVP-required columns.

CREATE TABLE IF NOT EXISTS companies (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  invite_code VARCHAR(50) UNIQUE NOT NULL,
  system_prompt TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  company_id INTEGER REFERENCES companies(id),
  role VARCHAR(20) NOT NULL CHECK (role IN ('newcomer', 'experienced')),
  position VARCHAR(100),
  name VARCHAR(255),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
  id SERIAL PRIMARY KEY,
  company_id INTEGER REFERENCES companies(id),
  position VARCHAR(100),
  difficulty INTEGER DEFAULT 1,
  description TEXT NOT NULL,
  solution TEXT,
  author_id INTEGER REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_task_progress (
  user_id INTEGER REFERENCES users(id),
  task_id INTEGER REFERENCES tasks(id),
  status VARCHAR(20) DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'solved')),
  attempt_text TEXT,
  score FLOAT,
  updated_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (user_id, task_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id SERIAL PRIMARY KEY,
  sender_id INTEGER REFERENCES users(id),
  receiver_id INTEGER REFERENCES users(id),
  task_id INTEGER REFERENCES tasks(id),
  text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  is_read BOOLEAN DEFAULT FALSE
);

