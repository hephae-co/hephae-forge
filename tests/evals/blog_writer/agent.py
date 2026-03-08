"""Eval wrapper — wraps research_compiler_agent + blog_writer_agent in a
SequentialAgent for ADK AgentEvaluator.

The blog writer pipeline runs two LlmAgents sequentially:
  1. ResearchCompilerAgent: compiles a structured research brief from business analysis data
  2. BlogWriterAgent: generates the full HTML blog post from the research brief
"""

from google.adk.agents import SequentialAgent

from hephae_capabilities.social.blog_writer.agent import (
    research_compiler_agent,
    blog_writer_agent,
)

root_agent = SequentialAgent(
    name="BlogWriterPipeline",
    description="Full blog generation: compile research brief then write the HTML post.",
    sub_agents=[research_compiler_agent, blog_writer_agent],
)

__all__ = ["root_agent"]
