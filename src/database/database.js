/**
 * Database layer for promptre.quest app
 * Handles all PostgreSQL operations
 */

const { Pool } = require('pg');

class PromptreQuestDatabase {
  constructor() {
    this.pool = null;
    this.isConnected = false;
    this.useMemoryFallback = false;
    this.memoryStorage = {
      ideas: [],
      validationResults: [],
      projects: []
    };
  }

  async initialize() {
    try {
      // Use environment variables or defaults
      const config = {
        host: process.env.POSTGRES_HOST || 'localhost',
        port: process.env.POSTGRES_PORT || 5432,
        database: process.env.POSTGRES_DB || 'idea_engine',
        user: process.env.POSTGRES_USER || 'postgres',
        password: process.env.POSTGRES_PASSWORD || 'password',
        ssl: process.env.DB_SSL === 'true' ? { rejectUnauthorized: false } : false,
        max: 20,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000,
      };

      // For Google Cloud SQL, use connection name
      if (process.env.DB_CONNECTION_NAME) {
        config.host = '/cloudsql/' + process.env.DB_CONNECTION_NAME;
      }

      this.pool = new Pool(config);

      // Test connection
      const client = await this.pool.connect();
      await client.query('SELECT NOW()');
      client.release();

      this.isConnected = true;
      console.log('Database connected successfully');
      return true;
    } catch (error) {
      console.warn('Database connection failed, falling back to in-memory mode:', error.message);
      this.isConnected = false;
      this.useMemoryFallback = true;
      // Don't throw error, use fallback mode
      return true;
    }
  }

