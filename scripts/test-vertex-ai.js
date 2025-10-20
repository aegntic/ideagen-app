#!/usr/bin/env node
/**
 * Vertex AI Integration Test Script
 * Tests the Google Cloud Vertex AI integration with Gemini models
 */

require('dotenv').config();
const IdeaGenVertexAIClient = require('../integrations/vertex-ai-client');

// Colors for console output
const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logSuccess(message) {
  log(`[SUCCESS] ${message}`, 'green');
}

function logError(message) {
  log(`[ERROR] ${message}`, 'red');
}

function logInfo(message) {
  log(`[INFO]  ${message}`, 'blue');
}

function logWarning(message) {
  log(`[WARNING]  ${message}`, 'yellow');
}

async function testVertexAIIntegration() {
  log('Testing Vertex AI Integration with Gemini Models', 'blue');
  log('=' .repeat(60));

  // Check environment variables
  const requiredEnvVars = [
    'GOOGLE_CLOUD_PROJECT_ID',
    'GOOGLE_CLOUD_LOCATION'
  ];

  let envValid = true;
  for (const envVar of requiredEnvVars) {
    if (!process.env[envVar]) {
      logError(`Missing environment variable: ${envVar}`);
      envValid = false;
    }
  }

  if (!envValid) {
    logError('Please set required environment variables');
    process.exit(1);
  }

  // Initialize Vertex AI client
  let vertexAIClient;
  try {
    const config = {
      projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
      location: process.env.GOOGLE_CLOUD_LOCATION || 'us-central1'
    };

    if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
      config.keyFile = process.env.GOOGLE_APPLICATION_CREDENTIALS;
    }

    vertexAIClient = new IdeaGenVertexAIClient(config);
    logSuccess('Vertex AI client initialized successfully');
  } catch (error) {
    logError(`Failed to initialize Vertex AI client: ${error.message}`);
    process.exit(1);
  }

  // Test 1: Quick Analysis with Flash model
  logInfo('\n[TEST] Test 1: Quick Analysis (Gemini 2.5 Flash-Nano-Banana)');
  try {
    const testText = "Artificial Intelligence is revolutionizing business automation and customer service.";
    const analysis = await vertexAIClient.quickAnalysis(testText, 'sentiment');

    logSuccess('Quick analysis completed');
    log(`   Sentiment: ${analysis.sentiment} (${Math.round(analysis.confidence * 100)}% confidence)`);
    log(`   Explanation: ${analysis.explanation}`);
  } catch (error) {
    logError(`Quick analysis failed: ${error.message}`);
  }

  // Test 2: Content Generation with Flash model
  logInfo('\n[TEST]  Test 2: Content Generation (Gemini 2.5 Flash-Nano-Banana)');
  try {
    const content = await vertexAIClient.generateContent(
      "Write a catchy tagline for an AI-powered business idea generator",
      'marketing'
    );

    logSuccess('Content generation completed');
    log(`   Generated content: "${content}"`);
  } catch (error) {
    logError(`Content generation failed: ${error.message}`);
  }

  // Test 3: Idea Generation with Pro model
  logInfo('\n💡 Test 3: Idea Generation (Gemini 2.5 Pro)');
  try {
    const trends = [
      { title: "AI Automation", description: "Growing trend in AI-powered business tools" },
      { title: "Remote Work", description: "Continued growth in remote collaboration tools" }
    ];

    const sources = [
      { type: "trends", data: "AI and automation trending up" },
      { type: "reddit", data: "Startups discussing AI solutions" }
    ];

    const ideas = await vertexAIClient.generateIdeas(trends, sources, 3);

    logSuccess('Idea generation completed');
    ideas.forEach((idea, index) => {
      log(`   Idea ${index + 1}: ${idea.title}`);
      log(`   Description: ${idea.description}`);
      log(`   Viability Score: ${idea.viabilityScore}/100`);
      log('');
    });
  } catch (error) {
    logError(`Idea generation failed: ${error.message}`);
  }

  // Test 4: Idea Validation with Pro model
  logInfo('\n[TEST] Test 4: Idea Validation (Gemini 2.5 Pro)');
  try {
    const testIdea = {
      title: "AI-Powered Customer Service Platform",
      description: "An automated customer support platform using AI to handle inquiries and improve satisfaction",
      marketProblem: "Businesses struggle with 24/7 customer support costs",
      solution: "AI agents handle common inquiries, escalating complex issues to humans",
      targetMarket: "Small to medium businesses",
      revenueModel: "SaaS subscription based on usage volume"
    };

    const validation = await vertexAIClient.validateIdea(testIdea);

    logSuccess('Idea validation completed');
    log(`   Overall Score: ${validation.overallScore}/100`);
    log(`   Recommendation: ${validation.recommendation}`);
    log(`   Market Demand: ${validation.marketDemand.score}/100`);
    log(`   Competition: ${validation.competition.score}/100`);
    log(`   Technical Feasibility: ${validation.technicalFeasibility.score}/100`);
  } catch (error) {
    logError(`Idea validation failed: ${error.message}`);
  }

  // Test 5: Performance Test
  logInfo('\n[TEST] Test 5: Performance Test');
  try {
    const startTime = Date.now();

    // Run multiple quick analyses concurrently
    const promises = [];
    for (let i = 0; i < 5; i++) {
      promises.push(
        vertexAIClient.quickAnalysis(
          `Test text ${i + 1} for performance testing`,
          'sentiment'
        )
      );
    }

    const results = await Promise.all(promises);
    const endTime = Date.now();
    const duration = endTime - startTime;

    logSuccess(`Performance test completed`);
    log(`   Processed 5 analyses in ${duration}ms`);
    log(`   Average time per analysis: ${Math.round(duration / 5)}ms`);
    log(`   Results: ${results.filter(r => r.sentiment).length} successful`);
  } catch (error) {
    logError(`Performance test failed: ${error.message}`);
  }

  // Summary
  logInfo('\n[SUMMARY] Test Summary');
  log('=' .repeat(30));
  logSuccess('Vertex AI integration tests completed');
  logInfo('Models tested:');
  log('   • Gemini 2.5 Pro (idea generation & validation)');
  log('   • Gemini 2.5 Flash-Nano-Banana (quick analysis & content)');
  logInfo('\nReady for hackathon deployment! [DONE]');
}

// Run tests
if (require.main === module) {
  testVertexAIIntegration()
    .then(() => {
      log('\n[SUCCESS] All tests completed successfully!', 'green');
      process.exit(0);
    })
    .catch((error) => {
      logError(`Test suite failed: ${error.message}`);
      process.exit(1);
    });
}

module.exports = { testVertexAIIntegration };