from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Config:
    top_k: int = 2
    positive_top_k: int = 1
    max_rounds: int = 3
    max_retrieval_calls: int = 9
    max_module_calls: int = 24
    max_work_tokens: int = 40000
    max_llm_tokens: int = 8000
    max_output_tokens: int = 800
    timeout_seconds: float = 45.0
    max_seconds: float = 90.0
    boundary_penalty: float = 0.55

    def __post_init__(self):
        for key in ('top_k', 'positive_top_k', 'max_rounds', 'max_retrieval_calls',
                    'max_module_calls', 'max_work_tokens', 'max_llm_tokens', 'max_output_tokens'):
            if getattr(self, key) < 1:
                raise ValueError(f'{key} must be >= 1')
        if self.timeout_seconds <= 0 or self.max_seconds <= 0:
            raise ValueError('Timeouts must be positive')
        if not 0 <= self.boundary_penalty <= 2:
            raise ValueError('boundary_penalty must be in [0, 2]')

    def to_dict(self):
        return asdict(self)
