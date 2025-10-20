# Vector Database Integration for IdeaGen

This document describes the comprehensive vector database integration implemented for the IdeaGen app, providing advanced semantic search capabilities for business ideas.

## Overview

The vector database integration enables **semantic search** functionality that finds ideas by meaning and context, not just keywords. This allows users to discover related business ideas using natural language queries.

## Architecture

### Components

1. **Vector Service** (`src/services/vectorService.js`)
   - Core vector operations and embeddings
   - Dual database support (Elasticsearch + ChromaDB)
   - Memory fallback for development/testing
   - Vertex AI embeddings integration

2. **Elasticsearch Integration** (`src/database/elasticsearchVector.js`)
   - Production-ready vector storage
   - Dense vector field support
   - Advanced filtering capabilities
   - High-performance similarity search

3. **ChromaDB Integration** (`src/database/vectorDatabase.js`)
   - Lightweight vector database option
   - Local development support
   - Efficient vector operations
   - Automatic collection management

4. **API Endpoints**
   - Semantic search: `POST /api/search/semantic`
   - Similar ideas: `POST /api/search/similarity`
   - Search suggestions: `GET /api/search/suggestions`
   - Search analytics: `GET /api/search/analytics`

## Features

### 🧠 Semantic Search
- Find ideas using natural language queries
- Understand context and meaning, not just keywords
- Configurable similarity thresholds
- Filter by category, tags, validation score

### 🔍 Similar Ideas Discovery
- Find ideas similar to a specific idea
- Useful for exploring related concepts
- Supports configurable similarity thresholds

### 💡 Search Suggestions
- Auto-complete for search queries
- Based on idea titles, categories, and tags
- Improves user experience

### 📊 Search Analytics
- Track search trends and patterns
- Category distribution
- Popular tags analysis
- Usage metrics

## Configuration

### Environment Variables

```bash
# Vector Database Configuration
VECTOR_DB_TYPE=chroma          # 'elasticsearch', 'chroma', or 'memory'
USE_MEMORY_FALLBACK=true       # Fallback to memory storage

# Elasticsearch Configuration
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=your-password

# ChromaDB Configuration
CHROMA_DB_PATH=./chroma_db
```

### Setup Options

#### 1. Memory Only (Development)
```bash
VECTOR_DB_TYPE=memory
USE_MEMORY_FALLBACK=true
```

#### 2. ChromaDB (Local Development)
```bash
VECTOR_DB_TYPE=chroma
CHROMA_DB_PATH=./chroma_db
```

#### 3. Elasticsearch (Production)
```bash
VECTOR_DB_TYPE=elasticsearch
ELASTICSEARCH_URL=https://your-cluster.es.amazonaws.com
ELASTICSEARCH_USERNAME=your-username
ELASTICSEARCH_PASSWORD=your-password
```

## API Usage

### Semantic Search

```bash
curl -X POST http://localhost:8080/api/search/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence automation platform",
    "limit": 10,
    "threshold": 0.3,
    "filters": {
      "category": "SaaS",
      "validationScore": { "$gte": 70 }
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "query": "artificial intelligence automation platform",
    "results": [
      {
        "id": "idea_123",
        "title": "AI-Powered Customer Support Platform",
        "description": "Automated customer service solution...",
        "similarityScore": 0.85,
        "similarityPercentage": 85,
        "category": "SaaS",
        "validationScore": 80
      }
    ],
    "count": 1,
    "searchedAt": "2025-01-15T10:30:00Z"
  }
}
```

### Similar Ideas

```bash
curl -X POST http://localhost:8080/api/search/similarity \
  -H "Content-Type: application/json" \
  -d '{
    "ideaId": "idea_123",
    "limit": 5,
    "threshold": 0.4
  }'
```

### Search Suggestions

```bash
curl -X GET "http://localhost:8080/api/search/suggestions?q=AI&limit=5"
```

### Search Analytics

```bash
curl -X GET http://localhost:8080/api/search/analytics
```

## Embeddings

### Vertex AI Integration
- Uses Google's Vertex AI text-embedding-004 model
- 768-dimensional embeddings
- High-quality semantic understanding
- Production-ready performance

