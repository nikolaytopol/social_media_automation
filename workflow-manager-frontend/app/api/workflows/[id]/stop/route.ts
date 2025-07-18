import { type NextRequest, NextResponse } from "next/server"
import { promises as fs } from "fs"
import path from "path"

const WORKFLOWS_DIR = process.env.WORKFLOWS_DIR || "./workflows"

async function updateWorkflowStatus(workflowId: string, status: string) {
  try {
    const metadataPath = path.join(WORKFLOWS_DIR, workflowId, ".workflow_state.json")
    const metadataContent = await fs.readFile(metadataPath, "utf-8")
    const metadata = JSON.parse(metadataContent)

    metadata.status = status
    metadata.lastRun = new Date().toISOString()

    await fs.writeFile(metadataPath, JSON.stringify(metadata, null, 2))
    return true
  } catch (error) {
    console.error(`Failed to update status for ${workflowId}:`, error)
    return false
  }
}

export async function POST(request: NextRequest, { params }: { params: { id: string } }) {
  const workflowId = params.id

  try {
    // Update metadata file
    const updated = await updateWorkflowStatus(workflowId, "stopped")

    if (!updated) {
      return NextResponse.json(
        {
          success: false,
          error: "Failed to update workflow status",
        },
        { status: 500 },
      )
    }

    // TODO: Actually stop the workflow process
    // This might involve:
    // - Killing a Python subprocess
    // - Stopping a background service
    // - Sending a stop signal to a process manager

    console.log(`Stopping workflow: ${workflowId}`)

    return NextResponse.json({
      success: true,
      message: `Workflow ${workflowId} stopped successfully`,
    })
  } catch (error) {
    console.error(`Failed to stop workflow ${workflowId}:`, error)
    return NextResponse.json(
      {
        success: false,
        error: "Failed to stop workflow",
      },
      { status: 500 },
    )
  }
}
