# Tanuh BCD Website

A full-stack application featuring a React frontend, Node.js backend, and PostgreSQL database, all containerized with Docker.

## Project Structure

- `frontend/`: Contains the frontend application, backend services, and Docker configuration.
  - `frontend/frontend/`: React + TypeScript application (Vite).
  - `frontend/backend/`: Node.js + Express + TypeORM API.
  - `frontend/docker-compose.yml`: Docker Compose configuration to run the entire stack.
- `backend/`: Root-level backend directory (alternative/original structure).

## Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Getting Started

To start the entire application (Frontend, Backend, and Database) using Docker Compose, follow these steps:

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Start the services:**
   ```bash
   docker-compose up --build
   ```

   This command will:
   - Build the frontend and backend Docker images.
   - Pull the PostgreSQL image.
   - Start all containers and link them together.

## Accessing the Application

Once the services are up and running, you can access them at:

- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:4000/api](http://localhost:4000/api)
- **Database:** PostgreSQL is running on port `5432` (internal to Docker network, exposed as `5432` if needed).

## Default Roles and Login

The application supports role-based access control with the following roles:
- `admin` (Superuser with access to all features)
- `clinic`
- `doctor`
- `technologist`

*Note: Initial users and hospitals may need to be seeded or created via the API/Database.*

## Development

If you wish to run the services individually for development:

### Backend
1. Navigate to the backend directory: `cd frontend/backend`
2. Install dependencies: `npm install`
3. Set up your `.env` file based on the environment variables in `docker-compose.yml`.
4. Run in development mode: `npm run dev`

### Frontend
1. Navigate to the frontend directory: `cd frontend/frontend`
2. Install dependencies: `npm install`
3. Start the development server: `npm run dev`
