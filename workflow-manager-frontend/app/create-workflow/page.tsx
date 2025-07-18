"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Bot, TrendingUp, Newspaper, MessageSquare } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

interface WorkflowTemplate {
  id: string
  name: string
  description: string
  category: string
  icon: React.ReactNode
  features: string[]
  configFields: {
    name: string
    type: string
    label: string
    description: string
    required: boolean
    defaultValue?: any
    options?: string[]
  }[]
}

export default function CreateWorkflowPage() {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  const fetchTemplates = async () => {
    try {
      const response = await fetch("/api/workflow-templates")
      const data = await response.json()
      setTemplates(data)
    } catch (error) {
      console.error("Failed to fetch templates:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTemplates()
  }, [])

  const selectTemplate = (templateId: string) => {
    router.push(`/create-workflow/configure/${templateId}`)
  }

  const getIcon = (category: string) => {
    switch (category) {
      case "social":
        return <MessageSquare className="h-8 w-8" />
      case "trading":
        return <TrendingUp className="h-8 w-8" />
      case "news":
        return <Newspaper className="h-8 w-8" />
      default:
        return <Bot className="h-8 w-8" />
    }
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case "social":
        return "bg-blue-500"
      case "trading":
        return "bg-green-500"
      case "news":
        return "bg-purple-500"
      default:
        return "bg-gray-500"
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex items-center gap-4 mb-8">
        <Link href="/">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Create New Workflow</h1>
          <p className="text-muted-foreground mt-2">Choose a template to get started</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => (
          <Card
            key={template.id}
            className="hover:shadow-lg transition-shadow cursor-pointer"
            onClick={() => selectTemplate(template.id)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between mb-3">
                <div className="p-2 rounded-lg bg-muted">{getIcon(template.category)}</div>
                <Badge className={getCategoryColor(template.category)}>{template.category}</Badge>
              </div>
              <CardTitle className="text-lg">{template.name}</CardTitle>
              <p className="text-sm text-muted-foreground">{template.description}</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div>
                  <h4 className="text-sm font-medium mb-2">Features:</h4>
                  <ul className="text-xs space-y-1">
                    {template.features.map((feature, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <div className="w-1 h-1 bg-current rounded-full"></div>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
                <Button className="w-full" onClick={() => selectTemplate(template.id)}>
                  Use This Template
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {templates.length === 0 && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">No templates available</p>
        </div>
      )}
    </div>
  )
}
