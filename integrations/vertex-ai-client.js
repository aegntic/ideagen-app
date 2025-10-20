/**
 * Google Vertex AI Client for Idea Generation
 * Replaces OpenAI GPT-4 with Gemini 2.5 Pro and Flash models
 */

const { VertexAI } = require('@google-cloud/vertexai');

class IdeaGenVertexAIClient {
  constructor(config) {
    this.vertexAI = new VertexAI({
      project: config.projectId,
      location: config.location,
      googleAuthOptions: {
        keyFilename: config.keyFile || process.env.GOOGLE_APPLICATION_CREDENTIALS
      }
    });

    this.models = {
      pro: 'gemini-2.5-pro',
      flash: 'gemini-2.5-flash-nano-banana'
    };

    this.config = config;
  }

  /**
   * Generate business ideas using Gemini 2.5 Pro
   */
  async generateIdeas(trends, sources, count = 10) {
    const model = this.vertexAI.getGenerativeModel({
      model: this.models.pro,
      generationConfig: {
        temperature: 0.7,
        topP: 0.95,
        topK: 64,
        maxOutputTokens: 2048,
        responseMimeType: "application/json"
      }
    });

    const prompt = `
You are an expert business analyst and startup strategist. Based on the following trending topics and market data, generate ${count} innovative business ideas.

TRENDING TOPICS:
${trends.map(t => `- ${t.title}: ${t.description}`).join('\n')}

DATA SOURCES:
${sources.map(s => `- ${s.type}: ${s.data}`).join('\n')}

REQUIREMENTS:
1. Each idea should be actionable and realistic
2. Include market analysis, revenue model, and competitive advantage
3. Consider current technology trends and market gaps
4. Provide a viability score (1-100) for each idea

FORMAT:
Return a JSON array with the following structure for each idea:
{
  "title": "Catchy business name",
  "description": "Brief description (1-2 sentences)",
  "marketProblem": "Problem being solved",
  "solution": "Proposed solution",
  "targetMarket": "Target audience",
  "revenueModel": "How it makes money",
  "competitiveAdvantage": "Unique selling proposition",
  "viabilityScore": 85,
  "estimatedTimeToMarket": "6-12 months",
  "requiredResources": ["Technology", "Marketing", "Operations"],
  "tags": ["SaaS", "AI", "FinTech"],
  "trendingTopics": ["AI", "Remote Work", "Sustainability"]
}

Focus on ideas that leverage emerging technologies and address real market needs.
`;

    try {
      const result = await model.generateContent(prompt);
      const response = result.response;
      const ideas = JSON.parse(response.text());

      return Array.isArray(ideas) ? ideas : [ideas];
    } catch (error) {
      console.error('Error generating ideas with Vertex AI:', error);
      throw new Error(`Failed to generate ideas: ${error.message}`);
    }
  }

  /**
   * Validate and score ideas using Gemini 2.5 Pro
   */
  async validateIdea(idea) {
    const model = this.vertexAI.getGenerativeModel({
      model: this.models.pro,
      generationConfig: {
        temperature: 0.3,
        topP: 0.8,
        topK: 40,
        maxOutputTokens: 1024,
        responseMimeType: "application/json"
      }
    });

    const prompt = `
You are a venture capitalist and business analyst. Analyze the following business idea and provide a detailed validation.

BUSINESS IDEA:
Title: ${idea.title}
Description: ${idea.description}
Market Problem: ${idea.marketProblem}
Solution: ${idea.solution}
Target Market: ${idea.targetMarket}
Revenue Model: ${idea.revenueModel}

ANALYSIS CRITERIA:
1. Market Demand (30%): Is there real market need?
2. Competition (20%): How competitive is the space?
3. Technical Feasibility (20%): Can this be built reasonably?
4. Scalability (20%): Can this scale to millions of users?
5. Time to Market (10%): How quickly can this launch?

Provide detailed analysis and scores for each criterion, plus an overall validation score.

FORMAT:
{
  "marketDemand": {
    "score": 85,
    "analysis": "Strong market need with growing demand..."
  },
  "competition": {
    "score": 70,
    "analysis": "Moderate competition with differentiation opportunities..."
  },
  "technicalFeasibility": {
    "score": 90,
    "analysis": "Technically achievable with current stack..."
  },
  "scalability": {
    "score": 80,
    "analysis": "Good potential for scale with proper infrastructure..."
  },
  "timeToMarket": {
    "score": 75,
    "analysis": "Can launch within 6-9 months..."
  },
  "overallScore": 82,
  "recommendation": "PROCEED",
  "strengths": ["Large addressable market", "Clear value proposition"],
  "weaknesses": ["Requires significant marketing budget"],
  "improvements": ["Start with MVP approach", "Focus on specific niche"]
}
`;

    try {
      const result = await model.generateContent(prompt);
      const response = result.response;
      const validation = JSON.parse(response.text());

      return validation;
    } catch (error) {
      console.error('Error validating idea with Vertex AI:', error);
      throw new Error(`Failed to validate idea: ${error.message}`);
    }
  }

