/**
 * IdeaGen App Server - Google Cloud Version
 * Automated Business Idea Pipeline with Vertex AI
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
const winston = require('winston');
const path = require('path');
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
const IdeaGenVertexAIClient = require('./integrations/vertex-ai-client');

// Initialize Express app
const app = express();
const PORT = process.env.PORT || 8080;

// Configure Winston logging
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    })
  ]
});

// Middleware
app.use(helmet());
app.use(compression());
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use('/api/', limiter);

// Secret Manager client
const secretClient = new SecretManagerServiceClient();
let secrets = {};

// Vertex AI client
let vertexAIClient = null;

// Initialize application
async function initializeApp() {
  try {
    logger.info('Initializing IdeaGen App...');

    // Load secrets from Secret Manager
    await loadSecrets();

    // Initialize Vertex AI client
    await initializeVertexAI();

    logger.info('Application initialized successfully');
  } catch (error) {
    logger.error('Failed to initialize application:', error);
    process.exit(1);
  }
}

// Load secrets from Google Secret Manager
async function loadSecrets() {
  try {
    const secretNames = [
      'idea-gen-db-password',
      'idea-gen-google-credentials',
      'idea-gen-api-keys'
    ];

    for (const secretName of secretNames) {
      try {
        const [version] = await secretClient.accessSecretVersion({
          name: `projects/${process.env.GOOGLE_CLOUD_PROJECT_ID}/secrets/${secretName}/versions/latest`
        });

        const payload = version.payload.data.toString();

        if (secretName === 'idea-gen-api-keys') {
          secrets.apiKeys = JSON.parse(payload);
        } else {
          secrets[secretName.replace('idea-gen-', '')] = payload;
        }

        logger.info(`Loaded secret: ${secretName}`);
      } catch (error) {
        logger.warn(`Failed to load secret ${secretName}:`, error.message);
      }
    }
  } catch (error) {
    logger.error('Error loading secrets:', error);
    throw error;
  }
}

// Initialize Vertex AI client
async function initializeVertexAI() {
  try {
    const config = {
      projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
      location: process.env.GOOGLE_CLOUD_LOCATION || 'us-central1'
    };

    // Use service account credentials if available
    if (secrets.googleCredentials) {
      // Write credentials to temporary file
      const fs = require('fs');
      const credentialsPath = '/tmp/google-credentials.json';
      fs.writeFileSync(credentialsPath, secrets.googleCredentials);
      config.keyFile = credentialsPath;
    }

    vertexAIClient = new IdeaGenVertexAIClient(config);
    logger.info('Vertex AI client initialized');
  } catch (error) {
    logger.error('Failed to initialize Vertex AI client:', error);
    throw error;
  }
}

// Routes
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: '2.0.0',
    features: {
      vertexAI: !!vertexAIClient,
      secrets: Object.keys(secrets).length > 0
    }
  });
});

// Generate ideas endpoint
app.post('/api/ideas/generate', async (req, res) => {
  try {
    const { sources, count = 10, trends } = req.body;

    if (!vertexAIClient) {
      return res.status(503).json({
        error: 'Vertex AI client not initialized'
      });
    }

    logger.info(`Generating ${count} ideas from sources:`, sources);

    const ideas = await vertexAIClient.generateIdeas(trends || [], sources || [], count);

    res.json({
      success: true,
      data: {
        ideas,
        generatedAt: new Date().toISOString(),
        count: ideas.length
      }
    });
  } catch (error) {
    logger.error('Error generating ideas:', error);
    res.status(500).json({
      error: 'Failed to generate ideas',
      details: error.message
    });
  }
});

// Validate idea endpoint
app.post('/api/ideas/validate', async (req, res) => {
  try {
    const { idea } = req.body;

    if (!vertexAIClient) {
      return res.status(503).json({
        error: 'Vertex AI client not initialized'
      });
    }

    if (!idea) {
      return res.status(400).json({
        error: 'Idea is required'
      });
    }

    logger.info(`Validating idea: ${idea.title}`);

    const validation = await vertexAIClient.validateIdea(idea);

    res.json({
      success: true,
      data: {
        validation,
        validatedAt: new Date().toISOString()
      }
    });
  } catch (error) {
    logger.error('Error validating idea:', error);
    res.status(500).json({
      error: 'Failed to validate idea',
      details: error.message
    });
  }
});

// Generate content endpoint
app.post('/api/content/generate', async (req, res) => {
  try {
    const { prompt, contentType = 'marketing' } = req.body;

    if (!vertexAIClient) {
      return res.status(503).json({
        error: 'Vertex AI client not initialized'
      });
    }

    if (!prompt) {
      return res.status(400).json({
        error: 'Prompt is required'
      });
    }

    const content = await vertexAIClient.generateContent(prompt, contentType);

    res.json({
      success: true,
      data: {
        content,
        contentType,
        generatedAt: new Date().toISOString()
      }
    });
  } catch (error) {
    logger.error('Error generating content:', error);
    res.status(500).json({
      error: 'Failed to generate content',
      details: error.message
    });
  }
});

// Quick analysis endpoint
app.post('/api/analysis/quick', async (req, res) => {
  try {
    const { text, analysisType = 'sentiment' } = req.body;

    if (!vertexAIClient) {
      return res.status(503).json({
        error: 'Vertex AI client not initialized'
      });
    }

    if (!text) {
      return res.status(400).json({
        error: 'Text is required'
      });
    }

    const analysis = await vertexAIClient.quickAnalysis(text, analysisType);

    res.json({
      success: true,
      data: {
        analysis,
        analysisType,
        analyzedAt: new Date().toISOString()
      }
    });
  } catch (error) {
    logger.error('Error in quick analysis:', error);
    res.status(500).json({
      error: 'Failed to perform analysis',
      details: error.message
    });
  }
});

// Test Vertex AI connection
app.post('/api/test/vertex-ai', async (req, res) => {
  try {
    if (!vertexAIClient) {
      return res.status(503).json({
        error: 'Vertex AI client not initialized'
      });
    }

    // Simple test
    const testAnalysis = await vertexAIClient.quickAnalysis(
      'This is a test of the Vertex AI integration.',
      'sentiment'
    );

    res.json({
      success: true,
      data: {
        vertexAI: 'connected',
        models: {
          pro: 'gemini-2.5-pro',
          flash: 'gemini-2.5-flash-nano-banana'
        },
        testResult: testAnalysis
      }
    });
  } catch (error) {
    logger.error('Vertex AI test failed:', error);
    res.status(500).json({
      error: 'Vertex AI test failed',
      details: error.message
    });
  }
});

// API documentation endpoint
app.get('/api/docs', (req, res) => {
  res.json({
    title: 'IdeaGen API Documentation',
    version: '2.0.0',
    endpoints: {
      'GET /health': 'Health check endpoint',
      'POST /api/ideas/generate': 'Generate business ideas using Vertex AI',
      'POST /api/ideas/validate': 'Validate and score business ideas',
      'POST /api/content/generate': 'Generate marketing/technical content',
      'POST /api/analysis/quick': 'Quick text analysis',
      'POST /api/test/vertex-ai': 'Test Vertex AI connection'
    },
    models: {
      'gemini-2.5-pro': 'High-performance model for complex tasks',
      'gemini-2.5-flash-nano-banana': 'Fast model for quick responses'
    }
  });
});

// Error handling middleware
app.use((error, req, res, next) => {
  logger.error('Unhandled error:', error);
  res.status(500).json({
    error: 'Internal server error',
    requestId: req.id
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: 'Endpoint not found',
    path: req.originalUrl
  });
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('SIGINT received, shutting down gracefully');
  process.exit(0);
});

// Start server
initializeApp().then(() => {
  app.listen(PORT, () => {
    logger.info(`IdeaGen server running on port ${PORT}`);
    logger.info(`Health check: http://localhost:${PORT}/health`);
    logger.info(`API docs: http://localhost:${PORT}/api/docs`);
    logger.info(`Powered by Gemini 2.5 Pro & Flash models`);
  });
}).catch(error => {
  logger.error('Failed to start server:', error);
  process.exit(1);
});

module.exports = app;