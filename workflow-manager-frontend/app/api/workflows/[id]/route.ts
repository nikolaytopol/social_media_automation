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

async function readWorkflowMetadata(workflowId: string): Promise<WorkflowMetadata | null> {
  try {
    const workflowPath = path.join(WORKFLOWS_DIR, workflowId)
    const metadataPath = path.join(workflowPath, ".workflow_state.json")
    const metadataContent = await fs.readFile(metadataPath, "utf-8")
    return JSON.parse(metadataContent)
  } catch (error) {
    console.error(`Failed to read metadata for ${workflowId}:`, error)
    return null
  }
}

async function readRetrainingMessages(workflowId: string): Promise<string[]> {
  try {
    const retrainingPath = path.join(WORKFLOWS_DIR, workflowId, "retraining")
    const files = await fs.readdir(retrainingPath)
    const messages: string[] = []

    for (const file of files) {
      if (file.endsWith(".txt")) {
        const content = await fs.readFile(path.join(retrainingPath, file), "utf-8")
        messages.push(...content.split("\n").filter((line) => line.trim()))
      }
    }

    return messages
  } catch (error) {
    console.error(`Failed to read retraining messages for ${workflowId}:`, error)
    return []
  }
}

// Add a helper to recursively get all .json files in a directory and its subdirectories
async function getAllJsonFiles(dir: string): Promise<string[]> {
  let results: string[] = []
  try {
    const list = await fs.readdir(dir, { withFileTypes: true })
    for (const file of list) {
      const filePath = path.join(dir, file.name)
      if (file.isDirectory()) {
        results = results.concat(await getAllJsonFiles(filePath))
      } else if (file.name.endsWith(".json")) {
        results.push(filePath)
      }
    }
  } catch (error) {
    // Directory may not exist, just return empty
  }
  return results
}

// Helper to get all subfolders in a directory
async function getAllSubfolders(dir: string): Promise<string[]> {
  let results: string[] = []
  try {
    const list = await fs.readdir(dir, { withFileTypes: true })
    for (const file of list) {
      if (file.isDirectory()) {
        results.push(path.join(dir, file.name))
      }
    }
  } catch (error) {
    // Directory may not exist
  }
  return results
}

// Helper to get message/tweet info from a subfolder
async function getMessageInfo(folder: string, type: 'posted' | 'history') {
  let textFile = type === 'posted' ? 'tweet_text.txt' : 'original_message.txt'
  let text = ''
  let media: string[] = []
  let otherFiles: string[] = []
  let id = path.basename(folder)
  let timestamp: string | null = null
  try {
    const stat = await fs.stat(folder)
    timestamp = stat.mtime.toISOString()
    const files = await fs.readdir(folder)
    for (const file of files) {
      const filePath = path.join(folder, file)
      if (file === textFile) {
        text = await fs.readFile(filePath, 'utf8')
      } else if (file.match(/\.(jpg|jpeg|png|gif|mp4|webm)$/i)) {
        media.push(file)
      } else {
        otherFiles.push(file)
      }
    }
  } catch (error) { }
  return { id, text, timestamp, media, otherFiles }
}

// Update readPostedTweets to use getAllJsonFiles
async function readPostedTweets(workflowId: string) {
  try {
    const postedPath = path.join(WORKFLOWS_DIR, workflowId, "posted_messages")
    const jsonFiles = await getAllJsonFiles(postedPath)
    const recentFiles = jsonFiles
      .sort()
      .reverse()
      .slice(0, 10)
    const tweets = []
    for (const filePath of recentFiles) {
      try {
        const content = await fs.readFile(filePath, "utf-8")
        const tweetData = JSON.parse(content)
        tweets.push({
          id: path.basename(filePath).replace(".json", ""),
          text: tweetData.text || tweetData.content || "No text available",
          timestamp: tweetData.timestamp || tweetData.created_at || new Date().toISOString(),
          media: tweetData.media || [],
          otherFiles: tweetData.otherFiles || [],
          canMarkIncorrect: true,
        })
      } catch (error) {
        console.error(`Failed to read tweet file ${filePath}:`, error)
      }
    }
    return tweets
  } catch (error) {
    console.error(`Failed to read posted tweets for ${workflowId}:`, error)
    return []
  }
}

// Update readReceivedTweets to use getAllJsonFiles
async function readReceivedTweets(workflowId: string) {
  try {
    const historyPath = path.join(WORKFLOWS_DIR, workflowId, "message_history")
    const jsonFiles = await getAllJsonFiles(historyPath)
    const recentFiles = jsonFiles
      .sort()
      .reverse()
      .slice(0, 10)
    const tweets = []
    for (const filePath of recentFiles) {
      try {
        const content = await fs.readFile(filePath, "utf-8")
        const messageData = JSON.parse(content)
        if (Array.isArray(messageData)) {
          messageData.forEach((msg, idx) => {
            tweets.push({
              id: `${path.basename(filePath)}_${idx}`,
              text: msg.text || msg.content || "No text available",
              timestamp: msg.timestamp || msg.created_at || new Date().toISOString(),
              media: msg.media || [],
              otherFiles: msg.otherFiles || [],
              source: msg.source || msg.author || "Unknown",
            })
          })
        } else {
          tweets.push({
            id: path.basename(filePath),
            text: messageData.text || messageData.content || "No text available",
            timestamp: messageData.timestamp || messageData.created_at || new Date().toISOString(),
            media: messageData.media || [],
            otherFiles: messageData.otherFiles || [],
            source: messageData.source || messageData.author || "Unknown",
          })
        }
      } catch (error) {
        console.error(`Failed to read message history file ${filePath}:`, error)
      }
    }
    return tweets.slice(0, 10) // Limit to 10 most recent
  } catch (error) {
    console.error(`Failed to read received tweets for ${workflowId}:`, error)
    return []
  }
}

export async function GET(request: NextRequest, { params }: { params: { id: string } }) {
  const workflowId = params.id

  try {
    const metadata = await readWorkflowMetadata(workflowId)

    if (!metadata) {
      return NextResponse.json({ error: "Workflow not found" }, { status: 404 })
    }

    // Read additional data
    const retrainingMessages = await readRetrainingMessages(workflowId)
    const postedPath = path.join(WORKFLOWS_DIR, workflowId, "posted_messages")
    const historyPath = path.join(WORKFLOWS_DIR, workflowId, "message_history")

    // For posted_messages
    const postedFolders = await getAllSubfolders(postedPath)
    const postedTweets = await Promise.all(postedFolders.map(f => getMessageInfo(f, 'posted')))
    // For message_history
    const historyFolders = await getAllSubfolders(historyPath)
    const receivedMessages = await Promise.all(historyFolders.map(f => getMessageInfo(f, 'history')))

    const workflowDetail = {
      ...metadata,
      retrainingMessages,
      postedTweets,
      receivedTweets: receivedMessages,
    }

    return NextResponse.json(workflowDetail)
  } catch (error) {
    console.error(`Failed to fetch workflow ${workflowId}:`, error)
    return NextResponse.json({ error: "Failed to fetch workflow details" }, { status: 500 })
  }
}