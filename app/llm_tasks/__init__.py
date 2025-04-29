# app/llm_tasks/__init__.py

# Make tasks easily importable
from .router_task import BaseRouterTask, RouterTask, MockRouterTask, RouterOutput, RoutingError
from .summarizer_task import BaseSummarizerTask, SummarizerTask, MockSummarizerTask, SummarizationError

# Import factory functions
from .router_task import get_router_task
from .summarizer_task import get_summarizer_task

# from .summarizer_task import SummarizerTask, MockSummarizerTask 