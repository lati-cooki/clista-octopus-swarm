import threading

class MetabolicBudget:
    """
    An Antigravity Memory Bank / global ledger tracking the total-cap compute pool.
    """
    def __init__(self, initial_capacity: float):
        self._capacity = initial_capacity
        self._lock = threading.Lock()
        
    def consume(self, amount: float) -> bool:
        with self._lock:
            if self._capacity >= amount:
                self._capacity -= amount
                return True
            return False
            
    def get_remaining(self) -> float:
        with self._lock:
            return self._capacity
