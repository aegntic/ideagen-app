/**
 * Vector Database Implementation
 * Handles vector storage and retrieval with fallback options
 */

const winston = require('winston');

class VectorDatabase {
  constructor(config = {}) {
    this.config = {
      provider: config.provider || 'memory', // 'memory', 'chroma', 'elasticsearch'
      collection: config.collection || 'ideas',
      ...config
    };

    this.client = null;
    this.collection = null;
    this.isConnected = false;
    this.vectorStore = new Map(); // In-memory storage

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
      this.logger.info(`Initializing vector database with provider: ${this.config.provider}`);

      switch (this.config.provider) {
        case 'chroma':
          return await this._initializeChromaDB();
        case 'elasticsearch':
          return await this._initializeElasticsearch();
        default:
          return await this._initializeMemory();
      }
    } catch (error) {
      this.logger.error(`Failed to initialize vector database (${this.config.provider}):`, error);
      // Fall back to memory storage
      this.logger.info('Falling back to in-memory vector storage');
      return await this._initializeMemory();
    }
  }

  async _initializeMemory() {
    this.logger.info('Using in-memory vector database');
    this.isConnected = true;
    return true;
  }

  async _initializeChromaDB() {
    try {
      const { ChromaClient } = require('chromadb');

      this.client = new ChromaClient({
        path: this.config.path || 'http://localhost:8000'
      });

      this.collection = await this.client.getOrCreateCollection({
        name: this.config.collection,
        metadata: {
          description: 'Ideas vector collection for semantic search',
          created: new Date().toISOString()
        }
      });

      this.isConnected = true;
      this.logger.info('ChromaDB client initialized successfully');
      return true;
    } catch (error) {
      this.logger.error('ChromaDB initialization failed:', error.message);
      throw error;
    }
  }

  async _initializeElasticsearch() {
    try {
      const { Client } = require('@elastic/elasticsearch');

      this.client = new Client({
        node: this.config.elasticsearchUrl || 'http://localhost:9200'
      });

      await this.client.ping();
      this.isConnected = true;
      this.logger.info('Elasticsearch client initialized successfully');
      return true;
    } catch (error) {
      this.logger.error('Elasticsearch initialization failed:', error.message);
      throw error;
    }
  }

  /**
   * Store vector embedding
   */
  async storeVector(vectorData) {
    try {
      if (!this.isConnected) {
        throw new Error('Vector database not connected');
      }

      const { id, embedding, text, metadata } = vectorData;

      switch (this.config.provider) {
        case 'chroma':
          return await this._storeChromaVector(vectorData);
        case 'elasticsearch':
          return await this._storeElasticsearchVector(vectorData);
        default:
          return await this._storeMemoryVector(vectorData);
      }
    } catch (error) {
      this.logger.error('Error storing vector:', error);
      // Store in memory as fallback
      return await this._storeMemoryVector(vectorData);
    }
  }

  async _storeMemoryVector(vectorData) {
    const { id, embedding, text, metadata } = vectorData;

    this.vectorStore.set(id, {
      id,
      embedding,
      text,
      metadata,
      createdAt: new Date().toISOString()
    });

    this.logger.debug(`Stored vector in memory: ${id}`);
    return true;
  }

  async _storeChromaVector(vectorData) {
    const { id, embedding, text, metadata } = vectorData;

    const chromaData = {
      ids: [id],
      embeddings: [embedding],
      documents: [text],
      metadatas: [metadata]
    };

    await this.collection.upsert(chromaData);
    this.logger.debug(`Stored vector in ChromaDB: ${id}`);
    return true;
  }

  async _storeElasticsearchVector(vectorData) {
    const { id, embedding, text, metadata } = vectorData;

    await this.client.index({
      index: this.config.collection,
      id: id,
      body: {
        text,
        embedding,
        metadata,
        timestamp: new Date().toISOString()
      }
    });

    this.logger.debug(`Stored vector in Elasticsearch: ${id}`);
    return true;
  }

  /**
   * Search for similar vectors
   */
  async searchSimilar(queryEmbedding, limit = 10) {
    try {
      if (!this.isConnected) {
        throw new Error('Vector database not connected');
      }

      switch (this.config.provider) {
        case 'chroma':
          return await this._searchChromaSimilar(queryEmbedding, limit);
        case 'elasticsearch':
          return await this._searchElasticsearchSimilar(queryEmbedding, limit);
        default:
          return await this._searchMemorySimilar(queryEmbedding, limit);
      }
    } catch (error) {
      this.logger.error('Error searching vectors:', error);
      // Search in memory as fallback
      return await this._searchMemorySimilar(queryEmbedding, limit);
    }
  }

  async _searchMemorySimilar(queryEmbedding, limit = 10) {
    const results = [];

    for (const [id, data] of this.vectorStore.entries()) {
      const similarity = this._cosineSimilarity(queryEmbedding, data.embedding);
      results.push({
        id,
        text: data.text,
        metadata: data.metadata,
        score: similarity
      });
    }

    // Sort by similarity and return top results
    results.sort((a, b) => b.score - a.score);
    return results.slice(0, limit);
  }

  async _searchChromaSimilar(queryEmbedding, limit = 10) {
    const results = await this.collection.query({
      queryEmbeddings: [queryEmbedding],
      nResults: limit
    });

    return results.ids[0].map((id, index) => ({
      id,
      text: results.documents[0][index],
      metadata: results.metadatas[0][index],
      score: results.distances[0][index]
    }));
  }

  async _searchElasticsearchSimilar(queryEmbedding, limit = 10) {
    const response = await this.client.search({
      index: this.config.collection,
      body: {
        size: limit,
        query: {
          script_score: {
            query: { match_all: {} },
            script: {
              source: 'cosineSimilarity(params.query_vector, \'embedding\') + 1.0',
              params: { query_vector: queryEmbedding }
            }
          }
        }
      }
    });

    return response.body.hits.hits.map(hit => ({
      id: hit._id,
      text: hit._source.text,
      metadata: hit._source.metadata,
      score: hit._score
    }));
  }

  /**
   * Calculate cosine similarity between two vectors
   */
  _cosineSimilarity(vecA, vecB) {
    if (vecA.length !== vecB.length) {
      throw new Error('Vectors must be same length');
    }

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < vecA.length; i++) {
      dotProduct += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }

    if (normA === 0 || normB === 0) {
      return 0;
    }

    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  /**
   * Get vector by ID
   */
  async getVector(id) {
    try {
      if (this.config.provider === 'memory' || !this.isConnected) {
        return this.vectorStore.get(id);
      }

      switch (this.config.provider) {
        case 'chroma':
          const results = await this.collection.get({
            ids: [id]
          });
          if (results.ids.length > 0) {
            return {
              id: results.ids[0],
              text: results.documents[0],
              metadata: results.metadatas[0]
            };
          }
          break;
        case 'elasticsearch':
          const response = await this.client.get({
            index: this.config.collection,
            id: id
          });
          return {
            id: response.body._id,
            text: response.body._source.text,
            metadata: response.body._source.metadata
          };
      }
      return null;
    } catch (error) {
      this.logger.error('Error getting vector:', error);
      return this.vectorStore.get(id) || null;
    }
  }

  /**
   * Delete vector by ID
   */
  async deleteVector(id) {
    try {
      this.vectorStore.delete(id);

      if (!this.isConnected) {
        return true;
      }

      switch (this.config.provider) {
        case 'chroma':
          await this.collection.delete({
            ids: [id]
          });
          break;
        case 'elasticsearch':
          await this.client.delete({
            index: this.config.collection,
            id: id
          });
          break;
      }
      return true;
    } catch (error) {
      this.logger.error('Error deleting vector:', error);
      return false;
    }
  }

  /**
   * Get collection statistics
   */
  async getStats() {
    try {
      const memoryCount = this.vectorStore.size;

      if (!this.isConnected) {
        return {
          provider: 'memory',
          totalDocuments: memoryCount,
          isConnected: false
        };
      }

      switch (this.config.provider) {
        case 'chroma':
          const chromaCount = await this.collection.count();
          return {
            provider: 'chroma',
            totalDocuments: chromaCount,
            memoryDocuments: memoryCount,
            isConnected: true
          };
        case 'elasticsearch':
          const esResponse = await this.client.count({
            index: this.config.collection
          });
          return {
            provider: 'elasticsearch',
            totalDocuments: esResponse.body.count,
            memoryDocuments: memoryCount,
            isConnected: true
          };
        default:
          return {
            provider: 'memory',
            totalDocuments: memoryCount,
            isConnected: true
          };
      }
    } catch (error) {
      this.logger.error('Error getting stats:', error);
      return {
        provider: this.config.provider,
        totalDocuments: this.vectorStore.size,
        isConnected: false,
        error: error.message
      };
    }
  }
}

module.exports = VectorDatabase;