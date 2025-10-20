/**
 * Elasticsearch Vector Database Integration
 * Handles vector storage and retrieval using Elasticsearch with dense vector fields
 */

const { Client } = require('@elastic/elasticsearch');
const winston = require('winston');

class ElasticsearchVector {
  constructor(config = {}) {
    this.config = {
      url: config.url || 'http://localhost:9200',
      username: config.username || null,
      password: config.password || null,
      index: config.index || 'ideas_vectors',
      vectorDimension: config.vectorDimension || 768,
      similarity: config.similarity || 'cosine',
      ...config
    };

    this.client = null;
    this.isConnected = false;
    this.indexName = this.config.index;

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
      this.logger.info('Initializing Elasticsearch vector client...');

      // Create Elasticsearch client
      const clientConfig = {
        node: this.config.url,
        requestTimeout: 30000,
        sniffOnStart: true
      };

      if (this.config.username && this.config.password) {
        clientConfig.auth = {
          username: this.config.username,
          password: this.config.password
        };
      }

      this.client = new Client(clientConfig);

      // Test connection
      const health = await this.client.cluster.health();
      this.logger.info(`Elasticsearch cluster status: ${health.status}`);

      // Create index with vector mapping if it doesn't exist
      await this.createIndex();

      this.isConnected = true;
      this.logger.info('Elasticsearch vector client initialized successfully');
      return true;
    } catch (error) {
      this.logger.error('Failed to initialize Elasticsearch:', error);
      throw error;
    }
  }

  /**
   * Create index with appropriate mapping for vector search
   */
  async createIndex() {
    try {
      const exists = await this.client.indices.exists({
        index: this.indexName
      });

      if (!exists) {
        this.logger.info(`Creating index: ${this.indexName}`);

        const mapping = {
          mappings: {
            properties: {
              id: {
                type: 'keyword'
              },
              text: {
                type: 'text',
                analyzer: 'standard',
                fields: {
                  keyword: {
                    type: 'keyword'
                  }
                }
              },
              embedding: {
                type: 'dense_vector',
                dims: this.config.vectorDimension,
                index: true,
                similarity: this.config.similarity
              },
              metadata: {
                properties: {
                  title: {
                    type: 'text',
                    fields: {
                      keyword: { type: 'keyword' }
                    }
                  },
                  description: {
                    type: 'text'
                  },
                  category: {
                    type: 'keyword'
                  },
                  tags: {
                    type: 'keyword'
                  },
                  targetMarket: {
                    type: 'text',
                    fields: {
                      keyword: { type: 'keyword' }
                    }
                  },
                  revenueModel: {
                    type: 'keyword'
                  },
                  validationScore: {
                    type: 'float'
                  },
                  createdAt: {
                    type: 'date'
                  }
                }
              },
              createdAt: {
                type: 'date'
              },
              updatedAt: {
                type: 'date'
              }
            }
          },
          settings: {
            number_of_shards: 1,
            number_of_replicas: 0,
            index: {
              max_result_window: 50000
            }
          }
        };

        await this.client.indices.create({
          index: this.indexName,
          body: mapping
        });

        this.logger.info(`Index ${this.indexName} created successfully`);
      } else {
        this.logger.info(`Index ${this.indexName} already exists`);
      }
    } catch (error) {
      this.logger.error('Error creating index:', error);
      throw error;
    }
  }

  /**
   * Store vector embedding in Elasticsearch
   */
  async storeVector(vectorData) {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      const { id, embedding, text, metadata } = vectorData;

      const document = {
        id,
        text,
        embedding,
        metadata: {
          ...metadata,
          // Ensure searchable fields are at the top level for better filtering
          title: metadata.title,
          description: metadata.description,
          category: metadata.category,
          tags: metadata.tags || [],
          targetMarket: metadata.targetMarket,
          revenueModel: metadata.revenueModel,
          validationScore: metadata.validationScore,
          createdAt: metadata.createdAt
        },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };

      // Check if document already exists
      const existingDoc = await this.client.search({
        index: this.indexName,
        body: {
          query: {
            term: {
              id: id
            }
          },
          _source: false,
          size: 1
        }
      });

      if (existingDoc.hits.hits.length > 0) {
        // Update existing document
        await this.client.update({
          index: this.indexName,
          id: id,
          body: {
            doc: document
          }
        });
        this.logger.info(`Updated vector document: ${id}`);
        return { id, action: 'updated' };
      } else {
        // Index new document
        await this.client.index({
          index: this.indexName,
          id: id,
          body: document
        });
        this.logger.info(`Stored vector document: ${id}`);
        return { id, action: 'added' };
      }
    } catch (error) {
      this.logger.error('Error storing vector in Elasticsearch:', error);
      throw error;
    }
  }

  /**
   * Search for similar vectors using cosine similarity
   */
  async searchSimilar(queryEmbedding, options = {}) {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      const {
        limit = 10,
        threshold = 0.7,
        filters = {},
        includeMetadata = true
      } = options;

      // Build Elasticsearch query
      const query = {
        bool: {
          must: [
            {
              script_score: {
                query: { match_all: {} },
                script: {
                  source: "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                  params: {
                    query_vector: queryEmbedding
                  }
                },
                min_score: threshold + 1 // cosineSimilarity returns -1 to 1, we add 1 to make it 0-2
              }
            }
          ]
        }
      };

      // Add filters
      if (Object.keys(filters).length > 0) {
        query.bool.filter = this.buildFilters(filters);
      }

      // Search query
      const searchBody = {
        query,
        size: limit,
        _source: includeMetadata
      };

      const result = await this.client.search({
        index: this.indexName,
        body: searchBody
      });

      // Process results
      const processedResults = [];
      result.hits.hits.forEach(hit => {
        const score = hit._score - 1; // Convert back to -1 to 1 range
        const similarity = Math.max(0, score); // Ensure non-negative

        const resultItem = {
          id: hit._source.id,
          similarity,
          score: hit._score
        };

        if (includeMetadata) {
          resultItem.text = hit._source.text;
          resultItem.metadata = hit._source.metadata;
        }

        processedResults.push(resultItem);
      });

      this.logger.info(`Elasticsearch search returned ${processedResults.length} results`);
      return processedResults;
    } catch (error) {
      this.logger.error('Error searching Elasticsearch:', error);
      throw error;
    }
  }

  /**
   * Get vector data by ID
   */
  async getVector(id) {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      const result = await this.client.search({
        index: this.indexName,
        body: {
          query: {
            term: {
              id: id
            }
          },
          size: 1
        }
      });

      if (result.hits.hits.length === 0) {
        return null;
      }

      const hit = result.hits.hits[0];
      return {
        id: hit._source.id,
        text: hit._source.text,
        embedding: hit._source.embedding,
        metadata: hit._source.metadata
      };
    } catch (error) {
      this.logger.error('Error getting vector from Elasticsearch:', error);
      throw error;
    }
  }

  /**
   * Delete vector by ID
   */
  async deleteVector(id) {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      await this.client.deleteByQuery({
        index: this.indexName,
        body: {
          query: {
            term: {
              id: id
            }
          }
        }
      });

      this.logger.info(`Deleted vector: ${id}`);
      return true;
    } catch (error) {
      this.logger.error('Error deleting vector from Elasticsearch:', error);
      throw error;
    }
  }

  /**
   * Batch store multiple vectors
   */
  async batchStoreVectors(vectors) {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      const body = [];
      const results = [];

      for (const vectorData of vectors) {
        const { id, embedding, text, metadata } = vectorData;

        const document = {
          id,
          text,
          embedding,
          metadata: {
            ...metadata,
            title: metadata.title,
            description: metadata.description,
            category: metadata.category,
            tags: metadata.tags || [],
            targetMarket: metadata.targetMarket,
            revenueModel: metadata.revenueModel,
            validationScore: metadata.validationScore,
            createdAt: metadata.createdAt
          },
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        };

        // Add bulk operation
        body.push({
          index: {
            _index: this.indexName,
            _id: id
          }
        });
        body.push(document);
      }

      // Execute bulk request
      const bulkResponse = await this.client.bulk({ body });

      // Process results
      bulkResponse.items.forEach((item, index) => {
        if (item.index.status === 200 || item.index.status === 201) {
          results.push({ id: vectors[index].id, success: true });
        } else {
          results.push({
            id: vectors[index].id,
            success: false,
            error: item.index.error
          });
        }
      });

      const successCount = results.filter(r => r.success).length;
      this.logger.info(`Bulk store completed: ${successCount}/${vectors.length} vectors stored successfully`);

      return results;
    } catch (error) {
      this.logger.error('Error in bulk storing vectors:', error);
      throw error;
    }
  }

  /**
   * Build Elasticsearch filters from filter object
   */
  buildFilters(filters) {
    const esFilters = [];

    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;

      if (typeof value === 'string') {
        esFilters.push({
          term: { [`metadata.${key}`]: value }
        });
      } else if (Array.isArray(value)) {
        esFilters.push({
          terms: { [`metadata.${key}`]: value }
        });
      } else if (typeof value === 'object') {
        // Support range filters
        if (value.$gte !== undefined || value.$lte !== undefined) {
          const rangeFilter = { range: {} };
          if (value.$gte !== undefined) {
            rangeFilter.range[`metadata.${key}`] = { gte: value.$gte };
          }
          if (value.$lte !== undefined) {
            rangeFilter.range[`metadata.${key}`] = { lte: value.$lte };
          }
          esFilters.push(rangeFilter);
        }
      } else {
        esFilters.push({
          term: { [`metadata.${key}`]: value }
        });
      }
    }

    return esFilters;
  }

  /**
   * Get index statistics
   */
  async getStats() {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      const stats = await this.client.indices.stats({
        index: this.indexName
      });

      const countResult = await this.client.count({
        index: this.indexName
      });

      return {
        connected: this.isConnected,
        indexName: this.indexName,
        documentCount: countResult.count,
        indexSize: stats.indices[this.indexName]?.total?.store?.size_in_bytes || 0,
        lastActivity: new Date().toISOString()
      };
    } catch (error) {
      this.logger.error('Error getting Elasticsearch stats:', error);
      return {
        connected: false,
        error: error.message
      };
    }
  }

  /**
   * Clear all vectors from index
   */
  async clearIndex() {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      await this.client.deleteByQuery({
        index: this.indexName,
        body: {
          query: {
            match_all: {}
          }
        }
      });

      this.logger.info(`Cleared all vectors from index: ${this.indexName}`);
      return true;
    } catch (error) {
      this.logger.error('Error clearing Elasticsearch index:', error);
      throw error;
    }
  }

  /**
   * Close Elasticsearch connection
   */
  async close() {
    try {
      if (this.client) {
        await this.client.close();
        this.isConnected = false;
        this.client = null;
        this.logger.info('Elasticsearch connection closed');
      }
    } catch (error) {
      this.logger.error('Error closing Elasticsearch connection:', error);
    }
  }

  /**
   * Health check for Elasticsearch
   */
  async healthCheck() {
    try {
      if (!this.isConnected) {
        return { status: 'disconnected', error: 'Elasticsearch not connected' };
      }

      const clusterHealth = await this.client.cluster.health();
      const indexStats = await this.client.indices.stats({
        index: this.indexName
      });

      return {
        status: clusterHealth.status,
        cluster: clusterHealth.cluster_name,
        nodes: clusterHealth.number_of_nodes,
        documentCount: indexStats.indices[this.indexName]?.total?.docs?.count || 0,
        indexName: this.indexName,
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

  /**
   * Optimize index for better search performance
   */
  async optimizeIndex() {
    try {
      if (!this.isConnected) {
        throw new Error('Elasticsearch not connected');
      }

      await this.client.indices.forcemerge({
        index: this.indexName,
        max_num_segments: 1
      });

      this.logger.info(`Index ${this.indexName} optimized successfully`);
      return true;
    } catch (error) {
      this.logger.error('Error optimizing Elasticsearch index:', error);
      throw error;
    }
  }
}

module.exports = ElasticsearchVector;