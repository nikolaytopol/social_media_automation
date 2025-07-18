"use client"

import { useState, useEffect, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowLeft, Play, Square, Save, RefreshCw, Send } from "lucide-react"
import Link from "next/link"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileText, Folder, ImageIcon, AlertTriangle } from "lucide-react"

interface Tweet {
  id: string
  text: string
  timestamp: string
  media?: string[]
  otherFiles?: string[]
  canMarkIncorrect?: boolean
  source?: string
  __json_path?: string // Add this property for backend compatibility
}

interface WorkflowDetails {
  id: string
  name: string
  status: "running" | "stopped" | "error"
  description?: string
  retrainingMessages: string[]
  config: Record<string, any>
  postedTweets?: Tweet[]
  receivedTweets?: Tweet[]
}

export default function WorkflowDetailPage() {
  const params = useParams()
  const router = useRouter()
  const workflowId = params.id as string

  const [workflow, setWorkflow] = useState<WorkflowDetails | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [retrainingMessage, setRetrainingMessage] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [postedTweets, setPostedTweets] = useState<Tweet[]>([])
  const [receivedTweets, setReceivedTweets] = useState<Tweet[]>([])
  const [error, setError] = useState<string | null>(null)

  const logsEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const fetchWorkflowDetails = async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch workflow info
      const res = await fetch(`http://localhost:9000/workflow/info?name=${workflowId}`)
      if (!res.ok) throw new Error("Failed to fetch workflow info")
      const data = await res.json()
      setWorkflow({
        id: data.name,
        name: data.name,
        status: data.status,
        description: data.description || '',
        retrainingMessages: data.retrainingMessages || [],
        config: data.config || {},
      })
      setRetrainingMessage(data.retrainingMessages?.join("\n") || "")

      // Fetch posted messages
      const postedRes = await fetch(`http://localhost:9000/workflow/${workflowId}/messages/posted`)
      const postedRaw = await postedRes.json()
      const posted = postedRaw.map((msg: any) => ({
        id: msg.dir || msg.id || Math.random().toString(36),
        text: msg.current_message_preview || msg.text || "",
        media: msg.media || [],
        __json_path: `/Users/userok/Desktop/Social_Media_CURSOR_2/workflows/${workflowId}/posted_messages/${msg.dir}`,
        ...msg
      }))
      setPostedTweets(posted)

      // Fetch received messages
      const receivedRes = await fetch(`http://localhost:9000/workflow/${workflowId}/messages/history`)
      const receivedRaw = await receivedRes.json()
      const received = receivedRaw.map((msg: any) => ({
        id: msg.dir || msg.id || Math.random().toString(36),
        text: msg.current_message_preview || msg.text || "",
        media: msg.media || [],
        __json_path: `/Users/userok/Desktop/Social_Media_CURSOR_2/workflows/${workflowId}/message_history/${msg.dir}`,
        ...msg
      }))
      setReceivedTweets(received)

      // Fetch logs
      const logsRes = await fetch(`http://localhost:9000/logs?name=${workflowId}&lines=40`)
      if (logsRes.ok) {
        const logsText = await logsRes.text()
        setLogs(logsText.split('\n').filter(Boolean))
      } else {
        setLogs([])
      }
    } catch (err: any) {
      setError("Failed to load workflow details. Backend may be unavailable.")
      setWorkflow(null)
      setPostedTweets([])
      setReceivedTweets([])
      setLogs([])
    } finally {
      setLoading(false)
    }
  }

  const startWorkflow = async () => {
    setError(null)
    try {
      const res = await fetch(`http://localhost:9000/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: workflowId }),
      })
      const data = await res.json()
      if (data.status !== "success") {
        setError(`Failed to start workflow: ${data.message || "Unknown error"}`)
      }
      fetchWorkflowDetails()
    } catch (error) {
      setError("Failed to start workflow. Backend unavailable.")
    }
  }

  const stopWorkflow = async () => {
    setError(null)
    try {
      const res = await fetch(`http://localhost:9000/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: workflowId }),
      })
      const data = await res.json()
      if (data.status !== "success") {
        setError(`Failed to stop workflow: ${data.message || "Unknown error"}`)
      }
      fetchWorkflowDetails()
    } catch (error) {
      setError("Failed to stop workflow. Backend unavailable.")
    }
  }

  // Mark as incorrect: expects tweet object to have a __json_path property
  const markTweetIncorrect = async (tweetId: string, jsonPath: string, tweetType: string) => {
    setError(null)
    try {
      const res = await fetch(`http://localhost:9000/mark_incorrect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          json_path: jsonPath,
          tweet_type: tweetType,
          comment: "", // Optionally add a comment field
        }),
      })
      const data = await res.json()
      if (!data.success) {
        setError(`Failed to mark tweet as incorrect: ${data.error || "Unknown error"}`)
      } else {
        fetchWorkflowDetails()
      }
    } catch (error) {
      setError("Failed to mark tweet as incorrect. Backend unavailable.")
    }
  }

  const sendForRetraining = async () => {
    setSaving(true)
    try {
      await fetch(`/api/workflows/${workflowId}/send-retraining`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: retrainingMessage.split("\n").filter((msg) => msg.trim()),
        }),
      })
      // Show success message or update UI
      console.log("Sent for retraining successfully")
    } catch (error) {
      console.error("Failed to send for retraining:", error)
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    fetchWorkflowDetails()
    // Optionally, set up polling for logs/messages
    const interval = setInterval(fetchWorkflowDetails, 10000)
    return () => clearInterval(interval)
  }, [workflowId])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <div className="mb-4 p-4 bg-red-100 text-red-700 rounded border border-red-300">
          {error}
        </div>
        <Link href="/">
          <Button className="mt-4">Back to Dashboard</Button>
        </Link>
      </div>
    )
  }

  if (!workflow) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-muted-foreground">Workflow not found</p>
          <Link href="/">
            <Button className="mt-4">Back to Dashboard</Button>
          </Link>
        </div>
      </div>
    )
  }

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
      <div className="flex items-center gap-4 mb-6">
        <Link href="/">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{workflow.name}</h1>
            <Badge className={getStatusColor(workflow.status)}>{workflow.status}</Badge>
          </div>
          {workflow.description && <p className="text-muted-foreground mt-1">{workflow.description}</p>}
        </div>
        <div className="flex gap-2">
          {workflow.status === "running" ? (
            <Button variant="destructive" onClick={stopWorkflow}>
              <Square className="h-4 w-4 mr-2" />
              Stop Workflow
            </Button>
          ) : (
            <Button onClick={startWorkflow}>
              <Play className="h-4 w-4 mr-2" />
              Start Workflow
            </Button>
          )}
        </div>
      </div>

      <Tabs defaultValue="logs" className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="logs">Real-time Logs</TabsTrigger>
          <TabsTrigger value="files">File Structure</TabsTrigger>
          <TabsTrigger value="tweets">Tweet Management</TabsTrigger>
          <TabsTrigger value="retraining">Retraining</TabsTrigger>
          <TabsTrigger value="config">Configuration</TabsTrigger>
        </TabsList>

        <TabsContent value="logs">
          <Card>
            <CardHeader>
              <CardTitle>Live Logs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-black text-green-400 p-4 rounded-lg h-96 overflow-y-auto font-mono text-sm">
                {logs.length === 0 ? (
                  <div className="text-gray-500">Waiting for logs...</div>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} className="mb-1">
                      {log}
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="files">
          <Card>
            <CardHeader>
              <CardTitle>Workflow File Structure</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex items-center gap-2 font-medium">
                  <Folder className="h-4 w-4" />
                  {workflow.name}
                </div>
                <div className="ml-6 space-y-1">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Folder className="h-3 w-3" />
                    __pycache__
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Folder className="h-3 w-3" />
                    logs
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Folder className="h-3 w-3" />
                    message_history
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Folder className="h-3 w-3" />
                    posted_messages
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Folder className="h-3 w-3" />
                    retraining
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <FileText className="h-3 w-3" />
                    .env
                  </div>
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <FileText className="h-3 w-3" />
                    {workflow.id}_main.py
                  </div>
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <FileText className="h-3 w-3" />
                    test_twitter_connection.py
                  </div>
                  <div className="flex items-center gap-2 text-sm text-yellow-600">
                    <FileText className="h-3 w-3" />
                    .workflow_state.json
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tweets">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Posted Tweets</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-96">
                  <div className="space-y-4">
                    {postedTweets.map((tweet) => (
                      <div key={tweet.id} className="border rounded-lg p-4 space-y-3">
                        <div className="text-sm font-medium">Text:</div>
                        <div className="text-sm whitespace-pre-wrap bg-muted p-3 rounded">{tweet.text}</div>

                        {tweet.media && tweet.media.length > 0 && (
                          <div>
                            <div className="text-sm font-medium mb-2">Media:</div>
                            <div className="flex gap-2">
                              {tweet.media.map((media, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center gap-1 text-xs bg-blue-100 px-2 py-1 rounded"
                                >
                                  <ImageIcon className="h-3 w-3" />
                                  {media}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {tweet.otherFiles && tweet.otherFiles.length > 0 && (
                          <div>
                            <div className="text-sm font-medium mb-2">Other files:</div>
                            <ul className="text-xs space-y-1">
                              {tweet.otherFiles.map((file, idx) => (
                                <li key={idx} className="flex items-center gap-1">
                                  <FileText className="h-3 w-3" />
                                  <span className="text-blue-600 underline cursor-pointer">{file}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {tweet.canMarkIncorrect && tweet.__json_path && (
                          <Button variant="destructive" size="sm" onClick={() => markTweetIncorrect(tweet.id, tweet.__json_path!, "posted_messages")}>
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Mark as Incorrect
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Received Tweets</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-96">
                  <div className="space-y-4">
                    {receivedTweets.map((tweet) => (
                      <div key={tweet.id} className="border rounded-lg p-4 space-y-3">
                        <div className="text-sm font-medium">Text:</div>
                        <div className="text-sm whitespace-pre-wrap bg-muted p-3 rounded">{tweet.text}</div>

                        {tweet.source && <div className="text-xs text-muted-foreground">Source: {tweet.source}</div>}

                        {tweet.media && tweet.media.length > 0 && (
                          <div>
                            <div className="text-sm font-medium mb-2">Media:</div>
                            <div className="flex gap-2">
                              {tweet.media.map((media, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center gap-1 text-xs bg-blue-100 px-2 py-1 rounded"
                                >
                                  <ImageIcon className="h-3 w-3" />
                                  {media}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {tweet.otherFiles && tweet.otherFiles.length > 0 && (
                          <div>
                            <div className="text-sm font-medium mb-2">Other files:</div>
                            <ul className="text-xs space-y-1">
                              {tweet.otherFiles.map((file, idx) => (
                                <li key={idx} className="flex items-center gap-1">
                                  <FileText className="h-3 w-3" />
                                  <span className="text-blue-600 underline cursor-pointer">{file}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {tweet.canMarkIncorrect && tweet.__json_path && (
                          <Button variant="destructive" size="sm" onClick={() => markTweetIncorrect(tweet.id, tweet.__json_path!, "message_history")}>
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Mark as Incorrect
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="retraining">
          <Card>
            <CardHeader>
              <CardTitle>Retraining Messages</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="retraining-messages">Messages (one per line)</Label>
                <Textarea
                  id="retraining-messages"
                  value={retrainingMessage}
                  onChange={(e) => setRetrainingMessage(e.target.value)}
                  placeholder="Enter retraining messages, one per line..."
                  className="min-h-32 font-mono"
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={sendForRetraining} disabled={saving}>
                  <Send className="h-4 w-4 mr-2" />
                  Send for Retraining
                </Button>
              </div>

              {workflow.retrainingMessages && workflow.retrainingMessages.length > 0 && (
                <div className="mt-4">
                  <h4 className="font-medium mb-2">Current Messages:</h4>
                  <div className="bg-muted p-3 rounded-lg">
                    {workflow.retrainingMessages.map((msg, index) => (
                      <div key={index} className="text-sm mb-1">
                        {index + 1}. {msg}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="config">
          <Card>
            <CardHeader>
              <CardTitle>Workflow Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="workflow-id">Workflow ID</Label>
                  <Input id="workflow-id" value={workflow.id} disabled />
                </div>
                <div>
                  <Label htmlFor="workflow-name">Name</Label>
                  <Input id="workflow-name" value={workflow.name} disabled />
                </div>
                {workflow.config && Object.keys(workflow.config).length > 0 && (
                  <div>
                    <Label>Configuration</Label>
                    <pre className="bg-muted p-3 rounded-lg text-sm overflow-x-auto">
                      {JSON.stringify(workflow.config, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
