#!/bin/bash
# Idea Engine App - Quick Setup Script

echo "🚀 Idea Engine App Setup"
echo "========================"

# Check prerequisites
echo "Checking prerequisites..."

# Check for PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL not found. Please install PostgreSQL first."
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+ first."
    exit 1
fi

# Check for n8n
if ! command -v n8n &> /dev/null; then
    echo "❌ n8n not found. Installing n8n globally..."
    npm install -g n8n
fi

echo "✅ All prerequisites found!"

# Database setup
echo ""
echo "Setting up PostgreSQL database..."
read -p "Enter PostgreSQL username (default: postgres): " PG_USER
PG_USER=${PG_USER:-postgres}

read -sp "Enter PostgreSQL password: " PG_PASS
echo ""

# Create database
PGPASSWORD=$PG_PASS createdb -U $PG_USER idea_engine 2>/dev/null || echo "Database might already exist"

# Import schema
echo "Importing database schema..."
PGPASSWORD=$PG_PASS psql -U $PG_USER -d idea_engine -f database/schema.sql

# Create .env file
echo ""
echo "Creating .env configuration..."
cat > .env << EOF
# n8n Configuration
N8N_WEBHOOK_BASE_URL=http://localhost:5678
N8N_PORT=5678

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=idea_engine
POSTGRES_USER=$PG_USER
POSTGRES_PASSWORD=$PG_PASS

# Google Cloud Configuration (Please fill these in)
GOOGLE_CLOUD_PROJECT_ID=
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_SERVICE_ACCOUNT_EMAIL=
GOOGLE_PRIVATE_KEY=
GOOGLE_APPLICATION_CREDENTIALS=

# Other API Keys
PRODUCTHUNT_API_KEY=
SERP_API_KEY=
GITHUB_TOKEN=
NETLIFY_TOKEN=

# Webhooks
NOTIFICATION_WEBHOOK_URL=http://localhost:5678/webhook/notify
ERROR_WEBHOOK_URL=http://localhost:5678/webhook/error
EOF

echo "✅ Configuration file created!"

# Create n8n data directory
mkdir -p ~/.n8n

# Summary
echo ""
echo "✨ Setup Complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API keys"
echo "2. Start n8n: n8n start"
echo "3. Access n8n at: http://localhost:5678"
echo "4. Import workflows from the workflows/ directory"
echo "5. Configure credentials in n8n UI"
echo ""
echo "For detailed instructions, see README.md"
