# DSPy Financial Advisor System - Setup Instructions

## 🚀 Quick Start

### 1. Install Dependencies
```bash

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
cp .env.example .env
# Edit .env with your API keys
export OPENAI_API_KEY="your_openai_api_key_here"
```

### 3. Run the System
```bash
# Test the DSPy system directly
python dspy_financial_system.py

# Or run as web service
uvicorn dspy_financial_system:app --host 0.0.0.0 --port 8000 --reload
```

## 🧪 Testing Your Complex Query

The system is designed to handle your exact use case:

```python
complex_query = """
Show me the client John Doe's risk profile, then compare it with his portfolio allocation, 
then suggest an adjustment, and also give me what are the basic requirements for this 
client's retirement plan.
"""
```

## 🔧 Key Components

### DSPy Modules (The Intelligence Layer)
- **QueryDecomposer**: Breaks down complex queries intelligently
- **TaskExecutor**: Executes tasks using appropriate tools
- **AgentCoordinator**: Manages agent-to-agent communication

### Agent Architecture
- **MainQueryAgent**: Handles risk analysis, portfolio queries
- **RetirementAgent**: Specialized for retirement planning
- **BaseFinancialAgent**: Common functionality and tool access

### MCP Tool Integration
- **CustomerFetchTool**: Retrieves customer data via MCP
- **PortfolioFetchTool**: Fetches portfolio information
- **PolicyRAGTool**: Queries company policies using RAG

## 🌊 How It Handles a Complex Query

1. **Query Decomposition** (DSPy Intelligence):
   ```
   "Show me client's risk profile..." 
   ↓
   Task 1: Fetch customer data
   Task 2: Analyze risk profile  
   Task 3: Fetch portfolio
   Task 4: Compare allocation vs risk
   Task 5: Suggest adjustments
   Task 6: Check retirement requirements
   ```

2. **Agent Assignment** (Dynamic):
   ```
   Tasks 1-5 → MainQueryAgent
   Task 6 → RetirementAgent
   ```

3. **Tool Selection** (DSPy-powered):
   ```
   Task 1 → CustomerFetchTool
   Task 2 → Internal analysis
   Task 3 → PortfolioFetchTool  
   Task 6 → PolicyRAGTool
   ```

4. **A2A Communication**:
   ```
   MainQueryAgent ←→ RetirementAgent
   Via structured messages and SSE
   ```

## 🔄 Dynamic vs Static Elements

### What DSPy does (Dynamically):
- Task breakdown from any complex query
- Tool selection based on requirements
- Agent routing decisions
- Parameter extraction for tools

### What we need defines (Static):
- Module structure and signatures
- Available tools and agents
- Communication protocols
- Error handling patterns

## 🎯 Real-World Integration

### With Existing Stack(LangGraph-LangChain-MCP):
```python
# LangGraph integration
from langgraph.graph import StateGraph

# Your existing MCP client
from your_mcp_client import MCPClient

# Integrate DSPy system
financial_system = FinancialAdvisorSystem()

# Use in LangGraph workflow
def create_langgraph_with_dspy():
    workflow = StateGraph(FinancialState)
    workflow.add_node("dspy_analysis", lambda state: 
        financial_system.process_complex_query(state.query)
    )
    return workflow.compile()
```

## 🔍 Monitoring and Debugging

### Logging Output Example:
```
INFO: Processing complex query: Show me the client's risk profile...
INFO: Query decomposed into 6 tasks
INFO: main_query executing task: task_0
INFO: Coordinating task task_5 with retirement
INFO: Tasks completed successfully
```

### API Endpoints:
- `POST /query` - Process financial queries
- `GET /stream/{query_id}` - SSE for progress updates

## 🚨 Important Notes

1. **Mock Data**: Current implementation uses mock data for demonstration
2. **MCP Integration**: Replace mock tools with actual MCP calls
3. **Error Handling**: Includes basic error handling, extend as needed
4. **Security**: Add authentication and authorization for production

## 🔧 Customization

### Adding New Task Types:
```python
class TaskType(Enum):
    RISK_ANALYSIS = "risk_analysis"
    YOUR_NEW_TASK = "your_new_task"  # Add here

class YourNewTool(MCPTool):
    def __init__(self):
        super().__init__("your_tool", "Description")
    
    async def execute(self, **kwargs):
        # Your implementation
        pass
```

### Adding New Agents:
```python
class YourSpecializedAgent(BaseFinancialAgent):
    def __init__(self):
        super().__init__(AgentType.YOUR_AGENT)
        self.capabilities = ["your_capability"]
```

## 📊 Performance Considerations

- **Async Operations**: All tool calls are async for better performance
- **Context Management**: Efficient context passing between tasks
- **Error Recovery**: Graceful handling of tool failures
- **Caching**: Consider adding Redis for production caching

Ready to proceed to the next step or need clarification on any part?