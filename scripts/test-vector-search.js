/**
 * Test script for vector search functionality
 * This script tests the vector database integration and semantic search
 */

const path = require('path');

// Set environment variables for testing
process.env.NODE_ENV = 'development';
process.env.VECTOR_DB_TYPE = 'memory'; // Use memory fallback for testing
process.env.USE_MEMORY_FALLBACK = 'true';

// Load the services
const ideaService = require('../src/services/ideaService');
const vectorService = require('../src/services/vectorService');

async function testVectorSearch() {
  console.log('🧪 Testing Vector Search Integration...\n');

  try {
    // Initialize services
    console.log('📡 Initializing services...');
    await ideaService.initialize();
    console.log('✅ Services initialized successfully\n');

    // Test 1: Generate some sample ideas
    console.log('🚀 Generating sample ideas...');
    const sampleIdeas = await ideaService.generateIdeas({
      sources: ['mock'],
      count: 5,
      categories: ['AI', 'FinTech', 'HealthTech', 'SaaS', 'E-commerce']
    });

    console.log(`✅ Generated ${sampleIdeas.length} sample ideas`);
    sampleIdeas.forEach((idea, index) => {
      console.log(`   ${index + 1}. ${idea.title} (${idea.category})`);
    });
    console.log();

    // Test 2: Semantic search
    console.log('🔍 Testing semantic search...');
    const searchQueries = [
      'artificial intelligence automation',
      'financial technology',
      'healthcare solutions',
      'online shopping platform'
    ];

    for (const query of searchQueries) {
      console.log(`\n📝 Query: "${query}"`);
      const results = await ideaService.semanticSearch(query, {
        limit: 3,
        threshold: 0.1
      });

      if (results.length > 0) {
        console.log(`   Found ${results.length} results:`);
        results.forEach((result, index) => {
          console.log(`   ${index + 1}. ${result.title}`);
          console.log(`      Similarity: ${result.similarityPercentage}%`);
          console.log(`      Category: ${result.category}`);
        });
      } else {
        console.log('   No results found');
      }
    }

    // Test 3: Find similar ideas
    console.log('\n🔄 Testing similar ideas search...');
    if (sampleIdeas.length > 0) {
      const firstIdea = sampleIdeas[0];
      console.log(`📋 Finding ideas similar to: "${firstIdea.title}"`);

      const similarIdeas = await ideaService.findSimilarIdeas(firstIdea.id, {
        limit: 3,
        threshold: 0.1
      });

      if (similarIdeas.length > 0) {
        console.log(`   Found ${similarIdeas.length} similar ideas:`);
        similarIdeas.forEach((idea, index) => {
          console.log(`   ${index + 1}. ${idea.title} (${idea.similarityPercentage}% similar)`);
        });
      } else {
        console.log('   No similar ideas found');
      }
    }

    // Test 4: Vector service stats
    console.log('\n📊 Vector Service Statistics:');
    const stats = await vectorService.getStats();
    console.log(`   Primary Vector DB: ${stats.primaryVectorDB}`);
    console.log(`   Memory Fallback: ${stats.useMemoryFallback}`);
    console.log(`   Memory Store Size: ${stats.memoryStoreSize}`);
    console.log(`   Initialized: ${stats.initialized}`);

    // Test 5: Search suggestions
    console.log('\n💡 Testing search suggestions...');
    const suggestions = await ideaService.getSearchSuggestions('ai', { limit: 5 });
    if (suggestions.length > 0) {
      console.log('   Suggestions for "ai":');
      suggestions.forEach((suggestion, index) => {
        console.log(`   ${index + 1}. ${suggestion}`);
      });
    } else {
      console.log('   No suggestions found');
    }

    // Test 6: Search analytics
    console.log('\n📈 Search Analytics:');
    const analytics = await ideaService.getSearchAnalytics();
    console.log(`   Total Ideas: ${analytics.totalIdeas}`);
    console.log(`   Average Score: ${analytics.averageScore}`);
    console.log('   Categories:');
    Object.entries(analytics.categories).forEach(([category, count]) => {
      console.log(`     ${category}: ${count}`);
    });

    console.log('\n🎉 All tests completed successfully!');

  } catch (error) {
    console.error('❌ Test failed:', error);
    process.exit(1);
  }
}

// Run the test
if (require.main === module) {
  testVectorSearch()
    .then(() => {
      console.log('\n✨ Vector search integration test completed');
      process.exit(0);
    })
    .catch(error => {
      console.error('💥 Test failed:', error);
      process.exit(1);
    });
}

module.exports = testVectorSearch;