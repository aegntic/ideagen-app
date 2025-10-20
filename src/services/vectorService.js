/**
 * Vector Database Service
 * Handles vector embeddings and semantic search across multiple vector databases
 */

const { VertexAI } = require('@google-cloud/vertexai');
const ElasticsearchVector = require('../database/elasticsearchVector');
const ChromaVectorDB = require('../database/vectorDatabase');
const winston = require('winston');

class VectorService {
  constructor() {
    this.vertexAI = null;
    this.elasticsearchClient = null;
    this.chromaClient = null;
    this.isInitialized = false;
    this.primaryVectorDB = process.env.VECTOR_DB_TYPE || 'chroma'; // 'elasticsearch' or 'chroma'
    this.useMemoryFallback = process.env.USE_MEMORY_FALLBACK !== 'false';
    this.memoryStore = new Map(); // In-memory fallback for vectors

    this.logger = winston.createLogger({
      level: 'info',
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
      ),
      transports: [
        new winston.transports.Console({
          format: winston.format.simple()
        })
      ]
    });
  }

  async initialize() {
    try {
      this.logger.info('Initializing VectorService...');

      // Initialize Vertex AI for embeddings
      if (process.env.GOOGLE_CLOUD_PROJECT_ID) {
        this.vertexAI = new VertexAI({
          project: process.env.GOOGLE_CLOUD_PROJECT_ID,
          location: process.env.GOOGLE_CLOUD_LOCATION || 'us-central1'
        });
        this.logger.info('Vertex AI client initialized for embeddings');
      }

      // Initialize Elasticsearch vector support
      if (process.env.ELASTICSEARCH_URL && this.primaryVectorDB === 'elasticsearch') {
        this.elasticsearchClient = new ElasticsearchVector({
          url: process.env.ELASTICSEARCH_URL,
          username: process.env.ELASTICSEARCH_USERNAME,
          password: process.env.ELASTICSEARCH_PASSWORD,
          index: 'ideas_vectors'
        });
        await this.elasticsearchClient.initialize();
        this.logger.info('Elasticsearch vector client initialized');
      }

      // Initialize ChromaDB vector support
      if (this.primaryVectorDB === 'chroma') {
        this.chromaClient = new ChromaVectorDB({
          path: process.env.CHROMA_DB_PATH || './chroma_db',
          collection: 'ideas'
        });
        await this.chromaClient.initialize();
        this.logger.info('ChromaDB client initialized');
      }

      this.isInitialized = true;
      this.logger.info(`VectorService initialized successfully with ${this.primaryVectorDB} as primary vector DB`);
      return true;
    } catch (error) {
      this.logger.error('Failed to initialize VectorService:', error);
      // Continue with memory fallback if initialization fails
      this.useMemoryFallback = true;
      this.isInitialized = true;
      this.logger.warn('VectorService using memory fallback due to initialization failure');
      return true;
    }
  }

  /**
   * Generate vector embedding for text using Vertex AI
   */
  async generateEmbedding(text) {
    try {
      if (!this.vertexAI) {
        // Fallback to mock embedding for testing
        return this.generateMockEmbedding(text);
      }

      const model = this.vertexAI.getGenerativeModel({
        model: 'text-embedding-004'
      });

      const result = await model.embedContent({
        content: {
          parts: [{ text }]
        }
      });

      return result.embedding.values;
    } catch (error) {
      this.logger.error('Error generating embedding:', error);
      // Fallback to mock embedding
      return this.generateMockEmbedding(text);
    }
  }

  /**
   * Generate mock embedding for testing/fallback purposes
   */
  generateMockEmbedding(text) {
    // Generate deterministic pseudo-random embedding based on text
    const dimension = 768; // Standard embedding dimension
    const embedding = new Array(dimension);
    let hash = 0;

    for (let i = 0; i < text.length; i++) {
      const char = text.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }

    for (let i = 0; i < dimension; i++) {
      hash = ((hash << 5) - hash) + i;
      hash = hash & hash;
      embedding[i] = (hash % 2000 - 1000) / 1000; // Normalize to [-1, 1]
    }

    return embedding;
  }

  /**
   * Store idea with its vector embedding
   */
  async storeIdea(idea) {
    try {
      const { id, title, description, category, metadata } = idea;

      // Create searchable text from idea fields
      const searchableText = `
        Title: ${title}
        Description: ${description}
        Category: ${category}
        Tags: ${(metadata?.tags || []).join(', ')}
        Target Market: ${metadata?.targetMarket || ''}
        Revenue Model: ${metadata?.revenueModel || ''}
      `.trim();

      // Generate embedding
      const embedding = await this.generateEmbedding(searchableText);

      const vectorData = {
        id: id.toString(),
        text: searchableText,
        embedding,
        metadata: {
          id,
          title,
          description,
          category,
          tags: metadata?.tags || [],
          targetMarket: metadata?.targetMarket || '',
          revenueModel: metadata?.revenueModel || '',
          validationScore: metadata?.validationScore || null,
          createdAt: metadata?.createdAt || new Date().toISOString()
        }
      };

      // Store in primary vector database
      if (this.primaryVectorDB === 'elasticsearch' && this.elasticsearchClient) {
        await this.elasticsearchClient.storeVector(vectorData);
      } else if (this.primaryVectorDB === 'chroma' && this.chromaClient) {
        await this.chromaClient.storeVector(vectorData);
      }

      // Store in memory fallback
      if (this.useMemoryFallback) {
        this.memoryStore.set(id.toString(), vectorData);
      }

      this.logger.info(`Stored vector embedding for idea: ${title} (${id})`);
      return true;
    } catch (error) {
      this.logger.error('Error storing idea vector:', error);
      throw error;
    }
  }

  /**
   * Perform semantic search to find similar ideas
   */
  async semanticSearch(query, options = {}) {
    try {
      const {
        limit = 10,
        threshold = 0.7,
        filters = {},
        includeMetadata = true
      } = options;

      // Generate embedding for query
      const queryEmbedding = await this.generateEmbedding(query);

      let results = [];

      // Search in primary vector database
      if (this.primaryVectorDB === 'elasticsearch' && this.elasticsearchClient) {
        results = await this.elasticsearchClient.searchSimilar(queryEmbedding, {
          limit,
          threshold,
          filters,
          includeMetadata
        });
      } else if (this.primaryVectorDB === 'chroma' && this.chromaClient) {
        results = await this.chromaClient.searchSimilar(queryEmbedding, {
          limit,
          threshold,
          filters,
          includeMetadata
        });
      }

      // Fallback to memory search if primary search fails or no results
      if ((results.length === 0 || !this.primaryVectorDB) && this.useMemoryFallback) {
        results = this.memorySearch(queryEmbedding, { limit, threshold });
      }

      this.logger.info(`Semantic search for "${query}" returned ${results.length} results`);
      return results;
    } catch (error) {
      this.logger.error('Error in semantic search:', error);
      // Fallback to memory search
      if (this.useMemoryFallback) {
        const queryEmbedding = await this.generateEmbedding(query);
        return this.memorySearch(queryEmbedding, options);
      }
      throw error;
    }
  }

  /**
   * In-memory vector search using cosine similarity
   */
  memorySearch(queryEmbedding, options = {}) {
    const { limit = 10, threshold = 0.7 } = options;
    const results = [];

    for (const [id, vectorData] of this.memoryStore.entries()) {
      const similarity = this.cosineSimilarity(queryEmbedding, vectorData.embedding);

      if (similarity >= threshold) {
        results.push({
          id,
          similarity,
          text: vectorData.text,
          metadata: vectorData.metadata
        });
      }
    }

    // Sort by similarity and limit results
    return results
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, limit);
  }

  /**
   * Calculate cosine similarity between two vectors
   */
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

  /**
   * Update idea vector when idea is modified
   */
  async updateIdea(idea) {
    try {
      // Remove old vector
      await this.deleteIdea(idea.id);
      // Store new vector
      await this.storeIdea(idea);

      this.logger.info(`Updated vector embedding for idea: ${idea.id}`);
      return true;
    } catch (error) {
      this.logger.error('Error updating idea vector:', error);
      throw error;
    }
  }

  /**
   * Delete idea vector
   */
  async deleteIdea(ideaId) {
    try {
      const id = ideaId.toString();

      // Delete from primary vector database
      if (this.primaryVectorDB === 'elasticsearch' && this.elasticsearchClient) {
        await this.elasticsearchClient.deleteVector(id);
      } else if (this.primaryVectorDB === 'chroma' && this.chromaClient) {
        await this.chromaClient.deleteVector(id);
      }

      // Delete from memory fallback
      if (this.useMemoryFallback) {
        this.memoryStore.delete(id);
      }

      this.logger.info(`Deleted vector embedding for idea: ${ideaId}`);
      return true;
    } catch (error) {
      this.logger.error('Error deleting idea vector:', error);
      throw error;
    }
  }

  /**
   * Get vector statistics and health status
   */
  async getStats() {
    const stats = {
      initialized: this.isInitialized,
      primaryVectorDB: this.primaryVectorDB,
      useMemoryFallback: this.useMemoryFallback,
      memoryStoreSize: this.memoryStore.size,
      clients: {
        vertexAI: !!this.vertexAI,
        elasticsearch: !!this.elasticsearchClient?.isConnected,
        chroma: !!this.chromaClient?.isConnected
      }
    };

    // Get specific database stats
    if (this.primaryVectorDB === 'elasticsearch' && this.elasticsearchClient) {
      stats.elasticsearch = await this.elasticsearchClient.getStats();
    } else if (this.primaryVectorDB === 'chroma' && this.chromaClient) {
      stats.chroma = await this.chromaClient.getStats();
    }

    return stats;
  }

  /**
   * Batch store multiple ideas
   */
  async batchStoreIdeas(ideas) {
    try {
      const results = [];

      for (const idea of ideas) {
        try {
          await this.storeIdea(idea);
          results.push({ id: idea.id, success: true });
        } catch (error) {
          this.logger.error(`Failed to store idea ${idea.id}:`, error);
          results.push({ id: idea.id, success: false, error: error.message });
        }
      }

      const successCount = results.filter(r => r.success).length;
      this.logger.info(`Batch stored ${successCount}/${ideas.length} idea vectors`);

      return results;
    } catch (error) {
      this.logger.error('Error in batch storing ideas:', error);
      throw error;
    }
  }

  /**
   * Find similar ideas based on an existing idea ID
   */
  async findSimilarIdeas(ideaId, options = {}) {
    try {
      // Get the idea and find similar ones
      const vectorData = await this.getIdeaVector(ideaId);
      if (!vectorData) {
        throw new Error(`Idea ${ideaId} not found in vector store`);
      }

      const results = await this.semanticSearch(vectorData.text, {
        ...options,
        excludeIds: [ideaId] // Exclude the original idea
      });

      this.logger.info(`Found ${results.length} similar ideas for idea ${ideaId}`);
      return results;
    } catch (error) {
      this.logger.error('Error finding similar ideas:', error);
      throw error;
    }
  }

  /**
   * Get vector data for a specific idea
   */
  async getIdeaVector(ideaId) {
    const id = ideaId.toString();

    // Try primary vector database first
    if (this.primaryVectorDB === 'elasticsearch' && this.elasticsearchClient) {
      return await this.elasticsearchClient.getVector(id);
    } else if (this.primaryVectorDB === 'chroma' && this.chromaClient) {
      return await this.chromaClient.getVector(id);
    }

    // Fallback to memory store
    if (this.useMemoryFallback) {
      return this.memoryStore.get(id);
    }

    return null;
  }
}

module.exports = new VectorService();