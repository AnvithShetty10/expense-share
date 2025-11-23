# Expense Share

A backend API for an expense sharing application that allows users to split expenses among multiple people and view outstanding balances.

## Features

- **User Authentication** - JWT-based authentication with secure password hashing
- **Expense Management** - Create, read, update, and delete expenses
- **Flexible Splitting** - Support for equal, percentage-based, and manual splits
- **Balance Calculations** - Automatic calculation of who owes whom and balance summary
- **Smart Caching** - Redis-backed caching for optimal performance
- **Interactive API Docs** - Auto-generated Swagger UI for API documentation

## Technology Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0 (async)
- **Cache**: Redis
- **Authentication**: OAuth2 with JWT
- **Testing**: pytest with async support
- **Containerization**: Docker + Docker Compose

## Quick Start

### Prerequisites
- Docker
- Docker Compose
- Make (usually pre-installed on Linux/Mac)

### Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd expense-sharing-api
```

2. **Create environment file**
```bash
cp .env.example .env
# Edit .env if needed (default values work for Docker setup)
```

3. **Generate JWT secret (update in .env)**
```python
import secrets
print(secrets.token_hex(64))
```

4. **Start all services**
```bash
make build && make up
```

5. **Help**
```bash
make help
```

The application will:
- Start PostgreSQL database
- Start Redis cache
- Run database migrations automatically
- Seed database with 5 test users
- Start the API server

4. **Access the application**
- API Base URL: http://localhost:8000
- API Documentation (Swagger UI): http://localhost:8000/docs

5. **How to Authorize in Swagger UI**
- Open the Swagger UI at `/docs`.
- Click the **Authorize** button.
- Fill in your username and password.
- Click **Authorize**.

Swagger UI will automatically request a token and attach it to all protected API calls.

## Local Development Setup (Without Docker)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis

### Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd expense-share
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Setup PostgreSQL database**
```bash
psql -U postgres
CREATE DATABASE expense_db;
```

5. **Setup Redis**
```bash
# Start Redis server (if not running)
redis-server
```

6. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your database and Redis URLs
```

Example `.env`:
```
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/expense_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-at-least-32-characters-long
```

7. **Run database migrations**
```bash
alembic upgrade head
```

8. **Seed database with test users**
```bash
python scripts/seed_database.py
```

9. **Start the application**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Test User Credentials

The database is pre-seeded with 5 test users:

| Email | Username | Password    | Full Name |
|-------|----------|-------------|-----------|
| user1@example.com | user1 | password111 | User One |
| user2@example.com | user2 | password222 | User Two |
| user3@example.com | user3 | password333 | User Three |
| user4@example.com | user4 | password444 | User Four |
| user5@example.com | user5 | password555 | User Five |

## API Documentation

#### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get JWT token
- `GET /api/v1/auth/me` - Get current user info

#### Expenses
- `POST /api/v1/expenses` - Create new expense (supports idempotency)
- `GET /api/v1/expenses` - List user's expenses (with pagination)
- `GET /api/v1/expenses/{id}` - Get expense details
- `PUT /api/v1/expenses/{id}` - Update expense (creator only)
- `DELETE /api/v1/expenses/{id}` - Delete expense (creator only)

#### Balances
- `GET /api/v1/balances` - Get all balances for current user
- `GET /api/v1/balances/summary` - Get balance summary
- `GET /api/v1/balances/user/{user_id}` - Get balance with specific user

#### Users
- `GET /api/v1/users` - List all users (with search)
- `GET /api/v1/users/{id}` - Get user details

### Example API Requests

#### Create an Expense (Equal Split)

```bash
POST /api/v1/expenses
Authorization: Bearer <your-token>
Content-Type: application/json

{
  "description": "Lunch at Corner Cafe",
  "total_amount": 1000.00,
  "expense_date": "2024-11-23",
  "split_type": "EQUAL",
  "group_name": "Office Team",
  "participants": [
    {
      "user_id": "uuid-of-user1",
      "amount_paid": 1000.00
    },
    {
      "user_id": "uuid-of-user2",
      "amount_paid": 0.00
    },
    {
      "user_id": "uuid-of-user3",
      "amount_paid": 0.00
    },
    {
      "user_id": "uuid-of-user4",
      "amount_paid": 0.00
    }
  ]
}
```

