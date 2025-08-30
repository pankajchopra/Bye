import json
import logging
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import dspy
from dspy.signatures.signature import Signature

from app.tools import CustomerFetchTool, PortfolioFetchTool, PolicyRAGTool

logger = logging.getLogger(__name__)

# =============================================================================
# Data Models and Enums
# =============================================================================

class AgentType(Enum):
    MAIN_QUERY = "main_query"
    RETIREMENT = "retirement"
    ADVISOR = "advisor"

class TaskType(Enum):
    RISK_ANALYSIS = "risk_analysis"
    PORTFOLIO_FETCH = "portfolio_fetch"
    PORTFOLIO_COMPARE = "portfolio_compare"
    ADJUSTMENT_SUGGEST = "adjustment_suggest"
    RETIREMENT_REQUIREMENTS = "retirement_requirements"
    CUSTOMER_FETCH = "customer_fetch"

@dataclass
class FinancialTask:
    task_id: str
    task_type: TaskType
    assigned_agent: AgentType
    dependencies: List[str]
    parameters: Dict[str, Any]
    status: str = "pending"
    result: Optional[Dict] = None

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

class TaskExecutionSignature(Signature):
    """Execute a specific financial task with context"""
    task: str = dspy.InputField(desc="The specific task to execute")
    available_tools: str = dspy.InputField(desc="JSON of available tools and their descriptions")
    context: str = dspy.InputField(desc="Context from previous tasks")
    
    tool_selection: str = dspy.OutputField(desc="The best tool to use for the task")
    parameters: Dict[str, Any] = dspy.OutputField(desc="Parameters to pass to the tool")
    reasoning: str = dspy.OutputField(desc="Reasoning for the tool selection")

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

class TaskExecutor(dspy.Module):
    """Executes individual tasks using appropriate tools"""
    
    def __init__(self):
        super().__init__()
        self.execute = dspy.ChainOfThought(TaskExecutionSignature)
    
    def forward(self, task: FinancialTask, available_tools: Dict, context: Dict = None):
        """
        Determine which tool to use for a given task
        """
        tools_json = json.dumps({name: tool.description for name, tool in available_tools.items()})
        context_json = json.dumps(context or {})
        
        return self.execute(
            task=task.parameters["description"],
            available_tools=tools_json,
            context=context_json
        )

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
# Agent Implementations
# =============================================================================

class BaseFinancialAgent:
    """Base class for financial agents"""
    
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.task_executor = TaskExecutor()
        self.tools = self._initialize_tools()
        self.context = {}
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize available tools for this agent"""
        return {
            "customer_fetch": CustomerFetchTool(),
            "portfolio_fetch": PortfolioFetchTool(),
            "policy_rag": PolicyRAGTool()
        }
    
    async def execute_task(self, task: FinancialTask) -> Dict[str, Any]:
        """Execute a task assigned to this agent"""
        logger.info(f"{self.agent_type.value} executing task: {task.task_id}")
        
        # Use DSPy to determine which tool to use
        execution_plan = self.task_executor.forward(
            task=task,
            available_tools=self.tools,
            context=self.context
        )
        
        # Retrieves the selected tool from available tools and execute the selected tool
        selected_tool = self.tools.get(execution_plan["tool_selection"])
        if selected_tool:
            result = await selected_tool.execute(**execution_plan["parameters"])
            
            # Update context for future tasks
            self.context[task.task_id] = result
            
            return {
                "task_id": task.task_id,
                "status": "completed",
                "result": result,
                "reasoning": execution_plan["reasoning"]
            }
        else:
            return {
                "task_id": task.task_id,
                "status": "failed",
                "error": f"Tool {execution_plan['tool_selection']} not available"
            }

class MainQueryAgent(BaseFinancialAgent):
    """Main agent handling general financial queries"""
    
    def __init__(self):
        super().__init__(AgentType.MAIN_QUERY)
        self.capabilities = [
            "risk_analysis", "portfolio_analysis", "general_queries"
        ]

class RetirementAgent(BaseFinancialAgent):
    """Specialized agent for retirement-related queries"""
    
    def __init__(self):
        super().__init__(AgentType.RETIREMENT)
        self.capabilities = [
            "retirement_planning", "policy_lookup", "eligibility_check"
        ]