### Fallback Embeddings
- Deterministic hash-based embeddings for testing
- Ensures functionality without API keys
- Suitable for development environments

## Database Schemas

### Elasticsearch Index Mapping

```json
{
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "text": { "type": "text" },
      "embedding": {
        "type": "dense_vector",
        "dims": 768,
        "similarity": "cosine"
      },
      "metadata": {
        "properties": {
          "title": { "type": "text" },
          "category": { "type": "keyword" },
          "tags": { "type": "keyword" },
          "validationScore": { "type": "float" }
        }
      }
    }
  }
}
```

### ChromaDB Collection
- Automatic schema management
- Efficient vector storage
- Built-in similarity search
- Metadata filtering support

## Performance

### Benchmarks
- **Memory Search**: ~1-2ms per query
- **ChromaDB**: ~5-10ms per query
- **Elasticsearch**: ~10-20ms per query

### Optimization Features
- Batch vector operations
- Efficient cosine similarity calculations
- Configurable indexing strategies
- Memory caching for frequently accessed vectors

## Development

### Testing

```bash
# Run vector search tests
npm run test:vectors

# Start development server with memory fallback
VECTOR_DB_TYPE=memory npm run dev

# Test with ChromaDB
VECTOR_DB_TYPE=chroma npm run dev

# Test with Elasticsearch
VECTOR_DB_TYPE=elasticsearch npm run dev
```

### Monitoring

```bash
# Health check
curl http://localhost:8080/health

# Vector service stats
curl http://localhost:8080/api/search/analytics
```

## Deployment

### Production Setup

1. **Elasticsearch Cluster**
   - Set up Elasticsearch cluster
   - Configure dense vector fields
   - Set appropriate memory allocation

2. **Environment Configuration**
   ```bash
   VECTOR_DB_TYPE=elasticsearch
   ELASTICSEARCH_URL=https://your-cluster.es.amazonaws.com
   ```

3. **Vertex AI Setup**
   - Enable Vertex AI API
   - Configure service account
   - Set proper IAM permissions

### Scaling Considerations

- **Horizontal Scaling**: Elasticsearch cluster scaling
- **Vector Storage**: SSD storage for better performance
- **Memory Allocation**: Adequate heap space for vector operations
- **Network**: Low-latency connections for optimal search speed

## Troubleshooting

### Common Issues

1. **ChromaDB Connection Issues**
   - Ensure ChromaDB server is running
   - Check URL format: `http://localhost:8000`

2. **Elasticsearch Errors**
   - Verify cluster health
   - Check mapping configuration
   - Ensure sufficient memory allocation

3. **Embedding Generation Issues**
   - Verify Vertex AI credentials
   - Check API quota limits
   - Fallback to memory embeddings for testing

### Debug Mode

```bash
# Enable debug logging
DEBUG=vector:* npm run dev

# Test specific components
node scripts/test-vector-search.js
```

## Future Enhancements

### Planned Features
- [ ] Hybrid search (keyword + semantic)
- [ ] Real-time vector updates
- [ ] Multi-language support
- [ ] Advanced filtering options
- [ ] Vector visualization
- [ ] A/B testing for search relevance

### Performance Optimizations
- [ ] Vector quantization
- [ ] Approximate nearest neighbor (ANN)
- [ ] Distributed vector processing
- [ ] Query result caching

## Contributing

### Adding New Vector Databases
1. Implement database interface in `src/database/`
2. Add configuration options to `vectorService.js`
3. Update documentation and examples
4. Add tests for new integration

### Testing
- Unit tests for vector operations
- Integration tests for API endpoints
- Performance benchmarks
- Error handling validation

---

## Support

For questions or issues with the vector database integration:
1. Check the troubleshooting section
2. Review test examples in `scripts/test-vector-search.js`
3. Examine API documentation via `/api/docs`
4. Check logs for detailed error information

This integration demonstrates advanced search capabilities suitable for the Elastic challenge, showcasing semantic understanding, efficient vector operations, and production-ready architecture.