The API will automatically calculate equal splits: each person owes ₹250.

#### Create an Expense (Percentage Split)

```bash
POST /api/v1/expenses
Authorization: Bearer <your-token>
Content-Type: application/json

{
  "description": "Team Dinner",
  "total_amount": 2000.00,
  "expense_date": "2024-11-23",
  "split_type": "PERCENTAGE",
  "participants": [
    {
      "user_id": "uuid-of-user1",
      "amount_paid": 2000.00,
      "percentage": 40.00
    },
    {
      "user_id": "uuid-of-user2",
      "amount_paid": 0.00,
      "percentage": 30.00
    },
    {
      "user_id": "uuid-of-user3",
      "amount_paid": 0.00,
      "percentage": 30.00
    }
  ]
}
```

User1 pays ₹2000 but owes ₹800 (40%), so others owe them ₹1200.

#### View Your Balances

```bash
GET /api/v1/balances
Authorization: Bearer <your-token>
```

Response:
```json
{
  "balances": [
    {
      "user": {
        "id": "uuid",
        "username": "user2",
        "full_name": "User Two",
        "email": "user2@example.com"
      },
      "amount": -550.00,
      "type": "you_owe"
    },
    {
      "user": {
        "id": "uuid",
        "username": "user3",
        "full_name": "User Three",
        "email": "user3@example.com"
      },
      "amount": 600.00,
      "type": "owes_you"
    }
  ]
}
```

#### View Balance Summary

```bash
GET /api/v1/balances/summary
Authorization: Bearer <your-token>
```

Response:
```json
{
  "overall_balance": 50.00,
  "total_you_owe": 550.00,
  "total_owed_to_you": 600.00,
  "num_people_you_owe": 1,
  "num_people_owe_you": 1
}
```

## Database Design

### Why PostgreSQL?

PostgreSQL was chosen for this application for the following reasons:

1. **ACID Compliance**: PostgreSQL provides full ACID (Atomicity, Consistency, Isolation, Durability) guarantees, which are essential for financial transactions. This ensures that all expense operations either complete fully or not at all, maintaining data integrity.

2. **Decimal Precision**: PostgreSQL's native DECIMAL data type provides exact precision for monetary values, eliminating floating-point arithmetic errors that could occur with binary floating-point types. This is critical when dealing with money - for example, storing ₹10.00 remains exactly ₹10.00, not ₹9.999999.

3. **Strong Constraints**: PostgreSQL enforces data integrity at the database level through foreign keys, check constraints, and unique constraints. This acts as a safety net, preventing invalid data from being stored even if application-level validation fails.

4. **JSONB Support**: While maintaining relational integrity for core financial data, PostgreSQL's JSONB type provides flexibility for future schema evolution without sacrificing query performance or consistency.

5. **Proven Scalability**: PostgreSQL has been battle-tested for handling millions of financial transactions. It scales vertically (more powerful hardware) and horizontally (read replicas) effectively.

6. **Transaction Isolation**: PostgreSQL's robust transaction isolation levels prevent race conditions in concurrent operations, which is crucial when multiple users create or modify expenses simultaneously.

7. **Rich Ecosystem**: Excellent ORM support (SQLAlchemy), mature migration tools (Alembic), and extensive monitoring/management tools make PostgreSQL a production-ready choice.

### Database Schema

The database consists of three main tables with clear relationships:

#### **users** table
Stores user account information and authentication credentials.

**Columns:**
- `id` (UUID, Primary Key) - Unique identifier for each user
- `email` (VARCHAR, UNIQUE, NOT NULL) - User's email address for login
- `username` (VARCHAR, UNIQUE, NOT NULL) - User's unique username
- `hashed_password` (VARCHAR, NOT NULL) - Bcrypt-hashed password
- `full_name` (VARCHAR, NULLABLE) - User's display name
- `is_active` (BOOLEAN, DEFAULT TRUE) - Account active status
- `created_at` (TIMESTAMP) - Account creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp

**Indexes:**
- Primary key on `id`
- Unique index on `email` (for fast login lookups)
- Unique index on `username` (for fast login lookups)

