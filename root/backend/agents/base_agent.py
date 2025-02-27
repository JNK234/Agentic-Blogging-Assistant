"""
Base agent implementation.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from langgraph.graph import StateGraph

class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    """
    def __init__(
        self,
        llm: Any,
        tools: List,
        verbose: bool = True
    ):
        """
        Initialize the base agent.
        
        Args:
            llm: Language model instance
            tools: List of tools available to the agent
            verbose: Whether to enable verbose logging
        """
        self.llm = llm
        self.tools = tools
        self.verbose = verbose
        
    async def initialize(self) -> None:
        """
        Initialize the agent.
        """
        await self._post_initialize()
    
    @abstractmethod
    async def _post_initialize(self) -> None:
        """
        Hook for additional initialization steps in derived classes.
        """
        pass
    
    @abstractmethod
    async def run(self, input_text: str) -> str:
        """
        Run the agent with the given input.
        
        Args:
            input_text: Input text to process
            
        Returns:
            str: Agent's response
        """
        pass

class BaseGraphAgent(BaseAgent):
    """
    Base class for agents that use graph-based processing.
    """
    def __init__(self, llm, tools, state_class, verbose=True):
        super().__init__(llm, tools, verbose=verbose)
        self.state_class = state_class
        self.graph = None

    async def _post_initialize(self) -> None:
        """Initialize the graph after agent setup."""
        pass

    async def run(self, input_text: str) -> str:
        """
        Run the agent with the given input.
        
        Args:
            input_text: Input text to process
            
        Returns:
            str: Agent's response
        """
        raise NotImplementedError("BaseGraphAgent does not implement run method directly")
            
    async def run_graph(self, initial_state: Any) -> Any:
        """Execute the graph with initial state."""
        if not self.graph:
            raise ValueError("Graph not initialized")
        return await self.graph.ainvoke(initial_state)
