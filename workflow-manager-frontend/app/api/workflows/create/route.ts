import { type NextRequest, NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"

const WORKFLOWS_DIR = process.env.WORKFLOWS_DIR || "./workflows"

interface WorkflowMetadata {
  id: string
  name: string
  status: "running" | "stopped" | "error"
  description: string
  template: string
  lastRun?: string
  createdAt: string
  config: Record<string, any>
}

async function createWorkflowStructure(workflowId: string, metadata: WorkflowMetadata) {
  const workflowPath = path.join(WORKFLOWS_DIR, workflowId)

  try {
    // Create main workflow directory
    await fs.mkdir(workflowPath, { recursive: true })

    // Create subdirectories
    const subdirs = ["logs", "message_history", "posted_messages", "retraining", "__pycache__"]
    for (const subdir of subdirs) {
      await fs.mkdir(path.join(workflowPath, subdir), { recursive: true })
    }

    // Create metadata file
    const metadataPath = path.join(workflowPath, ".workflow_state.json")
    await fs.writeFile(metadataPath, JSON.stringify(metadata, null, 2))

    // Create .env file template
    const envPath = path.join(workflowPath, ".env")
    const envTemplate = `# Environment variables for ${metadata.name}
# Add your API keys and configuration here
OPENAI_API_KEY=
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=
`
    await fs.writeFile(envPath, envTemplate)

    // Create main Python file based on template
    const mainPyPath = path.join(workflowPath, `${workflowId}_main.py`)
    const pythonTemplate = generatePythonTemplate(metadata)
    await fs.writeFile(mainPyPath, pythonTemplate)

    // Create test connection file
    const testPyPath = path.join(workflowPath, "test_twitter_connection.py")
    const testTemplate = generateTestTemplate(metadata)
    await fs.writeFile(testPyPath, testTemplate)

    console.log(`Created workflow structure for ${workflowId}`)
    return true
  } catch (error) {
    console.error(`Failed to create workflow structure for ${workflowId}:`, error)
    throw error
  }
}

function generatePythonTemplate(metadata: WorkflowMetadata): string {
  return `#!/usr/bin/env python3
"""
${metadata.name} - Generated from ${metadata.template} template
Created: ${metadata.createdAt}
Description: ${metadata.description}
"""

import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/workflow.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('${metadata.id}_bot')

class ${metadata.name.replace(" ", "")}Workflow:
    def __init__(self):
        self.config = ${JSON.stringify(metadata.config, null, 8)}
        self.status = "stopped"
        self.load_environment()
    
    def load_environment(self):
        """Load environment variables from .env file"""
        env_path = Path('.env')
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
    
    def update_status(self, status: str):
        """Update workflow status in metadata file"""
        try:
            with open('.workflow_state.json', 'r') as f:
                metadata = json.load(f)
            
            metadata['status'] = status
            metadata['lastRun'] = datetime.now().isoformat()
            
            with open('.workflow_state.json', 'w') as f:
                json.dump(metadata, f, indent=2)
                
            self.status = status
            logger.info(f"Status updated to: {status}")
        except Exception as e:
            logger.error(f"Failed to update status: {e}")
    
    def run(self):
        """Main workflow execution"""
        logger.info(f"Starting ${metadata.name} workflow...")
        self.update_status("running")
        
        try:
            # TODO: Implement your workflow logic here
            # This is where you would add your specific workflow functionality
            
            while self.status == "running":
                logger.info("Processing workflow iteration...")
                
                # Add your main workflow logic here
                # For example:
                # - Fetch data
                # - Process messages
                # - Generate content
                # - Post to social media
                
                time.sleep(self.config.get('posting_interval', 3600))
                
        except KeyboardInterrupt:
            logger.info("Workflow interrupted by user")
            self.update_status("stopped")
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            self.update_status("error")

if __name__ == "__main__":
    workflow = ${metadata.name.replace(" ", "")}Workflow()
    workflow.run()
`
}

function generateTestTemplate(metadata: WorkflowMetadata): string {
  return `#!/usr/bin/env python3
"""
Test Twitter/Social Media Connection for ${metadata.name}
"""

import os
import json
from pathlib import Path

def load_environment():
    """Load environment variables from .env file"""
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

def test_connection():
    """Test social media API connection"""
    load_environment()
    
    # TODO: Add your API connection testing logic here
    print("Testing API connections...")
    
    # Example for Twitter API
    api_key = os.getenv('TWITTER_API_KEY')
    if api_key:
        print("✓ Twitter API key found")
    else:
        print("✗ Twitter API key missing")
    
    # Add more connection tests as needed
    print("Connection test completed")

if __name__ == "__main__":
    test_connection()
`
}

export async function POST(request: NextRequest) {
  try {
    const { templateId, name, config, startImmediately } = await request.json()

    // Generate a unique workflow ID
    const workflowId = name
      .toLowerCase()
      .replace(/\s+/g, "_")
      .replace(/[^a-z0-9_]/g, "")

    // Check if workflow already exists
    const workflowPath = path.join(WORKFLOWS_DIR, workflowId)
    try {
      await fs.access(workflowPath)
      return NextResponse.json(
        {
          success: false,
          error: "Workflow with this name already exists",
        },
        { status: 400 },
      )
    } catch {
      // Workflow doesn't exist, which is good
    }

    // Create workflow metadata
    const metadata: WorkflowMetadata = {
      id: workflowId,
      name,
      status: "stopped",
      description: `${name} - Created from ${templateId} template`,
      template: templateId,
      createdAt: new Date().toISOString(),
      config,
    }

    // Create workflow structure
    await createWorkflowStructure(workflowId, metadata)

    // If startImmediately is true, you would launch the workflow process here
    if (startImmediately) {
      // TODO: Launch the workflow process
      // This might involve spawning a Python process or similar
      metadata.status = "running"
      metadata.lastRun = new Date().toISOString()

      // Update the metadata file with running status
      const metadataPath = path.join(workflowPath, ".workflow_state.json")
      await fs.writeFile(metadataPath, JSON.stringify(metadata, null, 2))
    }

    return NextResponse.json({
      success: true,
      workflowId,
      message: `Workflow '${name}' created successfully`,
    })
  } catch (error) {
    console.error("Failed to create workflow:", error)
    return NextResponse.json(
      {
        success: false,
        error: "Failed to create workflow",
      },
      { status: 500 },
    )
  }
}
