from services.coding_engine.engine import CodingEngine

_default_coding_engine = None


def get_coding_engine() -> CodingEngine:
    global _default_coding_engine
    if _default_coding_engine is None:
        _default_coding_engine = CodingEngine()
    return _default_coding_engine