  /**
   * Generate content using Gemini 2.5 Flash for faster responses
   */
  async generateContent(prompt, contentType = 'marketing') {
    const model = this.vertexAI.getGenerativeModel({
      model: this.models.flash,
      generationConfig: {
        temperature: 0.9,
        topP: 0.95,
        topK: 40,
        maxOutputTokens: 1024
      }
    });

    const contentPrompt = this.getContentPrompt(prompt, contentType);

    try {
      const result = await model.generateContent(contentPrompt);
      const response = result.response;
      return response.text();
    } catch (error) {
      console.error('Error generating content with Vertex AI:', error);
      throw new Error(`Failed to generate content: ${error.message}`);
    }
  }

  /**
   * Get contextual prompts for different content types
   */
  getContentPrompt(userPrompt, contentType) {
    const prompts = {
      marketing: `
You are a marketing copywriter. Create compelling marketing content based on the following request:
${userPrompt}

Keep it concise, engaging, and action-oriented.
Focus on benefits and value proposition.
`,
      technical: `
You are a technical writer. Create clear technical documentation based on:
${userPrompt}

Use clear, precise language. Include code examples where relevant.
Focus on implementation details and best practices.
`,
      social: `
You are a social media manager. Create engaging social media content for:
${userPrompt}

Use appropriate hashtags, emojis, and calls-to-action.
Adapt tone for the platform (LinkedIn, Twitter, etc.).
Keep it short and shareable.
`,
      website: `
You are a web copywriter. Create compelling website copy for:
${userPrompt}

Focus on:
- Clear value proposition
- Benefits over features
- Call-to-action
- SEO-friendly language
- Scannable formatting
`
    };

    return prompts[contentType] || prompts.marketing;
  }

  /**
   * Quick analysis using Flash model for real-time insights
   */
  async quickAnalysis(text, analysisType = 'sentiment') {
    const model = this.vertexAI.getGenerativeModel({
      model: this.models.flash,
      generationConfig: {
        temperature: 0.1,
        maxOutputTokens: 512,
        responseMimeType: "application/json"
      }
    });

    const prompts = {
      sentiment: `Analyze the sentiment of this text: "${text}". Return {"sentiment": "positive/negative/neutral", "confidence": 0.95, "explanation": "brief explanation"}`,
      keywords: `Extract key topics and keywords from: "${text}". Return {"keywords": ["keyword1", "keyword2"], "topics": ["topic1", "topic2"], "relevance_scores": [0.9, 0.8]}`,
      summary: `Summarize this text in 2-3 sentences: "${text}". Return {"summary": "concise summary", "word_count": 25}`,
      trends: `Identify trends from this data: "${text}". Return {"trends": ["trend1", "trend2"], "growth_potential": "high/medium/low", "timeframe": "short/medium/long term"}`
    };

    try {
      const result = await model.generateContent(prompts[analysisType] || prompts.sentiment);
      const response = result.response;
      return JSON.parse(response.text());
    } catch (error) {
      console.error('Error in quick analysis:', error);
      throw new Error(`Quick analysis failed: ${error.message}`);
    }
  }
}

module.exports = IdeaGenVertexAIClient;