/**
 * ChromaDB Vector Database Integration
 * Handles vector storage and retrieval using ChromaDB
 */

const { ChromaClient } = require('chromadb');
const winston = require('winston');

class ChromaVectorDB {
  constructor(config = {}) {
    this.config = {
      path: config.path || './chroma_db',
      collection: config.collection || 'ideas',
      embeddingFunction: config.embeddingFunction || null,
      ...config
    };

    this.client = null;
    this.collection = null;
    this.isConnected = false;

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
      this.logger.info('Initializing ChromaDB client...');

      // Initialize ChromaDB client
      this.client = new ChromaClient({
        path: this.config.path
      });

      // Get or create collection
      try {
        this.collection = await this.client.getCollection({
          name: this.config.collection
        });
        this.logger.info(`Connected to existing collection: ${this.config.collection}`);
      } catch (error) {
        if (error.message.includes('No collection found')) {
          this.logger.info(`Creating new collection: ${this.config.collection}`);
          this.collection = await this.client.createCollection({
            name: this.config.collection,
            metadata: {
              description: 'Ideas vector collection for semantic search',
              created: new Date().toISOString()
            }
          });
        } else {
          throw error;
        }
      }

      this.isConnected = true;
      this.logger.info('ChromaDB client initialized successfully');
      return true;
    } catch (error) {
      this.logger.error('Failed to initialize ChromaDB:', error);
      throw error;
    }
  }

  /**
   * Store vector embedding in ChromaDB
   */
  async storeVector(vectorData) {
    try {
      if (!this.isConnected) {
        throw new Error('ChromaDB not connected');
      }

      const { id, embedding, text, metadata } = vectorData;

      // Prepare data for ChromaDB
      const chromaData = {
        ids: [id],
        embeddings: [embedding],
        documents: [text],
        metadatas: [metadata]
      };

      // Check if document already exists and update it
      try {
        const existingDoc = await this.collection.get({
          ids: [id]
        });

        if (existingDoc.ids.length > 0) {
          // Update existing document
          await this.collection.update({
            ids: [id],
            embeddings: [embedding],
            documents: [text],
            metadatas: [metadata]
          });
          this.logger.info(`Updated vector document: ${id}`);
          return { id, action: 'updated' };
        }
      } catch (error) {
        // Document doesn't exist, continue with add
      }

      // Add new document
      await this.collection.add(chromaData);
      this.logger.info(`Stored vector document: ${id}`);
      return { id, action: 'added' };
    } catch (error) {
      this.logger.error('Error storing vector in ChromaDB:', error);
      throw error;
    }
  }

  /**
   * Search for similar vectors using cosine similarity
   */
  async searchSimilar(queryEmbedding, options = {}) {
    try {
      if (!this.isConnected) {
        throw new Error('ChromaDB not connected');
      }

      const {
        limit = 10,
        threshold = 0.7,
        filters = {},
        includeMetadata = true
      } = options;

      // Build where clause for filtering
      let whereClause = {};
      if (Object.keys(filters).length > 0) {
        whereClause = this.buildWhereClause(filters);
      }

      // Query ChromaDB
      const results = await this.collection.query({
        queryEmbeddings: [queryEmbedding],
        nResults: limit,
        where: Object.keys(whereClause).length > 0 ? whereClause : undefined,
        include: includeMetadata ? ['metadatas', 'documents', 'distances'] : ['distances']
      });

      // Process results
      const processedResults = [];
      if (results.ids[0] && results.ids[0].length > 0) {
        for (let i = 0; i < results.ids[0].length; i++) {
          const id = results.ids[0][i];
          const distance = results.distances[0][i];
          const similarity = 1 - distance; // Convert distance to similarity

          if (similarity >= threshold) {
            const result = {
              id,
              similarity,
              distance
            };

            if (includeMetadata) {
              result.text = results.documents[0][i];
              result.metadata = results.metadatas[0][i];
            }

            processedResults.push(result);
          }
        }
      }

      // Sort by similarity (highest first)
      processedResults.sort((a, b) => b.similarity - a.similarity);

      this.logger.info(`ChromaDB search returned ${processedResults.length} results`);
      return processedResults;
    } catch (error) {
      this.logger.error('Error searching ChromaDB:', error);
      throw error;
    }
  }

  /**
   * Get vector data by ID
   */
  async getVector(id) {
    try {
      if (!this.isConnected) {
        throw new Error('ChromaDB not connected');
      }

      const result = await this.collection.get({
        ids: [id],
        include: ['metadatas', 'documents', 'embeddings']
      });

      if (result.ids.length === 0) {
        return null;
      }

      return {
        id: result.ids[0],
        text: result.documents[0],
        embedding: result.embeddings[0],
        metadata: result.metadatas[0]
      };
    } catch (error) {
      this.logger.error('Error getting vector from ChromaDB:', error);
      throw error;
    }
  }

  /**
   * Delete vector by ID
   */
  async deleteVector(id) {
    try {
      if (!this.isConnected) {
        throw new Error('ChromaDB not connected');
      }

      await this.collection.delete({
        ids: [id]
      });

      this.logger.info(`Deleted vector: ${id}`);
      return true;
    } catch (error) {
      this.logger.error('Error deleting vector from ChromaDB:', error);
      throw error;
    }
  }

  /**
   * Batch store multiple vectors
   */
  async batchStoreVectors(vectors) {
    try {
      if (!this.isConnected) {
        throw new Error('ChromaDB not connected');
      }

      const results = [];

      // Process in batches to avoid overwhelming ChromaDB
      const batchSize = 100;
      for (let i = 0; i < vectors.length; i += batchSize) {
        const batch = vectors.slice(i, i + batchSize);

        const chromaData = {
          ids: batch.map(v => v.id),
          embeddings: batch.map(v => v.embedding),
          documents: batch.map(v => v.text),
          metadatas: batch.map(v => v.metadata)
        };

        try {
          await this.collection.add(chromaData);
          results.push(...batch.map(v => ({ id: v.id, success: true })));
          this.logger.info(`Batch stored ${batch.length} vectors (batch ${Math.floor(i/batchSize) + 1})`);
        } catch (error) {
          this.logger.error(`Error storing batch ${Math.floor(i/batchSize) + 1}:`, error);
          results.push(...batch.map(v => ({
            id: v.id,
            success: false,
            error: error.message
          })));
        }
      }

      const successCount = results.filter(r => r.success).length;
      this.logger.info(`Batch store completed: ${successCount}/${vectors.length} vectors stored successfully`);

      return results;
    } catch (error) {
      this.logger.error('Error in batch storing vectors:', error);
      throw error;
    }
  }

  /**
   * Build ChromaDB where clause from filters
   */
  buildWhereClause(filters) {
    const whereClause = {};

    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;

      if (typeof value === 'string') {
        whereClause[key] = { $eq: value };
      } else if (Array.isArray(value)) {
        whereClause[key] = { $in: value };
      } else if (typeof value === 'object') {
        // Support advanced filter operations
        if (value.$eq) whereClause[key] = { $eq: value.$eq };
        if (value.$ne) whereClause[key] = { $ne: value.$ne };
        if (value.$in) whereClause[key] = { $in: value.$in };
        if (value.$gt) whereClause[key] = { $gt: value.$gt };
        if (value.$gte) whereClause[key] = { $gte: value.$gte };
        if (value.$lt) whereClause[key] = { $lt: value.$lt };
        if (value.$lte) whereClause[key] = { $lte: value.$lte };
      } else {
        whereClause[key] = { $eq: value };
      }
    }

    return whereClause;
  }

  /**
   * Get collection statistics
   */
  async getStats() {
    try {
      if (!this.isConnected) {
        throw new Error('ChromaDB not connected');
      }

      const count = await this.collection.count();
      const collectionInfo = await this.collection.get();

      return {
        connected: this.isConnected,
        collectionName: this.config.collection,
        documentCount: count,
        sampleIds: collectionInfo.ids.slice(0, 5),
        lastActivity: new Date().toISOString()
      };
    } catch (error) {
      this.logger.error('Error getting ChromaDB stats:', error);
      return {
        connected: false,
        error: error.message
      };
    }
  }

  /**
   * Clear all vectors from collection
   */
  async clearCollection() {
    try {
      if (!this.isConnected) {
        throw new Error('ChromaDB not connected');
      }

      // Get all IDs and delete them
      const allDocs = await this.collection.get();
      if (allDocs.ids.length > 0) {
        await this.collection.delete({
          ids: allDocs.ids
        });
        this.logger.info(`Cleared ${allDocs.ids.length} vectors from collection`);
      }

      return true;
    } catch (error) {
      this.logger.error('Error clearing ChromaDB collection:', error);
      throw error;
    }
  }

  /**
   * Close ChromaDB connection
   */
  async close() {
    try {
      // ChromaDB doesn't have explicit close method for HTTP client
      this.isConnected = false;
      this.client = null;
      this.collection = null;
      this.logger.info('ChromaDB connection closed');
    } catch (error) {
      this.logger.error('Error closing ChromaDB connection:', error);
    }
  }

  /**
   * Health check for ChromaDB
   */
  async healthCheck() {
    try {
      if (!this.isConnected) {
        return { status: 'disconnected', error: 'ChromaDB not connected' };
      }

      // Try to get collection count as a simple health check
      const count = await this.collection.count();

      return {
        status: 'healthy',
        documentCount: count,
        collectionName: this.config.collection,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }
}

module.exports = ChromaVectorDB;