**Relationships:**
- One user can create many expenses (one-to-many)
- One user can participate in many expenses (many-to-many through expense_participants)

---

#### **expenses** table
Stores the core expense information.

**Columns:**
- `id` (UUID, Primary Key) - Unique identifier for each expense
- `description` (VARCHAR(500), NOT NULL) - What the expense was for
- `total_amount` (DECIMAL(12,2), NOT NULL) - Total expense amount with 2 decimal precision
- `currency` (VARCHAR(3), DEFAULT 'INR') - Currency code
- `expense_date` (DATE, NOT NULL) - When the expense occurred
- `created_by_user_id` (UUID, Foreign Key → users.id, NOT NULL) - Who created the expense
- `group_name` (VARCHAR(255), NULLABLE) - Optional group/category label
- `split_type` (VARCHAR(20), NOT NULL) - How expense is split: EQUAL, PERCENTAGE, or MANUAL
- `created_at` (TIMESTAMP) - When expense was created
- `updated_at` (TIMESTAMP) - Last update timestamp

**Constraints:**
- CHECK: `total_amount > 0` (expenses must be positive)
- CHECK: `split_type IN ('EQUAL', 'PERCENTAGE', 'MANUAL')`
- Foreign Key: `created_by_user_id` references `users(id)`

**Indexes:**
- Primary key on `id`
- Index on `created_by_user_id` (for "my expenses" queries)
- Index on `expense_date` (for date range queries)
- Index on `created_at` DESC (for recent expenses)

**Relationships:**
- Each expense belongs to one creator (many-to-one with users)
- Each expense has many participants (one-to-many with expense_participants)

---

#### **expense_participants** table
Tracks who paid and who owes for each expense (the "join" table with payment data).

**Columns:**
- `id` (UUID, Primary Key) - Unique identifier
- `expense_id` (UUID, Foreign Key → expenses.id, NOT NULL) - Which expense
- `user_id` (UUID, Foreign Key → users.id, NOT NULL) - Which user
- `amount_paid` (DECIMAL(12,2), NOT NULL, DEFAULT 0) - How much this user paid
- `amount_owed` (DECIMAL(12,2), NOT NULL, DEFAULT 0) - How much this user owes
- `percentage` (DECIMAL(5,2), NULLABLE) - Percentage for percentage splits (0-100)
- `created_at` (TIMESTAMP) - When participation was recorded

**Constraints:**
- UNIQUE: (`expense_id`, `user_id`) - Each user appears once per expense
- CHECK: `amount_paid >= 0` (no negative payments)
- CHECK: `amount_owed >= 0` (no negative debts)
- CHECK: `amount_paid > 0 OR amount_owed > 0` (must pay or owe something)
- CHECK: `percentage IS NULL OR (percentage >= 0 AND percentage <= 100)`
- Foreign Key: `expense_id` references `expenses(id)` ON DELETE CASCADE
- Foreign Key: `user_id` references `users(id)`

**Indexes:**
- Primary key on `id`
- Index on `expense_id` (for getting all participants of an expense)
- Index on `user_id` (for getting all expenses a user is part of)
- Composite index on (`user_id`, `expense_id`) (for balance calculations)

**Relationships:**
- Each participant record belongs to one expense (many-to-one)
- Each participant record belongs to one user (many-to-one)

## Testing

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=app --cov-report=html --cov-report=term
```

## Performance Considerations

### Current Capabilities

The application can handle:
- ~100 concurrent users
- ~10,000 expenses per day
- ~100 requests per second
- Response times < 200ms (95th percentile)

### Optimization Strategies

**Implemented:**
- Database connection pooling (20 connections)
- Redis caching for balance calculations
- Database indexes on frequently queried columns
- Async I/O for all operations
- Pagination for large result sets

## Future Enhancements

Features that could be added in future versions:

**User Features:**
- Group management with permissions
- Expense categories and tags
- Settlement recording (mark debts as paid)
- Expense comments and notes
- Activity feed

**Technical Features:**
- Multi-currency support with conversion rates
- Debt simplification algorithm
- Email notifications
- Expense export (CSV, PDF)

---

**Version**: 1.0.0  
**Last Updated**: November 23, 2024
