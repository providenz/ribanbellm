"""A scripted stand-in for the LLM that drives the character agents in tests."""

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


class Scripted(FunctionModel):
    """Answers turns and reflections from queues, and records what each call saw."""

    def __init__(self, turns: list[dict | Exception], reflections: list[dict | Exception] | None = None):
        self.turns = list(turns)
        self.reflections = list(reflections or [reflection(0), reflection(0)])
        self.calls: list[str] = []  # instructions + prompt of each call
        super().__init__(self._respond)

    def _respond(self, messages, info: AgentInfo) -> ModelResponse:
        prompt = ' '.join(str(getattr(part, 'content', '')) for part in messages[-1].parts)
        self.calls.append(f'{info.instructions}\n{prompt}')
        tool = info.output_tools[0]
        queue = self.turns if 'leave' in tool.parameters_json_schema['properties'] else self.reflections
        answer = queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ModelResponse(parts=[ToolCallPart(tool.name, answer)])


def turn(text='Bonjour.', emotion='neutral', leave=False) -> dict:
    return {'text': text, 'emotion': emotion, 'leave': leave}


def reflection(delta: int, text='Souvenir.') -> dict:
    return {'memory': {'text': text}, 'feeling_delta': delta}
