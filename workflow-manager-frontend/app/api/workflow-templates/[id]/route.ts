import { type NextRequest, NextResponse } from "next/server"

// Import the same templates array from the main route
const workflowTemplates = [
  {
    id: "social_media_bot",
    name: "Social Media Bot",
    description: "AI-powered social media content creation and posting",
    category: "social",
    features: [
      "Automated content generation",
      "Duplicate detection",
      "Sentiment analysis",
      "Media attachment support",
      "Engagement tracking",
    ],
    configFields: [
      {
        name: "posting_interval",
        type: "number",
        label: "Posting Interval (seconds)",
        description: "Time between posts in seconds",
        required: true,
        defaultValue: 3600,
      },
      {
        name: "max_posts_per_hour",
        type: "number",
        label: "Max Posts Per Hour",
        description: "Maximum number of posts per hour",
        required: true,
        defaultValue: 5,
      },
      {
        name: "generation_model",
        type: "select",
        label: "Generation Model",
        description: "AI model for content generation",
        required: true,
        defaultValue: "gpt-4",
        options: ["gpt-4", "gpt-3.5-turbo", "claude-3", "gemini-pro"],
      },
      {
        name: "filter_model",
        type: "select",
        label: "Filter Model",
        description: "AI model for content filtering",
        required: true,
        defaultValue: "gpt-3.5-turbo",
        options: ["gpt-4", "gpt-3.5-turbo", "claude-3", "gemini-pro"],
      },
      {
        name: "sentiment_threshold",
        type: "number",
        label: "Sentiment Threshold",
        description: "Minimum sentiment score (0.0 to 1.0)",
        required: true,
        defaultValue: 0.7,
      },
      {
        name: "duplicate_check_enabled",
        type: "boolean",
        label: "Enable Duplicate Check",
        description: "Check for duplicate content before posting",
        required: false,
        defaultValue: true,
      },
      {
        name: "topics",
        type: "textarea",
        label: "Topics of Interest",
        description: "Topics to focus on (one per line)",
        required: true,
        defaultValue: "Technology\nArtificial Intelligence\nStartups",
      },
      {
        name: "api_keys",
        type: "textarea",
        label: "API Keys Configuration",
        description: "API keys and tokens (JSON format)",
        required: true,
        defaultValue: '{\n  "twitter_api_key": "",\n  "openai_api_key": ""\n}',
      },
    ],
  },
  // ... other templates
]

export async function GET(request: NextRequest, { params }: { params: { id: string } }) {
  const templateId = params.id
  const template = workflowTemplates.find((t) => t.id === templateId)

  if (!template) {
    return NextResponse.json({ error: "Template not found" }, { status: 404 })
  }

  return NextResponse.json(template)
}