  async createIdea(ideaData) {
    if (this.useMemoryFallback) {
      return this.memoryCreateIdea(ideaData);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const {
      title,
      description,
      category,
      source = 'ai_generated',
      marketSizeEstimate,
      validationScore,
      metadata = {}
    } = ideaData;

    const query = `
      INSERT INTO ideas (title, description, category, source, market_size_estimate, validation_score, metadata)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      RETURNING *
    `;

    try {
      const result = await this.pool.query(query, [
        title,
        description,
        category,
        source,
        marketSizeEstimate,
        validationScore,
        JSON.stringify(metadata)
      ]);

      return result.rows[0];
    } catch (error) {
      console.error('Error creating idea:', error);
      throw error;
    }
  }

  async getIdeas(filters = {}) {
    if (this.useMemoryFallback) {
      return this.memoryGetIdeas(filters);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const {
      status,
      category,
      source,
      limit = 50,
      offset = 0,
      orderBy = 'created_at',
      orderDirection = 'DESC'
    } = filters;

    let query = 'SELECT * FROM ideas WHERE 1=1';
    const params = [];
    let paramIndex = 1;

    if (status) {
      query += ` AND status = $${paramIndex}`;
      params.push(status);
      paramIndex++;
    }

    if (category) {
      query += ` AND category = $${paramIndex}`;
      params.push(category);
      paramIndex++;
    }

    if (source) {
      query += ` AND source = $${paramIndex}`;
      params.push(source);
      paramIndex++;
    }

    query += ` ORDER BY ${orderBy} ${orderDirection}`;
    query += ` LIMIT $${paramIndex}`;
    params.push(limit);
    paramIndex++;

    query += ` OFFSET $${paramIndex}`;
    params.push(offset);

    try {
      const result = await this.pool.query(query, params);
      return result.rows;
    } catch (error) {
      console.error('Error fetching ideas:', error);
      throw error;
    }
  }

  async getIdeaById(id) {
    if (this.useMemoryFallback) {
      return this.memoryGetIdeaById(id);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const query = 'SELECT * FROM ideas WHERE id = $1';

    try {
      const result = await this.pool.query(query, [id]);
      return result.rows[0] || null;
    } catch (error) {
      console.error('Error fetching idea by ID:', error);
      throw error;
    }
  }

  async updateIdeaStatus(id, status) {
    if (this.useMemoryFallback) {
      return this.memoryUpdateIdeaStatus(id, status);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const query = `
      UPDATE ideas
      SET status = $1, updated_at = NOW()
      WHERE id = $2
      RETURNING *
    `;

    try {
      const result = await this.pool.query(query, [status, id]);
      return result.rows[0] || null;
    } catch (error) {
      console.error('Error updating idea status:', error);
      throw error;
    }
  }

  async createValidationResult(validationData) {
    if (this.useMemoryFallback) {
      return this.memoryCreateValidationResult(validationData);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const {
      ideaId,
      metricName,
      metricValue,
      rawData
    } = validationData;

    const query = `
      INSERT INTO validation_results (idea_id, metric_name, metric_value, raw_data)
      VALUES ($1, $2, $3, $4)
      RETURNING *
    `;

    try {
      const result = await this.pool.query(query, [
        ideaId,
        metricName,
        metricValue,
        JSON.stringify(rawData)
      ]);

      return result.rows[0];
    } catch (error) {
      console.error('Error creating validation result:', error);
      throw error;
    }
  }

  async getIdeaValidationResults(ideaId) {
    if (this.useMemoryFallback) {
      return this.memoryGetIdeaValidationResults(ideaId);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const query = 'SELECT * FROM validation_results WHERE idea_id = $1 ORDER BY created_at DESC';

    try {
      const result = await this.pool.query(query, [ideaId]);
      return result.rows;
    } catch (error) {
      console.error('Error fetching validation results:', error);
      throw error;
    }
  }

  async createProject(projectData) {
    if (this.useMemoryFallback) {
      return this.memoryCreateProject(projectData);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const {
      ideaId,
      projectName,
      projectSlug,
      websiteUrl,
      githubRepo,
      metadata = {}
    } = projectData;

    const query = `
      INSERT INTO projects (idea_id, project_name, project_slug, website_url, github_repo, metadata)
      VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING *
    `;

    try {
      const result = await this.pool.query(query, [
        ideaId,
        projectName,
        projectSlug,
        websiteUrl,
        githubRepo,
        JSON.stringify(metadata)
      ]);

      return result.rows[0];
    } catch (error) {
      console.error('Error creating project:', error);
      throw error;
    }
  }

  async getProjects(filters = {}) {
    if (this.useMemoryFallback) {
      return this.memoryGetProjects(filters);
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    const {
      status,
      limit = 20,
      offset = 0
    } = filters;

    let query = `
      SELECT p.*, i.title as idea_title, i.description as idea_description
      FROM projects p
      JOIN ideas i ON p.idea_id = i.id
      WHERE 1=1
    `;
    const params = [];
    let paramIndex = 1;

    if (status) {
      query += ` AND p.status = $${paramIndex}`;
      params.push(status);
      paramIndex++;
    }

    query += ` ORDER BY p.created_at DESC`;
    query += ` LIMIT $${paramIndex}`;
    params.push(limit);
    paramIndex++;

    query += ` OFFSET $${paramIndex}`;
    params.push(offset);

    try {
      const result = await this.pool.query(query, params);
      return result.rows;
    } catch (error) {
      console.error('Error fetching projects:', error);
      throw error;
    }
  }

  async getStats() {
    if (this.useMemoryFallback) {
      return this.memoryGetStats();
    }

    if (!this.isConnected) {
      throw new Error('Database not connected');
    }

    try {
      const ideasQuery = 'SELECT COUNT(*) as total FROM ideas';
      const projectsQuery = 'SELECT COUNT(*) as total FROM projects';
      const validationQuery = 'SELECT AVG(metric_value) as avg_score FROM validation_results WHERE metric_name = \'overall_score\'';

      const [ideasResult, projectsResult, validationResult] = await Promise.all([
        this.pool.query(ideasQuery),
        this.pool.query(projectsQuery),
        this.pool.query(validationQuery)
      ]);

      return {
        totalIdeas: parseInt(ideasResult.rows[0].total),
        totalProjects: parseInt(projectsResult.rows[0].total),
        averageValidationScore: parseFloat(validationResult.rows[0].avg_score) || 0
      };
    } catch (error) {
      console.error('Error fetching stats:', error);
      throw error;
    }
  }

  async close() {
    if (this.pool) {
      await this.pool.end();
      this.isConnected = false;
      console.log('Database connection closed');
    }
  }

  // Memory fallback methods
  memoryCreateIdea(ideaData) {
    const idea = {
      id: 'idea_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
      title: ideaData.title,
      description: ideaData.description,
      category: ideaData.category,
      source: ideaData.source,
      market_size_estimate: ideaData.marketSizeEstimate,
      validation_score: ideaData.validationScore,
      metadata: ideaData.metadata,
      status: 'pending',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    this.memoryStorage.ideas.push(idea);
    return idea;
  }

  memoryGetIdeas(filters = {}) {
    let ideas = [...this.memoryStorage.ideas];

    if (filters.status) {
      ideas = ideas.filter(idea => idea.status === filters.status);
    }
    if (filters.category) {
      ideas = ideas.filter(idea => idea.category === filters.category);
    }
    if (filters.source) {
      ideas = ideas.filter(idea => idea.source === filters.source);
    }

    // Sort
    const order = filters.orderDirection === 'ASC' ? 1 : -1;
    ideas.sort((a, b) => {
      if (filters.orderBy === 'created_at') {
        return order * (new Date(a.created_at) - new Date(b.created_at));
      }
      return 0;
    });

    // Limit and offset
    const limit = filters.limit || 50;
    const offset = filters.offset || 0;
    return ideas.slice(offset, offset + limit);
  }

  memoryGetIdeaById(id) {
    return this.memoryStorage.ideas.find(idea => idea.id === id) || null;
  }

  memoryUpdateIdeaStatus(id, status) {
    const idea = this.memoryStorage.ideas.find(idea => idea.id === id);
    if (idea) {
      idea.status = status;
      idea.updated_at = new Date().toISOString();
    }
    return idea || null;
  }

  memoryCreateValidationResult(validationData) {
    const result = {
      id: 'val_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
      idea_id: validationData.ideaId,
      metric_name: validationData.metricName,
      metric_value: validationData.metricValue,
      raw_data: validationData.rawData,
      created_at: new Date().toISOString()
    };

    this.memoryStorage.validationResults.push(result);
    return result;
  }

  memoryGetIdeaValidationResults(ideaId) {
    return this.memoryStorage.validationResults
      .filter(result => result.idea_id === ideaId)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }

  memoryCreateProject(projectData) {
    const project = {
      id: 'proj_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
      idea_id: projectData.ideaId,
      project_name: projectData.projectName,
      project_slug: projectData.projectSlug,
      website_url: projectData.websiteUrl,
      github_repo: projectData.githubRepo,
      metadata: projectData.metadata,
      status: 'initializing',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    this.memoryStorage.projects.push(project);
    return project;
  }

  memoryGetProjects(filters = {}) {
    let projects = this.memoryStorage.projects.map(project => {
      const idea = this.memoryStorage.ideas.find(i => i.id === project.idea_id);
      return {
        ...project,
        idea_title: idea?.title || 'Unknown',
        idea_description: idea?.description || ''
      };
    });

    if (filters.status) {
      projects = projects.filter(project => project.status === filters.status);
    }

    projects.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    const limit = filters.limit || 20;
    const offset = filters.offset || 0;
    return projects.slice(offset, offset + limit);
  }

  memoryGetStats() {
    const totalIdeas = this.memoryStorage.ideas.length;
    const totalProjects = this.memoryStorage.projects.length;
    const overallResults = this.memoryStorage.validationResults.filter(r => r.metric_name === 'overall_score');
    const avgScore = overallResults.length > 0
      ? overallResults.reduce((sum, r) => sum + r.metric_value, 0) / overallResults.length
      : 0;

    return {
      totalIdeas,
      totalProjects,
      averageValidationScore: avgScore
    };
  }
}

module.exports = new PromptreQuestDatabase();