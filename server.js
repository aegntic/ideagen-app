/**
 * promptre.quest App Server - Google Cloud Version
 * AI-Powered Business Idea Quest with Vertex AI
 */

// Load environment variables
require('dotenv').config();

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
const winston = require('winston');
const path = require('path');
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
const ideaService = require('./src/services/ideaService');

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

// Serve static files
app.use(express.static('public'));

// Root route - serve the frontend
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use('/api/', limiter);

// Secret Manager client
const secretClient = new SecretManagerServiceClient();
let secrets = {};

// Initialize application
async function initializeApp() {
  try {
    logger.info('Initializing promptre.quest App...');

    // Load secrets from Secret Manager
    await loadSecrets();

    // Initialize the idea service (database + Vertex AI)
    await ideaService.initialize();

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


// Routes
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: '2.0.0',
    features: {
      ideaService: !!ideaService.isInitialized,
      database: !!ideaService.database?.isConnected,
      memoryFallback: !!ideaService.database?.useMemoryFallback,
      secrets: Object.keys(secrets).length > 0
    }
  });
});

// Generate ideas endpoint
app.post('/api/ideas/generate', async (req, res) => {
  try {
    const { sources, count = 10, trends } = req.body;

    logger.info(`Generating ${count} ideas from sources:`, sources);

    const ideas = await ideaService.generateIdeas({ sources, count, trends });

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
    const { ideaId } = req.body;

    if (!ideaId) {
      return res.status(400).json({
        error: 'Idea ID is required'
      });
    }

    logger.info(`Validating idea: ${ideaId}`);

    const validation = await ideaService.validateIdea(ideaId);

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

    if (!prompt) {
      return res.status(400).json({
        error: 'Prompt is required'
      });
    }

    const content = await ideaService.generateContent(prompt, contentType);

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

    if (!text) {
      return res.status(400).json({
        error: 'Text is required'
      });
    }

    const analysis = await ideaService.quickAnalysis(text, analysisType);

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

// Get ideas endpoint
app.get('/api/ideas', async (req, res) => {
  try {
    const filters = {
      status: req.query.status,
      category: req.query.category,
      source: req.query.source,
      limit: parseInt(req.query.limit) || 50,
      offset: parseInt(req.query.offset) || 0,
      orderBy: req.query.orderBy || 'created_at',
      orderDirection: req.query.orderDirection || 'DESC'
    };

    const ideas = await ideaService.getIdeas(filters);

    res.json({
      success: true,
      data: {
        ideas,
        count: ideas.length,
        filters
      }
    });
  } catch (error) {
    logger.error('Error fetching ideas:', error);
    res.status(500).json({
      error: 'Failed to fetch ideas',
      details: error.message
    });
  }
});

// Get single idea endpoint
app.get('/api/ideas/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const idea = await ideaService.getIdeaById(id);

    if (!idea) {
      return res.status(404).json({
        error: 'Idea not found'
      });
    }

    res.json({
      success: true,
      data: { idea }
    });
  } catch (error) {
    logger.error('Error fetching idea:', error);
    res.status(500).json({
      error: 'Failed to fetch idea',
      details: error.message
    });
  }
});

// Select idea endpoint
app.post('/api/ideas/:id/select', async (req, res) => {
  try {
    const { id } = req.params;
    const result = await ideaService.selectIdea(id);

    res.json({
      success: true,
      data: {
        message: 'Idea selected successfully',
        result
      }
    });
  } catch (error) {
    logger.error('Error selecting idea:', error);
    res.status(500).json({
      error: 'Failed to select idea',
      details: error.message
    });
  }
});

// Semantic search endpoint
app.post('/api/search/semantic', async (req, res) => {
  try {
    const { query, filters = {}, limit = 10, threshold = 0.3 } = req.body;

    if (!query || query.trim().length === 0) {
      return res.status(400).json({
        error: 'Search query is required'
      });
    }

    logger.info(`Performing semantic search for: "${query}"`);

    const results = await ideaService.semanticSearch(query, {
      filters,
      limit,
      threshold
    });

    res.json({
      success: true,
      data: {
        query,
        results,
        count: results.length,
        searchedAt: new Date().toISOString()
      }
    });
  } catch (error) {
    logger.error('Error in semantic search:', error);
    res.status(500).json({
      error: 'Failed to perform semantic search',
      details: error.message
    });
  }
});

// Vector similarity endpoint
app.post('/api/search/similarity', async (req, res) => {
  try {
    const { ideaId, limit = 5, threshold = 0.3 } = req.body;

    if (!ideaId) {
      return res.status(400).json({
        error: 'Idea ID is required'
      });
    }

    logger.info(`Finding similar ideas for: ${ideaId}`);

    const similarIdeas = await ideaService.findSimilarIdeas(ideaId, {
      limit,
      threshold
    });

    res.json({
      success: true,
      data: {
        ideaId,
        similarIdeas,
        count: similarIdeas.length,
        searchedAt: new Date().toISOString()
      }
    });
  } catch (error) {
    logger.error('Error finding similar ideas:', error);
    res.status(500).json({
      error: 'Failed to find similar ideas',
      details: error.message
    });
  }
});

// Search suggestions endpoint
app.get('/api/search/suggestions', async (req, res) => {
  try {
    const { q: query = '', limit = 5 } = req.query;

    if (query.length < 2) {
      return res.json({
        success: true,
        data: { suggestions: [] }
      });
    }

    const suggestions = await ideaService.getSearchSuggestions(query, { limit });

    res.json({
      success: true,
      data: { suggestions }
    });
  } catch (error) {
    logger.error('Error getting search suggestions:', error);
    res.status(500).json({
      error: 'Failed to get search suggestions',
      details: error.message
    });
  }
});

// Search analytics endpoint
app.get('/api/search/analytics', async (req, res) => {
  try {
    const analytics = await ideaService.getSearchAnalytics();

    res.json({
      success: true,
      data: { analytics }
    });
  } catch (error) {
    logger.error('Error fetching search analytics:', error);
    res.status(500).json({
      error: 'Failed to fetch search analytics',
      details: error.message
    });
  }
});

// Get stats endpoint
app.get('/api/stats', async (req, res) => {
  try {
    const stats = await ideaService.getStats();

    res.json({
      success: true,
      data: { stats }
    });
  } catch (error) {
    logger.error('Error fetching stats:', error);
    res.status(500).json({
      error: 'Failed to fetch stats',
      details: error.message
    });
  }
});

// API documentation endpoint
app.get('/api/docs', (req, res) => {
  res.json({
    title: 'promptre.quest API Documentation',
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
    logger.info(`promptre.quest server running on port ${PORT}`);
    logger.info(`Health check: http://localhost:${PORT}/health`);
    logger.info(`API docs: http://localhost:${PORT}/api/docs`);
    logger.info(`Powered by Gemini 2.5 Pro & Flash models`);
  });
}).catch(error => {
  logger.error('Failed to start server:', error);
  process.exit(1);
});

module.exports = app;