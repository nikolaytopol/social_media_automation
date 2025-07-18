"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { ArrowLeft, Save, Play } from "lucide-react"
import Link from "next/link"

interface ConfigField {
  name: string
  type: string
  label: string
  description: string
  required: boolean
  defaultValue?: any
  options?: string[]
}

interface WorkflowTemplate {
  id: string
  name: string
  description: string
  category: string
  configFields: ConfigField[]
}

export default function ConfigureWorkflowPage() {
  const params = useParams()
  const router = useRouter()
  const templateId = params.templateId as string

  const [template, setTemplate] = useState<WorkflowTemplate | null>(null)
  const [config, setConfig] = useState<Record<string, any>>({})
  const [workflowName, setWorkflowName] = useState("")
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const fetchTemplate = async () => {
    try {
      const response = await fetch(`/api/workflow-templates/${templateId}`)
      const data = await response.json()
      setTemplate(data)

      // Initialize config with default values
      const initialConfig: Record<string, any> = {}
      data.configFields.forEach((field: ConfigField) => {
        initialConfig[field.name] = field.defaultValue || ""
      })
      setConfig(initialConfig)
    } catch (error) {
      console.error("Failed to fetch template:", error)
    } finally {
      setLoading(false)
    }
  }

  const updateConfig = (fieldName: string, value: any) => {
    setConfig((prev) => ({ ...prev, [fieldName]: value }))
  }

  const createWorkflow = async (startImmediately = false) => {
    if (!workflowName.trim()) {
      alert("Please enter a workflow name")
      return
    }

    setCreating(true)
    try {
      const response = await fetch("/api/workflows/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          templateId,
          name: workflowName,
          config,
          startImmediately,
        }),
      })

      const result = await response.json()
      if (result.success) {
        router.push(`/workflow/${result.workflowId}`)
      } else {
        alert("Failed to create workflow: " + result.error)
      }
    } catch (error) {
      console.error("Failed to create workflow:", error)
      alert("Failed to create workflow")
    } finally {
      setCreating(false)
    }
  }

  useEffect(() => {
    fetchTemplate()
  }, [templateId])

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
        </div>
      </div>
    )
  }

  if (!template) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-muted-foreground">Template not found</p>
          <Link href="/create-workflow">
            <Button className="mt-4">Back to Templates</Button>
          </Link>
        </div>
      </div>
    )
  }

  const renderConfigField = (field: ConfigField) => {
    switch (field.type) {
      case "text":
        return (
          <Input
            value={config[field.name] || ""}
            onChange={(e) => updateConfig(field.name, e.target.value)}
            placeholder={field.description}
          />
        )
      case "textarea":
        return (
          <Textarea
            value={config[field.name] || ""}
            onChange={(e) => updateConfig(field.name, e.target.value)}
            placeholder={field.description}
            rows={3}
          />
        )
      case "number":
        return (
          <Input
            type="number"
            value={config[field.name] || ""}
            onChange={(e) => updateConfig(field.name, Number.parseFloat(e.target.value) || 0)}
            placeholder={field.description}
          />
        )
      case "select":
        return (
          <Select value={config[field.name] || ""} onValueChange={(value) => updateConfig(field.name, value)}>
            <SelectTrigger>
              <SelectValue placeholder={field.description} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )
      case "boolean":
        return (
          <div className="flex items-center space-x-2">
            <Switch
              checked={config[field.name] || false}
              onCheckedChange={(checked) => updateConfig(field.name, checked)}
            />
            <span className="text-sm text-muted-foreground">{field.description}</span>
          </div>
        )
      default:
        return (
          <Input
            value={config[field.name] || ""}
            onChange={(e) => updateConfig(field.name, e.target.value)}
            placeholder={field.description}
          />
        )
    }
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <div className="flex items-center gap-4 mb-8">
        <Link href="/create-workflow">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Templates
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Configure {template.name}</h1>
          <p className="text-muted-foreground mt-2">{template.description}</p>
        </div>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="workflow-name">Workflow Name *</Label>
              <Input
                id="workflow-name"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                placeholder="Enter a unique name for your workflow"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {template.configFields.map((field) => (
              <div key={field.name} className="space-y-2">
                <Label htmlFor={field.name}>
                  {field.label} {field.required && "*"}
                </Label>
                {renderConfigField(field)}
                {field.description && <p className="text-xs text-muted-foreground">{field.description}</p>}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Configuration Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
              {JSON.stringify({ name: workflowName, ...config }, null, 2)}
            </pre>
          </CardContent>
        </Card>

        <div className="flex gap-4">
          <Button onClick={() => createWorkflow(false)} disabled={creating}>
            <Save className="h-4 w-4 mr-2" />
            {creating ? "Creating..." : "Create Workflow"}
          </Button>
          <Button onClick={() => createWorkflow(true)} disabled={creating}>
            <Play className="h-4 w-4 mr-2" />
            {creating ? "Creating..." : "Create & Start"}
          </Button>
        </div>
      </div>
    </div>
  )
}
