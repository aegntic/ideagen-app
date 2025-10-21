/**
 * Idea Generation Service
 * Core business logic for generating, validating, and managing ideas
 */

const db = require('../database/database');
const PromptreQuestVertexAIClient = require('../../integrations/vertex-ai-client');
const vectorService = require('./vectorService');

class IdeaService {
  constructor() {
    this.vertexAI = null;
    this.isInitialized = false;
  }

  async initialize() {
    try {
      // Initialize database
      await db.initialize();

      // Initialize Vector Service
      await vectorService.initialize();

      // Initialize Vertex AI
      if (process.env.GOOGLE_CLOUD_PROJECT_ID) {
        const config = {
          projectId: process.env.GOOGLE_CLOUD_PROJECT_ID,
          location: process.env.GOOGLE_CLOUD_LOCATION || 'us-central1'
        };

        if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
          config.keyFile = process.env.GOOGLE_APPLICATION_CREDENTIALS;
        }

        this.vertexAI = new PromptreQuestVertexAIClient(config);
        console.log('Vertex AI client initialized');
      }

      this.isInitialized = true;
      console.log('IdeaService initialized successfully');
      return true;
    } catch (error) {
      console.error('Failed to initialize IdeaService:', error);
      throw error;
    }
  }

  async generateIdeas(options = {}) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    const {
      sources = ['trends', 'reddit'],
      count = 10,
      trends = [],
      categories = ['SaaS', 'AI', 'FinTech', 'HealthTech', 'E-commerce']
    } = options;

    try {
      console.log(`Generating ${count} ideas from sources:`, sources);

      // Generate sample trends if none provided
      const sampleTrends = trends.length > 0 ? trends : [
        { title: "AI-Powered Automation", description: "Businesses are rapidly adopting AI for workflow automation" },
        { title: "Remote Work Tools", description: "Continued demand for better remote collaboration" },
        { title: "Sustainable Technology", description: "Growing focus on climate tech and sustainability" },
        { title: "FinTech Innovation", description: "Digital banking and payment solutions" },
        { title: "Health Technology", description: "AI-driven healthcare solutions" }
      ];

      const sourceData = sources.map(source => ({
        type: source,
        data: `Sample data from ${source}`
      }));

      // Generate ideas using Vertex AI with fallback
      let ideas = [];
      if (this.vertexAI) {
        try {
          ideas = await this.vertexAI.generateIdeas(sampleTrends, sourceData, count);
        } catch (error) {
          console.warn('Vertex AI failed, falling back to mock ideas:', error.message);
          ideas = this.generateMockIdeas(count, categories);
        }
      } else {
        // Fallback to mock ideas if Vertex AI is not available
        ideas = this.generateMockIdeas(count, categories);
      }

      // Store ideas in database
      const storedIdeas = [];
      for (const idea of ideas) {
        try {
          const storedIdea = await db.createIdea({
            title: idea.title,
            description: idea.description,
            category: idea.category || idea.tags?.[0] || 'Technology',
            source: 'ai_generated',
            marketSizeEstimate: idea.marketSizeEstimate || null,
            validationScore: idea.viabilityScore || null,
            metadata: {
              tags: idea.tags || [],
              targetMarket: idea.targetMarket || '',
              revenueModel: idea.revenueModel || '',
              competitiveAdvantage: idea.competitiveAdvantage || '',
              trends: idea.trendingTopics || [],
              estimatedTimeToMarket: idea.estimatedTimeToMarket || '',
              requiredResources: idea.requiredResources || [],
              createdAt: new Date().toISOString()
            }
          });

          // Store idea in vector database for semantic search
          try {
            await vectorService.storeIdea({
              id: storedIdea.id,
              title: storedIdea.title,
              description: storedIdea.description,
              category: storedIdea.category,
              metadata: storedIdea.metadata
            });
          } catch (vectorError) {
            console.warn('Failed to store idea in vector database:', vectorError.message);
            // Continue even if vector storage fails
          }

          storedIdeas.push(storedIdea);
        } catch (error) {
          console.error('Error storing idea:', error);
          // Continue with other ideas even if one fails
        }
      }

      console.log(`Successfully generated and stored ${storedIdeas.length} ideas`);
      return storedIdeas;
    } catch (error) {
      console.error('Error in generateIdeas:', error);
      throw error;
    }
  }

  generateMockIdeas(count, categories) {
    const mockIdeas = [];
    const ideaTemplates = [
      {
        title: "AI-Powered Customer Support Platform",
        description: "Automated customer service solution using AI to handle inquiries and improve satisfaction",
        category: "SaaS",
        tags: ["AI", "Customer Service", "Automation"]
      },
      {
        title: "Sustainable Supply Chain Tracker",
        description: "Real-time tracking platform for monitoring environmental impact of supply chains",
        category: "Sustainability",
        tags: ["Sustainability", "Logistics", "Tracking"]
      },
      {
        title: "Remote Team Collaboration Hub",
        description: "Integrated platform for remote teams to collaborate, communicate, and manage projects",
        category: "SaaS",
        tags: ["Remote Work", "Collaboration", "Productivity"]
      },
      {
        title: "AI Financial Advisor",
        description: "Personalized financial advice platform using AI to optimize investments and savings",
        category: "FinTech",
        tags: ["AI", "Finance", "Investment"]
      },
      {
        title: "Health Monitoring Wearable",
        description: "Advanced wearable device for continuous health monitoring and early disease detection",
        category: "HealthTech",
        tags: ["Health", "Wearable", "Monitoring"]
      }
    ];

    for (let i = 0; i < Math.min(count, ideaTemplates.length); i++) {
      const template = ideaTemplates[i];
      mockIdeas.push({
        ...template,
        viabilityScore: Math.floor(Math.random() * 30) + 70, // 70-100
        marketSizeEstimate: Math.floor(Math.random() * 900000000) + 100000000, // 100M-1B
        targetMarket: "Small to Medium Businesses",
        revenueModel: "SaaS Subscription",
        competitiveAdvantage: "AI-powered automation with superior accuracy",
        estimatedTimeToMarket: "6-12 months",
        requiredResources: ["Development", "AI/ML", "Marketing"]
      });
    }

    return mockIdeas;
  }

  async validateIdea(ideaId) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      // Get idea from database
      const idea = await db.getIdeaById(ideaId);
      if (!idea) {
        throw new Error('Idea not found');
      }

      console.log(`Validating idea: ${idea.title}`);

      let validation;
      if (this.vertexAI) {
        // Use Vertex AI for validation
        validation = await this.vertexAI.validateIdea({
          title: idea.title,
          description: idea.description,
          marketProblem: idea.metadata?.marketProblem || '',
          solution: idea.metadata?.solution || '',
          targetMarket: idea.metadata?.targetMarket || '',
          revenueModel: idea.metadata?.revenueModel || ''
        });
      } else {
        // Fallback to mock validation
        validation = this.generateMockValidation(idea);
      }

      // Store validation results
      const validationPromises = [
        db.createValidationResult({
          ideaId,
          metricName: 'market_demand',
          metricValue: validation.marketDemand?.score || Math.floor(Math.random() * 30) + 70,
          rawData: validation.marketDemand || { analysis: 'Mock analysis' }
        }),
        db.createValidationResult({
          ideaId,
          metricName: 'competition',
          metricValue: validation.competition?.score || Math.floor(Math.random() * 30) + 60,
          rawData: validation.competition || { analysis: 'Mock analysis' }
        }),
        db.createValidationResult({
          ideaId,
          metricName: 'technical_feasibility',
          metricValue: validation.technicalFeasibility?.score || Math.floor(Math.random() * 20) + 80,
          rawData: validation.technicalFeasibility || { analysis: 'Mock analysis' }
        }),
        db.createValidationResult({
          ideaId,
          metricName: 'overall_score',
          metricValue: validation.overallScore || Math.floor(Math.random() * 30) + 70,
          rawData: validation
        })
      ];

      await Promise.all(validationPromises);

      // Update idea status
      const overallScore = validation.overallScore || 80;
      const newStatus = overallScore >= 70 ? 'validated' : 'pending';
      await db.updateIdeaStatus(ideaId, newStatus);

      console.log(`Idea validated with score: ${overallScore}`);
      return validation;
    } catch (error) {
      console.error('Error validating idea:', error);
      throw error;
    }
  }

  generateMockValidation(idea) {
    const scores = {
      marketDemand: Math.floor(Math.random() * 30) + 70,
      competition: Math.floor(Math.random() * 30) + 60,
      technicalFeasibility: Math.floor(Math.random() * 20) + 80,
      scalability: Math.floor(Math.random() * 25) + 75,
      timeToMarket: Math.floor(Math.random() * 20) + 70
    };

    const overallScore = Math.round(
      (scores.marketDemand * 0.3 +
       scores.competition * 0.2 +
       scores.technicalFeasibility * 0.2 +
       scores.scalability * 0.2 +
       scores.timeToMarket * 0.1)
    );

    return {
      marketDemand: {
        score: scores.marketDemand,
        analysis: "Strong market need with growing demand"
      },
      competition: {
        score: scores.competition,
        analysis: "Moderate competition with differentiation opportunities"
      },
      technicalFeasibility: {
        score: scores.technicalFeasibility,
        analysis: "Technically achievable with current stack"
      },
      scalability: {
        score: scores.scalability,
        analysis: "Good potential for scale with proper infrastructure"
      },
      timeToMarket: {
        score: scores.timeToMarket,
        analysis: "Can launch within 6-9 months"
      },
      overallScore,
      recommendation: overallScore >= 70 ? 'PROCEED' : 'REVIEW',
      strengths: ["Large addressable market", "Clear value proposition"],
      weaknesses: ["Requires significant marketing budget"],
      improvements: ["Start with MVP approach", "Focus on specific niche"]
    };
  }

  async getIdeas(filters = {}) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      const ideas = await db.getIdeas(filters);

      // Attach validation results to each idea
      const ideasWithValidation = await Promise.all(
        ideas.map(async (idea) => {
          const validationResults = await db.getIdeaValidationResults(idea.id);
          const overallScore = validationResults.find(r => r.metric_name === 'overall_score');

          return {
            ...idea,
            validationScore: overallScore?.metric_value || null,
            validationResults
          };
        })
      );

      return ideasWithValidation;
    } catch (error) {
      console.error('Error fetching ideas:', error);
      throw error;
    }
  }

  async getIdeaById(id) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      const idea = await db.getIdeaById(id);
      if (!idea) {
        return null;
      }

      const validationResults = await db.getIdeaValidationResults(id);
      const overallScore = validationResults.find(r => r.metric_name === 'overall_score');

      return {
        ...idea,
        validationScore: overallScore?.metric_value || null,
        validationResults
      };
    } catch (error) {
      console.error('Error fetching idea by ID:', error);
      throw error;
    }
  }

  async selectIdea(ideaId) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      // Update idea status to selected
      const idea = await db.updateIdeaStatus(ideaId, 'selected');

      // Create a project for the selected idea
      const project = await db.createProject({
        ideaId,
        projectName: idea.title,
        projectSlug: idea.title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''),
        metadata: {
          selectedAt: new Date().toISOString(),
          status: 'initializing'
        }
      });

      console.log(`Idea selected and project created: ${idea.title}`);
      return { idea, project };
    } catch (error) {
      console.error('Error selecting idea:', error);
      throw error;
    }
  }

  async getStats() {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      return await db.getStats();
    } catch (error) {
      console.error('Error fetching stats:', error);
      throw error;
    }
  }

  async generateContent(prompt, contentType = 'marketing') {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      if (this.vertexAI) {
        return await this.vertexAI.generateContent(prompt, contentType);
      } else {
        // Fallback to mock content
        return `Generated ${contentType} content for: ${prompt}`;
      }
    } catch (error) {
      console.error('Error generating content:', error);
      throw error;
    }
  }

  async quickAnalysis(text, analysisType = 'sentiment') {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      if (this.vertexAI) {
        return await this.vertexAI.quickAnalysis(text, analysisType);
      } else {
        // Fallback to mock analysis
        return {
          sentiment: 'positive',
          confidence: 0.85,
          explanation: 'Mock analysis - text appears positive'
        };
      }
    } catch (error) {
      console.error('Error in quick analysis:', error);
      throw error;
    }
  }

  async updateIdea(ideaId, updates) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      // Update idea in database
      const updatedIdea = await db.updateIdea(ideaId, updates);

      if (!updatedIdea) {
        throw new Error('Idea not found or update failed');
      }

      // Update idea in vector database
      try {
        await vectorService.updateIdea(updatedIdea);
      } catch (vectorError) {
        console.warn('Failed to update idea in vector database:', vectorError.message);
        // Continue even if vector update fails
      }

      console.log(`Idea ${ideaId} updated successfully`);
      return updatedIdea;
    } catch (error) {
      console.error('Error updating idea:', error);
      throw error;
    }
  }

  async deleteIdea(ideaId) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      // Delete idea from database
      const deleted = await db.deleteIdea(ideaId);

      if (!deleted) {
        throw new Error('Idea not found or delete failed');
      }

      // Delete idea from vector database
      try {
        await vectorService.deleteIdea(ideaId);
      } catch (vectorError) {
        console.warn('Failed to delete idea from vector database:', vectorError.message);
        // Continue even if vector deletion fails
      }

      console.log(`Idea ${ideaId} deleted successfully`);
      return true;
    } catch (error) {
      console.error('Error deleting idea:', error);
      throw error;
    }
  }

  async semanticSearch(query, options = {}) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    const { filters = {}, limit = 10, threshold = 0.3 } = options;

    try {
      console.log(`Performing semantic search for: "${query}"`);

      // Use vector service for semantic search
      const vectorResults = await vectorService.semanticSearch(query, {
        filters,
        limit,
        threshold,
        includeMetadata: true
      });

      // Get full idea data from database
      const results = [];
      for (const vectorResult of vectorResults) {
        try {
          const idea = await this.getIdeaById(vectorResult.id);
          if (idea) {
            results.push({
              ...idea,
              similarityScore: vectorResult.similarity,
              similarityPercentage: Math.round(vectorResult.similarity * 100)
            });
          }
        } catch (error) {
          console.warn(`Failed to get idea ${vectorResult.id} from database:`, error.message);
        }
      }

      // Sort by similarity score descending
      results.sort((a, b) => b.similarityScore - a.similarityScore);

      console.log(`Semantic search returned ${results.length} results`);
      return results;
    } catch (error) {
      console.error('Error in semantic search:', error);
      // Fallback to basic text-based search
      return this.fallbackTextSearch(query, filters, limit);
    }
  }

  async findSimilarIdeas(ideaId, options = {}) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    const { limit = 5, threshold = 0.3 } = options;

    try {
      // Use vector service to find similar ideas
      const vectorResults = await vectorService.findSimilarIdeas(ideaId, {
        limit,
        threshold
      });

      // Get full idea data from database
      const similarIdeas = [];
      for (const vectorResult of vectorResults) {
        try {
          const idea = await this.getIdeaById(vectorResult.id);
          if (idea) {
            similarIdeas.push({
              ...idea,
              similarityScore: vectorResult.similarity,
              similarityPercentage: Math.round(vectorResult.similarity * 100)
            });
          }
        } catch (error) {
          console.warn(`Failed to get idea ${vectorResult.id} from database:`, error.message);
        }
      }

      console.log(`Found ${similarIdeas.length} similar ideas for idea ${ideaId}`);
      return similarIdeas;
    } catch (error) {
      console.error('Error finding similar ideas:', error);
      return [];
    }
  }

  async getSearchSuggestions(query, options = {}) {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    const { limit = 5 } = options;

    try {
      const ideas = await this.getIdeas({});
      const queryLower = query.toLowerCase();

      // Extract potential suggestions from titles, categories, and tags
      const suggestions = new Set();

      ideas.forEach(idea => {
        // Title suggestions
        if (idea.title.toLowerCase().includes(queryLower)) {
          suggestions.add(idea.title);
        }

        // Category suggestions
        if (idea.category.toLowerCase().includes(queryLower)) {
          suggestions.add(idea.category);
        }

        // Tag suggestions
        (idea.metadata?.tags || []).forEach(tag => {
          if (tag.toLowerCase().includes(queryLower)) {
            suggestions.add(tag);
          }
        });
      });

      return Array.from(suggestions).slice(0, limit);
    } catch (error) {
      console.error('Error getting search suggestions:', error);
      return [];
    }
  }

  async getSearchAnalytics() {
    if (!this.isInitialized) {
      throw new Error('IdeaService not initialized');
    }

    try {
      const ideas = await this.getIdeas({});

      return {
        totalIdeas: ideas.length,
        categories: this.getCategoryDistribution(ideas),
        averageScore: this.getAverageScore(ideas),
        topTags: this.getTopTags(ideas),
        searchTrends: this.getMockSearchTrends()
      };
    } catch (error) {
      console.error('Error getting search analytics:', error);
      return {
        totalIdeas: 0,
        categories: {},
        averageScore: 0,
        topTags: [],
        searchTrends: []
      };
    }
  }

  async generateEmbedding(text) {
    if (!this.vertexAI) {
      // Fallback: generate simple mock embedding based on text
      return this.generateMockEmbedding(text);
    }

    try {
      // In a real implementation, this would call Vertex AI embedding model
      // For now, return a mock embedding
      return this.generateMockEmbedding(text);
    } catch (error) {
      console.error('Error generating embedding:', error);
      return this.generateMockEmbedding(text);
    }
  }

  generateMockEmbedding(text) {
    // Generate a deterministic pseudo-random embedding based on text
    const embedding = [];
    const textHash = this.simpleHash(text);

    for (let i = 0; i < 384; i++) { // Standard embedding size
      embedding.push((Math.sin(textHash + i) + 1) / 2); // Normalize to [0, 1]
    }

    return embedding;
  }

  simpleHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }

  cosineSimilarity(vecA, vecB) {
    if (vecA.length !== vecB.length) {
      throw new Error('Vectors must be of same length');
    }

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < vecA.length; i++) {
      dotProduct += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }

    normA = Math.sqrt(normA);
    normB = Math.sqrt(normB);

    if (normA === 0 || normB === 0) {
      return 0;
    }

    return dotProduct / (normA * normB);
  }

  fallbackTextSearch(query, filters, limit) {
    // Simple text-based search as fallback
    const queryLower = query.toLowerCase();
    const ideas = []; // Would normally call this.getIdeas(filters)

    const results = ideas.filter(idea => {
      const searchText = `${idea.title} ${idea.description} ${idea.category} ${(idea.metadata?.tags || []).join(' ')}`.toLowerCase();
      return searchText.includes(queryLower);
    }).map(idea => ({
      ...idea,
      similarityScore: 0.5, // Default similarity for text search
      similarityPercentage: 50
    }));

    return results.slice(0, limit);
  }

  getCategoryDistribution(ideas) {
    const distribution = {};
    ideas.forEach(idea => {
      distribution[idea.category] = (distribution[idea.category] || 0) + 1;
    });
    return distribution;
  }

  getAverageScore(ideas) {
    const scores = ideas.filter(idea => idea.validationScore).map(idea => idea.validationScore);
    if (scores.length === 0) return 0;
    return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length);
  }

  getTopTags(ideas) {
    const tagCount = {};
    ideas.forEach(idea => {
      (idea.metadata?.tags || []).forEach(tag => {
        tagCount[tag] = (tagCount[tag] || 0) + 1;
      });
    });

    return Object.entries(tagCount)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 10)
      .map(([tag, count]) => ({ tag, count }));
  }

  getMockSearchTrends() {
    // Mock search trends for demonstration
    return [
      { query: 'AI automation', count: 45, trend: 'up' },
      { query: 'Sustainable tech', count: 32, trend: 'up' },
      { query: 'Healthcare AI', count: 28, trend: 'stable' },
      { query: 'FinTech', count: 25, trend: 'down' },
      { query: 'E-commerce', count: 22, trend: 'stable' }
    ];
  }
}

module.exports = new IdeaService();