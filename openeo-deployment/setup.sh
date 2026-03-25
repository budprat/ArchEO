#!/bin/bash
# OpenEO-FastAPI Setup Script
# Run this script after installing Homebrew, GDAL, PostgreSQL, and Docker

set -e

echo "=========================================="
echo "OpenEO-FastAPI Deployment Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check Homebrew
if ! command -v brew &> /dev/null; then
    echo -e "${RED}ERROR: Homebrew not installed${NC}"
    echo "Install with: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi
echo -e "${GREEN}✓ Homebrew installed${NC}"

# Check GDAL
if ! command -v gdal-config &> /dev/null; then
    echo -e "${RED}ERROR: GDAL not installed${NC}"
    echo "Install with: brew install gdal"
    exit 1
fi
echo -e "${GREEN}✓ GDAL installed ($(gdal-config --version))${NC}"

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    echo -e "${RED}ERROR: PostgreSQL not installed${NC}"
    echo "Install with: brew install postgresql@15 && brew services start postgresql@15"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL installed${NC}"

# Setup pyenv
echo -e "\n${YELLOW}Setting up Python environment...${NC}"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

PYTHON_VERSION=$(python --version 2>&1)
echo -e "${GREEN}✓ Python: $PYTHON_VERSION${NC}"

# Setup deployment directory
DEPLOY_DIR="/Users/macbookpro/openeo-deployment"
cd "$DEPLOY_DIR"

# Create/activate virtual environment
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    python -m venv venv
fi
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install openeo-fastapi
echo -e "\n${YELLOW}Installing openeo-fastapi...${NC}"
pip install --upgrade pip
pip install openeo-fastapi
echo -e "${GREEN}✓ openeo-fastapi installed${NC}"

# Create project structure using CLI
if [ ! -d "openeo_app" ]; then
    echo -e "\n${YELLOW}Creating project structure...${NC}"
    openeo_fastapi new "$DEPLOY_DIR/openeo_app"
    echo -e "${GREEN}✓ Project structure created${NC}"
fi

# Create database if not exists
echo -e "\n${YELLOW}Setting up database...${NC}"
if ! psql -lqt | cut -d \| -f 1 | grep -qw openeo; then
    createdb openeo
    echo -e "${GREEN}✓ Database 'openeo' created${NC}"
else
    echo -e "${GREEN}✓ Database 'openeo' already exists${NC}"
fi

# Create .env file
echo -e "\n${YELLOW}Creating environment configuration...${NC}"
cat > "$DEPLOY_DIR/.env" << 'EOF'
export API_DNS="localhost"
export API_TLS="False"
export API_TITLE="OpenEO API"
export API_DESCRIPTION="OpenEO FastAPI Implementation"
export OPENEO_VERSION="1.1.0"
export OPENEO_PREFIX="/openeo/1.1.0"
export OIDC_URL="https://aai.egi.eu/auth/realms/egi"
export OIDC_ORGANISATION="egi"
export STAC_API_URL="https://earth-search.aws.element84.com/v1/"
export POSTGRES_USER="$(whoami)"
export POSTGRES_PASSWORD=""
export POSTGRESQL_HOST="localhost"
export POSTGRESQL_PORT="5432"
export POSTGRES_DB="openeo"
export ALEMBIC_DIR="/Users/macbookpro/openeo-deployment/openeo_app/psql"
EOF
echo -e "${GREEN}✓ Environment file created at $DEPLOY_DIR/.env${NC}"

# Update alembic env.py
echo -e "\n${YELLOW}Configuring Alembic...${NC}"
cat > "$DEPLOY_DIR/openeo_app/psql/alembic/env.py" << 'EOF'
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
EOF
echo -e "${GREEN}✓ Alembic configured${NC}"

# Run database migrations
echo -e "\n${YELLOW}Running database migrations...${NC}"
source "$DEPLOY_DIR/.env"
cd "$DEPLOY_DIR/openeo_app/psql"
python -c "
from alembic import command
from alembic.config import Config
alembic_cfg = Config('alembic.ini')
command.revision(alembic_cfg, 'initial', autogenerate=True)
command.upgrade(alembic_cfg, 'head')
"
echo -e "${GREEN}✓ Database migrations complete${NC}"

# Create startup script
cat > "$DEPLOY_DIR/start.sh" << 'EOF'
#!/bin/bash
cd /Users/macbookpro/openeo-deployment
source .env
source venv/bin/activate
cd openeo_app
echo "Starting OpenEO API server at http://localhost:8000"
echo "API Documentation: http://localhost:8000/openeo/1.1.0/"
uvicorn app:app --reload --host 0.0.0.0 --port 8000
EOF
chmod +x "$DEPLOY_DIR/start.sh"

echo -e "\n${GREEN}=========================================="
echo "Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "To start the server, run:"
echo "  cd $DEPLOY_DIR && ./start.sh"
echo ""
echo "Or manually:"
echo "  source $DEPLOY_DIR/.env"
echo "  source $DEPLOY_DIR/venv/bin/activate"
echo "  cd $DEPLOY_DIR/openeo_app"
echo "  uvicorn app:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "API Endpoints:"
echo "  - Root: http://localhost:8000/"
echo "  - Capabilities: http://localhost:8000/openeo/1.1.0/"
echo "  - Collections: http://localhost:8000/openeo/1.1.0/collections"
echo "  - Processes: http://localhost:8000/openeo/1.1.0/processes"
