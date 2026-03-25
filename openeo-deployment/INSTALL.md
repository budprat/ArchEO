# OpenEO-FastAPI Deployment Guide

## Prerequisites (Require Admin Access)

### Option 1: Docker Deployment (RECOMMENDED)

```bash
# 1. Install Homebrew (requires admin password)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Add Homebrew to PATH (for Apple Silicon Macs)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# 3. Install Docker
brew install --cask docker

# 4. Launch Docker Desktop from Applications
open /Applications/Docker.app

# 5. Wait for Docker to start, then verify
docker --version
```

### Option 2: Native Installation

```bash
# 1. Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Add Homebrew to PATH
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# 3. Install GDAL (required for openeo-processes-dask)
brew install gdal

# 4. Install PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# 5. Create database
createdb openeo
```

---

## Deployment Steps (After Prerequisites)

### Step 1: Setup Python Environment

```bash
# Python 3.11 is already installed via pyenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Verify Python version
python --version  # Should show 3.11.x
```

### Step 2: Install openeo-fastapi

```bash
cd /Users/macbookpro/openeo-deployment
source venv/bin/activate
pip install openeo-fastapi
```

### Step 3: Create Project Structure

```bash
# Use the CLI to create project structure
openeo_fastapi new /Users/macbookpro/openeo-deployment/openeo_app
```

### Step 4: Set Environment Variables

Create `/Users/macbookpro/openeo-deployment/.env`:

```bash
export API_DNS="localhost"
export API_TLS="False"
export API_TITLE="OpenEO API"
export API_DESCRIPTION="OpenEO FastAPI Implementation"
export OPENEO_VERSION="1.1.0"
export OPENEO_PREFIX="/openeo/1.1.0"

# OIDC Configuration (use EGI Check-in for testing)
export OIDC_URL="https://aai.egi.eu/auth/realms/egi"
export OIDC_ORGANISATION="egi"

# STAC Catalogue (using AWS Earth Search as example)
export STAC_API_URL="https://earth-search.aws.element84.com/v1/"

# PostgreSQL Configuration
export POSTGRES_USER="$(whoami)"
export POSTGRES_PASSWORD=""
export POSTGRESQL_HOST="localhost"
export POSTGRESQL_PORT="5432"
export POSTGRES_DB="openeo"

# Alembic Directory
export ALEMBIC_DIR="/Users/macbookpro/openeo-deployment/openeo_app/psql"
```

### Step 5: Configure Alembic

Edit `/Users/macbookpro/openeo-deployment/openeo_app/psql/alembic/env.py`:

```python
from logging.config import fileConfig
from os import environ

from alembic import context
from sqlalchemy import engine_from_config, pool

from openeo_app.psql.models import metadata

config = context.config
config.set_main_option(
    "sqlalchemy.url",
    f"postgresql://{environ.get('POSTGRES_USER')}:{environ.get('POSTGRES_PASSWORD')}"
    f"@{environ.get('POSTGRESQL_HOST')}:{environ.get('POSTGRESQL_PORT')}"
    f"/{environ.get('POSTGRES_DB')}",
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Step 6: Run Database Migrations

```bash
source /Users/macbookpro/openeo-deployment/.env
cd /Users/macbookpro/openeo-deployment/openeo_app
python -m revise
```

### Step 7: Start the Server

```bash
source /Users/macbookpro/openeo-deployment/.env
cd /Users/macbookpro/openeo-deployment/openeo_app
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Step 8: Verify Deployment

Open in browser:
- http://localhost:8000/ - API Root
- http://localhost:8000/openeo/1.1.0/ - OpenEO Capabilities
- http://localhost:8000/openeo/1.1.0/collections - STAC Collections

---

## Docker Deployment (Alternative)

If using Docker, you can use the devcontainer provided in the repository:

```bash
cd /Users/macbookpro/openeo-fastapi
docker-compose -f .devcontainer/docker-compose.yml up -d
```

Or create a custom docker-compose.yml:

```yaml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - API_DNS=localhost
      - API_TLS=False
      - API_TITLE=OpenEO API
      - API_DESCRIPTION=OpenEO FastAPI Implementation
      - OIDC_URL=https://aai.egi.eu/auth/realms/egi
      - OIDC_ORGANISATION=egi
      - STAC_API_URL=https://earth-search.aws.element84.com/v1/
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRESQL_HOST=db
      - POSTGRESQL_PORT=5432
      - POSTGRES_DB=openeo
      - ALEMBIC_DIR=/app/psql
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=openeo
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Quick Test Commands

```bash
# Test capabilities endpoint
curl http://localhost:8000/openeo/1.1.0/

# Test collections endpoint
curl http://localhost:8000/openeo/1.1.0/collections

# Test processes endpoint
curl http://localhost:8000/openeo/1.1.0/processes
```
