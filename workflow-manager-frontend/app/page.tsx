"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Play, Square, Settings, RefreshCw, Plus } from "lucide-react"
import Link from "next/link"

interface Workflow {
  id: string
  name: string
  status: "running" | "stopped" | "error"
  lastRun?: string
  description?: string
}

export default function WorkflowDashboard() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchWorkflows = async () => {
    setError(null)
    setLoading(true)
    try {
      const response = await fetch("http://localhost:9000/health")
      if (!response.ok) throw new Error("Backend returned an error")
      const healthData = await response.json()
      const workflowNames = Object.keys(healthData.workflows || {})
      const workflowDetails = await Promise.all(
        workflowNames.map(async (name) => {
          try {
            const res = await fetch(`http://localhost:9000/workflow/info?name=${name}`)
            if (!res.ok) throw new Error("Failed to fetch workflow info")
            const data = await res.json()
            return {
              id: data.name,
              name: data.name,
              status: data.status,
              lastRun: data.lastRun,
              description: data.description || '',
            }
          } catch (err) {
            return {
              id: name,
              name: name,
              status: "error",
              lastRun: undefined,
              description: "Failed to load workflow info",
            }
          }
        })
      )
      setWorkflows(workflowDetails)
    } catch (error: any) {
      setError("Backend unavailable. Please check the server.")
      setWorkflows([])
    } finally {
      setLoading(false)
    }
  }

  const startWorkflow = async (workflowId: string) => {
    setError(null)
    try {
      const response = await fetch(`http://localhost:9000/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: workflowId }),
      })
      const data = await response.json()
      if (data.status !== "success") {
        setError(`Failed to start workflow: ${data.message || "Unknown error"}`)
      } else {
        fetchWorkflows() // Refresh status
      }
    } catch (error: any) {
      setError("Failed to start workflow. Backend unavailable.")
    }
  }

  const stopWorkflow = async (workflowId: string) => {
    setError(null)
    try {
      const response = await fetch(`http://localhost:9000/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: workflowId }),
      })
      const data = await response.json()
      if (data.status !== "success") {
        setError(`Failed to stop workflow: ${data.message || "Unknown error"}`)
      } else {
        fetchWorkflows() // Refresh status
      }
    } catch (error: any) {
      setError("Failed to stop workflow. Backend unavailable.")
    }
  }

  useEffect(() => {
    fetchWorkflows()
    const interval = setInterval(fetchWorkflows, 5000)
    return () => clearInterval(interval)
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-green-500"
      case "stopped":
        return "bg-gray-500"
      case "error":
        return "bg-red-500"
      default:
        return "bg-gray-500"
    }
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Workflow Manager</h1>
          <p className="text-muted-foreground mt-2">Manage and monitor your workflows</p>
        </div>
        <div className="flex gap-3">
          <Link href="/create-workflow">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Workflow
            </Button>
          </Link>
          <Button onClick={fetchWorkflows} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>
      {error && (
        <div className="mb-4 p-4 bg-red-100 text-red-700 rounded border border-red-300">
          {error}
        </div>
      )}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin" />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {workflows.map((workflow) => (
            <Card key={workflow.id || workflow.name} className="hover:shadow-lg transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{workflow.name}</CardTitle>
                  <Badge className={getStatusColor(workflow.status)}>{workflow.status}</Badge>
                </div>
                {workflow.description && <p className="text-sm text-muted-foreground">{workflow.description}</p>}
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex gap-2">
                    {workflow.status === "running" ? (
                      <Button size="sm" variant="destructive" onClick={() => stopWorkflow(workflow.id)}>
                        <Square className="h-4 w-4 mr-1" />
                        Stop
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => startWorkflow(workflow.id)}>
                        <Play className="h-4 w-4 mr-1" />
                        Start
                      </Button>
                    )}
                  </div>
                  <Link href={`/workflow/${workflow.id}`}>
                    <Button size="sm" variant="outline">
                      <Settings className="h-4 w-4 mr-1" />
                      Manage
                    </Button>
                  </Link>
                </div>
                {workflow.lastRun && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Last run: {new Date(workflow.lastRun).toLocaleString()}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {!loading && workflows.length === 0 && !error && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">No workflows found</p>
        </div>
      )}
    </div>
  )
}
