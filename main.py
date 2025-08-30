"""
DSPy Financial Advisor System
Complete working implementation with MCP integration, LangGraph, and multi-agent coordination
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# DSPy imports
import dspy
from dspy import ChainOfThought, Module, Signature

# LangGraph and LangChain imports
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, AIMessage

# Local imports
from app.agents import (
    AgentType,
    FinancialTask,
    MainQueryAgent,
    RetirementAgent,
    AgentCoordinator,
    TaskType
)
from app.tools import CustomerFetchTool, PortfolioFetchTool, PolicyRAGTool, CustomerData
from app.sse import SSEManager

# Async and networking
import httpx
from pydantic import BaseModel, Field

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# DSPy Configuration and Setup
# =============================================================================

# Configure DSPy with your LLM
dspy.configure(
    lm=dspy.OpenAI(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        max_tokens=2000
    )
)

# =============================================================================
# Data Models and Enums
# =============================================================================

@dataclass
class CustomerData:
    customer_id: str
    name: str
    account_number: str
    risk_tolerance: str
    age: int
    portfolio_value: float

@dataclass
class AgentCommunication:
    from_agent: AgentType
    to_agent: AgentType
    task_id: str
    message: Dict[str, Any]
    timestamp: datetime

# =============================================================================
# DSPy Signatures - Define Input/Output Contracts
# =============================================================================

class QueryDecompositionSignature(Signature):
    """Break down complex financial queries into executable tasks"""
    complex_query: str = dspy.InputField(desc="The complex financial query from the user")
    customer_context: str = dspy.InputField(desc="Available customer context")
    
    tasks: List[str] = dspy.OutputField(desc="List of specific tasks to execute")
    task_sequence: List[int] = dspy.OutputField(desc="Execution order (task indices)")
    agent_assignments: Dict[str, str] = dspy.OutputField(desc="Which agent handles each task")
    tool_requirements: Dict[str, List[str]] = dspy.OutputField(desc="Tools needed for each task")

class TaskExecutionSignature(Signature):
    """Execute a specific financial task with context"""
    task_description: str = dspy.InputField(desc="What task to execute")
    available_tools: str = dspy.InputField(desc="JSON string of available tools")
    context_data: str = dspy.InputField(desc="Previous task results as context")
    
    tool_selection: str = dspy.OutputField(desc="Selected tool name")
    tool_parameters: Dict[str, Any] = dspy.OutputField(desc="Parameters for the tool")
    reasoning: str = dspy.OutputField(desc="Why this tool and parameters were chosen")

class AgentCoordinationSignature(Signature):
    """Coordinate between agents for complex tasks"""
    current_task: str = dspy.InputField(desc="Task that needs agent coordination")
    available_agents: str = dspy.InputField(desc="JSON of available agents and capabilities")
    task_context: str = dspy.InputField(desc="Context from previous tasks")
    
    target_agent: str = dspy.OutputField(desc="Which agent should handle this")
    message_format: Dict[str, Any] = dspy.OutputField(desc="Structured message to send")
    expected_response: str = dspy.OutputField(desc="What response format to expect")

# =============================================================================
# DSPy Modules - Core Intelligence Components
# =============================================================================

class QueryDecomposer(dspy.Module):
    """Intelligently breaks down complex financial queries into executable tasks"""
    
    def __init__(self):
        super().__init__()
        self.decompose = dspy.ChainOfThought(QueryDecompositionSignature)
    
    def forward(self, complex_query: str, customer_context: str = ""):
        """
        Takes a complex query and returns structured task breakdown
        """
        result = self.decompose(
            complex_query=complex_query,
            customer_context=customer_context
        )
        
        # Convert to structured task objects
        tasks = []
        for i, task_desc in enumerate(result.tasks):
            task = FinancialTask(
                task_id=f"task_{i}",
                task_type=self._classify_task_type(task_desc),
                assigned_agent=AgentType(result.agent_assignments.get(str(i), "main_query")),
                dependencies=self._extract_dependencies(i, result.task_sequence),
                parameters={"description": task_desc}
            )
            tasks.append(task)
        
        return {
            "tasks": tasks,
            "execution_order": result.task_sequence,
            "tool_requirements": result.tool_requirements
        }
    
    def _classify_task_type(self, task_desc: str) -> TaskType:
        """Classify task description into TaskType enum"""
        task_lower = task_desc.lower()
        if "risk" in task_lower:
            return TaskType.RISK_ANALYSIS
        elif "portfolio" in task_lower and "fetch" in task_lower:
            return TaskType.PORTFOLIO_FETCH
        elif "compare" in task_lower:
            return TaskType.PORTFOLIO_COMPARE
        elif "adjust" in task_lower or "suggest" in task_lower:
            return TaskType.ADJUSTMENT_SUGGEST
        elif "retirement" in task_lower:
            return TaskType.RETIREMENT_REQUIREMENTS
        else:
            return TaskType.CUSTOMER_FETCH
    
    def _extract_dependencies(self, task_index: int, sequence: List[int]) -> List[str]:
        """Extract task dependencies based on execution sequence"""
        dependencies = []
        task_position = sequence.index(task_index) if task_index in sequence else 0
        for i in range(task_position):
            dependencies.append(f"task_{sequence[i]}")
        return dependencies

class TaskExecutor(dspy.Module):
    """Executes individual tasks using appropriate tools"""
    
    def __init__(self):
        super().__init__()
        self.execute = dspy.ChainOfThought(TaskExecutionSignature)
    
    def forward(self, task: FinancialTask, available_tools: Dict, context: Dict = None):
        """
        Execute a specific task with available tools and context
        """
        tools_json = json.dumps({name: tool.description for name, tool in available_tools.items()})
        context_json = json.dumps(context or {})
        
        result = self.execute(
            task_description=task.parameters["description"],
            available_tools=tools_json,
            context_data=context_json
        )
        
        return {
            "tool_selection": result.tool_selection,
            "parameters": result.tool_parameters,
            "reasoning": result.reasoning
        }

class AgentCoordinator(dspy.Module):
    """Coordinates communication between different agents"""
    
    def __init__(self):
        super().__init__()
        self.coordinate = dspy.ChainOfThought(AgentCoordinationSignature)
    
    def forward(self, task: FinancialTask, available_agents: Dict, context: Dict = None):
        """
        Determine how to coordinate with other agents for task completion
        """
        agents_json = json.dumps({
            agent_type.value: capabilities 
            for agent_type, capabilities in available_agents.items()
        })
        context_json = json.dumps(context or {})
        
        result = self.coordinate(
            current_task=task.parameters["description"],
            available_agents=agents_json,
            task_context=context_json
        )
        
        return AgentCommunication(
            from_agent=task.assigned_agent,
            to_agent=AgentType(result.target_agent),
            task_id=task.task_id,
            message=result.message_format,
            timestamp=datetime.now()
        )

# =============================================================================
# MCP Tool Integration
# =============================================================================

# Tools are now imported from app.tools

# =============================================================================
# Financial Advisor Orchestrator - Main DSPy System
# =============================================================================

class FinancialAdvisorSystem(dspy.Module):
    """
    Main orchestrator that handles complex multi-task financial queries
    This is where DSPy's power shines - one intelligent system handling any query
    """
    
    def __init__(self):
        super().__init__()
        
        # DSPy modules for intelligence
        self.query_decomposer = QueryDecomposer()
        self.agent_coordinator = AgentCoordinator()
        
        # Initialize agents
        self.agents = {
            AgentType.MAIN_QUERY: MainQueryAgent(),
            AgentType.RETIREMENT: RetirementAgent()
        }
        
        # Agent capabilities for coordination
        self.agent_capabilities = {
            AgentType.MAIN_QUERY: ["risk_analysis", "portfolio_analysis", "general_queries"],
            AgentType.RETIREMENT: ["retirement_planning", "policy_lookup", "eligibility_check"]
        }
        
        # Task execution context
        self.execution_context = {}
        
    async def process_complex_query(self, query: str, customer_context: str = "") -> Dict[str, Any]:
        """
        Main entry point - processes any complex financial query
        This demonstrates DSPy's ability to handle dynamic, complex scenarios
        """
        logger.info(f"Processing complex query: {query}")
        
        # Step 1: Use DSPy to decompose the query intelligently
        decomposition_result = self.query_decomposer.forward(
            complex_query=query,
            customer_context=customer_context
        )
        
        tasks = decomposition_result["tasks"]
        execution_order = decomposition_result["execution_order"]
        
        logger.info(f"Query decomposed into {len(tasks)} tasks")
        
        # Step 2: Execute tasks in the determined order
        completed_tasks = []
        for task_index in execution_order:
            if task_index < len(tasks):
                task = tasks[task_index]
                result = await self._execute_task_with_coordination(task)
                completed_tasks.append(result)
                
                # Update execution context for dependent tasks
                self.execution_context[task.task_id] = result
        
        # Step 3: Synthesize final response
        return self._synthesize_response(query, completed_tasks)
    
    async def _execute_task_with_coordination(self, task: FinancialTask) -> Dict[str, Any]:
        """
        Execute a task with intelligent agent coordination
        Determining if a task needs coordination between agents
        1. Routing tasks to the appropriate specialized agent
        2. Executing the task and returning results
        3. Code Analysis
        """
        # Determine if task needs agent coordination
        if task.assigned_agent != AgentType.MAIN_QUERY:
            # Use DSPy to coordinate with specialized agent
            coordination = self.agent_coordinator.forward(
                task=task,
                available_agents=self.agent_capabilities,
                context=self.execution_context
            )
            
            logger.info(f"Coordinating task {task.task_id} with {coordination.to_agent.value}")
        
        # Execute task with assigned agent
        assigned_agent = self.agents[task.assigned_agent]
        result = await assigned_agent.execute_task(task)
        
        return result
    
    def _synthesize_response(self, original_query: str, completed_tasks: List[Dict]) -> Dict[str, Any]:
        """
        Synthesize final response from completed tasks
        """
        return {
            "original_query": original_query,
            "status": "completed",
            "tasks_completed": len(completed_tasks),
            "results": completed_tasks,
            "synthesis": "Tasks completed successfully. Results available in tasks_completed.",
            "timestamp": datetime.now().isoformat()
        }

# =============================================================================
# Module Exports
# =============================================================================

__all__ = ['FinancialAdvisorSystem']

# =============================================================================
# Example Usage and Testing
# =============================================================================

async def main():
    """
    Example usage of the DSPy Financial Advisor System
    """
    
    # Initialize the system
    advisor_system = FinancialAdvisorSystem()
    
    # Your complex multi-task query example
    complex_query = """
    Show me the client John Doe's risk profile, then compare it with his portfolio allocation, 
    then suggest an adjustment, and also give me what are the basic requirements for this 
    client's retirement plan.
    """
    
    customer_context = "Client: John Doe, Account: Premium customer since 2015"
    
    try:
        # Process the complex query
        result = await advisor_system.process_complex_query(
            query=complex_query,
            customer_context=customer_context
        )
        
        print("=" * 80)
        print("DSPy FINANCIAL ADVISOR SYSTEM - COMPLEX QUERY RESULTS")
        print("=" * 80)
        print(f"Original Query: {result['original_query']}")
        print(f"Status: {result['status']}")
        print(f"Tasks Completed: {result['tasks_completed']}")
        print("\nDetailed Results:")
        
        for i, task_result in enumerate(result['results'], 1):
            print(f"\n--- Task {i}: {task_result['task_id']} ---")
            print(f"Status: {task_result['status']}")
            if 'result' in task_result:
                print(f"Result: {json.dumps(task_result['result'], indent=2)}")
            if 'reasoning' in task_result:
                print(f"Reasoning: {task_result['reasoning']}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    # For testing the system
    asyncio.run(main())
    
    # For running the web server
    # uvicorn.run(app, host="0.0.0.0", port=8000)