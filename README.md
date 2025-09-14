# SaaS Orchestration Platform

A secure, production-ready SaaS orchestration platform for managing VPS instances with Odoo deployments, featuring a comprehensive Nginx configuration editor with safety-first operations.

## Features

- **VPS Management**: Automated onboarding and bootstrap of VPS instances
- **Nginx Config Editor**: Secure, auditable configuration management with validation, versioning, and automatic rollback
- **Odoo Deployment**: Multi-version Odoo deployments with industry-specific configurations
- **Monitoring**: Comprehensive monitoring stack with Prometheus and Grafana
- **Security**: Admin-only access with encrypted data storage and audit logging
- **Automation**: Ansible-based remote orchestration and lifecycle management

## Architecture

### Backend (FastAPI + Python)
- FastAPI for high-performance async API
- PostgreSQL with SQLAlchemy for data persistence
- Redis for caching and task queues
- Celery for background task processing

### Frontend (React + TypeScript)
- React 18 with TypeScript
- Tailwind CSS for styling
- React Query for state management
- Vite for build tooling

### Infrastructure
- Docker & Docker Compose for containerization
- Ansible for VPS orchestration
- Prometheus + Grafana for monitoring
- GitHub Actions for CI/CD

## Quick Start

### Development Setup

1. **Backend Setup**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Infrastructure**:
   ```bash
   docker-compose up -d
   ```

## Security Features

- JWT-based admin authentication
- AES-256 encryption for sensitive configuration data
- Nginx configuration validation pipeline with `nginx -t`
- Automatic rollback on health degradation
- Comprehensive audit logging
- Role-based access control (Admin-only)

## Timezone

All scheduling and reporting uses **Asia/Dhaka (UTC+06:00)** timezone, with UTC storage for timestamps.

## Documentation

See the `docs/` directory for detailed documentation:
- [API Documentation](docs/api.md)
- [Operations Runbook](docs/operations.md)
- [Security Guide](docs/security.md)
- [Deployment Guide](docs/deployment.md)

## License

Proprietary - All rights reserved

## Contributors

- [@KhanShadman06](https://github.com/KhanShadman06)
