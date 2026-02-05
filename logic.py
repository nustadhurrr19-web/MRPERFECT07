import math
from collections import Counter

class TitanLogic:
    """
    TITAN PRO: APEX QUANTUM LOGIC ENGINE (V3 - HEAVY)
    -------------------------------------------------
    Features:
    - Multi-Depth Pattern Recognition (3, 4, 5, 6)
    - Volatility Index (Violet/Zero detection)
    - Momentum/Trend Scoring
    - Auto-Recovery & Money Management Flags
    """

    def __init__(self):
        # Tracking internal state
        self.wins = 0
        self.losses = 0
        self.streak = 0
        self.total_processed = 0
        
        # Configuration for "Sureshot" thresholds
        self.CONFIDENCE_THRESHOLD_LOW = 0.60
        self.CONFIDENCE_THRESHOLD_HIGH = 0.85
        self.CONFIDENCE_THRESHOLD_SURESHOT = 0.90

    def get_size(self, n):
        """Converts raw number to BIG/SMALL size."""
        try:
            return "BIG" if int(n) >= 5 else "SMALL"
        except:
            return "ERR"

    def _calculate_volatility(self, history, window=20):
        """
        Scans the last 'window' rounds to see how dangerous the market is.
        Returns True if the market is 'Violet Heavy' (0 or 5).
        """
        if len(history) < window: return False
        
        # Count how many 0s and 5s exist in the recent window
        violet_count = 0
        recent_slice = history[-window:]
        
        for item in recent_slice:
            if item['n'] == 0 or item['n'] == 5:
                violet_count += 1
        
        # If more than 25% of results are Violet, market is Volatile
        volatility_ratio = violet_count / window
        return volatility_ratio > 0.25

    def _check_symmetry(self, history):
        """
        Checks for mathematical symmetry in the last 2 numbers.
        Rule: Sum = 9 OR Identical Numbers (e.g., 4+5 or 8,8)
        """
        if len(history) < 2: return False
        n1 = int(history[-1]['n'])
        n2 = int(history[-2]['n'])
        
        if (n1 + n2) == 9: return True
        if n1 == n2: return True
        return False

    def _get_pattern_weight(self, history, depth):
        """
        Deep pattern scanner.
        Returns: (Predicted Result, Confidence Score)
        """
        if len(history) < depth + 1: return None, 0.0
        
        # 1. Extract the sequence we are looking for
        target_sequence = [x['s'] for x in history[-depth:]]
        
        # 2. Scan the ENTIRE history for this sequence
        matches = []
        search_limit = len(history) - (depth + 1)
        
        for i in range(search_limit):
            # Grab a chunk of the same length
            test_chunk = [x['s'] for x in history[i : i+depth]]
            
            # If it matches, what came NEXT?
            if test_chunk == target_sequence:
                next_val = history[i+depth]['s']
                matches.append(next_val)
        
        # 3. Calculate Probability
        if not matches: return None, 0.0
        
        counter = Counter(matches)
        top_result = counter.most_common(1)[0][0] # 'BIG' or 'SMALL'
        count = counter[top_result]
        total = len(matches)
        
        confidence = count / total
        return top_result, confidence

    def _resolve_conflicts(self, p3, s3, p4, s4, p5, s5):
        """
        Weighted voting system to resolve conflicting patterns.
        Depth 5 has higher weight than Depth 3.
        """
        # Weights: Depth 5 = 1.5x, Depth 4 = 1.2x, Depth 3 = 1.0x
        score_big = 0
        score_small = 0
        
        # Tally Depth 3
        if p3 == "BIG": score_big += (s3 * 1.0)
        elif p3 == "SMALL": score_small += (s3 * 1.0)
        
        # Tally Depth 4
        if p4 == "BIG": score_big += (s4 * 1.2)
        elif p4 == "SMALL": score_small += (s4 * 1.2)
        
        # Tally Depth 5
        if p5 == "BIG": score_big += (s5 * 1.5)
        elif p5 == "SMALL": score_small += (s5 * 1.5)
        
        # Final Decision
        if score_big > score_small:
            final_pred = "BIG"
            avg_strength = score_big / 3 # Rough average
        else:
            final_pred = "SMALL"
            avg_strength = score_small / 3
            
        return final_pred, avg_strength

    def analyze(self, history):
        """
        MAIN EXECUTABLE FUNCTION
        """
        # 1. Safety Checks
        if len(history) < 15:
            return None, "SYNCING DATA..."
            
        # 2. Volatility Check (The 0/5 Rule)
        # If the LAST result was a 0 or 5, we trigger strict mode.
        last_num = int(history[-1]['n'])
        is_violet_trigger = (last_num == 0 or last_num == 5)
        
        # Also check general market volatility
        is_market_volatile = self._calculate_volatility(history)

        # 3. Run Pattern Scans (Depths 3, 4, 5)
        p3, s3 = self._get_pattern_weight(history, 3)
        p4, s4 = self._get_pattern_weight(history, 4)
        p5, s5 = self._get_pattern_weight(history, 5)
        
        # 4. Resolve the Best Prediction
        best_pred, strength = self._resolve_conflicts(p3, s3, p4, s4, p5, s5)
        
        if not best_pred:
            # Fallback if no patterns found
            best_pred = history[-1]['s']
            strength = 0.5

        # 5. Check Secondary Filters
        is_symmetric = self._check_symmetry(history)
        
        # ---------------------------------------------------
        # DECISION TREE (FINAL BET TYPE)
        # ---------------------------------------------------
        
        # A. VIOLET TRIGGER HANDLING (Highest Priority)
        # If we just hit a 0 or 5, we DO NOT BET unless it's a perfect pattern.
        if is_violet_trigger:
            if strength > 0.92 and is_symmetric:
                return best_pred, "SURESHOT (VIOLET SAFE)"
            else:
                return None, f"SKIP (VIOLET {last_num})"

        # B. RECOVERY HANDLING
        # If user has lost 2 in a row, we force recovery mode logic.
        if self.streak >= 2:
            # We need at least decent strength to attempt recovery
            if strength > 0.60:
                return best_pred, "RECOVERY"
            else:
                return None, "SKIP (BAD RECOVERY)"

        # C. SURESHOT HANDLING
        # Requires High Strength + Symmetry
        if strength > self.CONFIDENCE_THRESHOLD_SURESHOT and is_symmetric:
            return best_pred, "SURESHOT"

        # D. HIGH BET HANDLING
        # Requires Good Strength, Symmetry optional
        if strength > self.CONFIDENCE_THRESHOLD_HIGH:
            return best_pred, "HIGH BET"
            
        # E. LOW BET / WAITING
        # If market is volatile, skip low bets entirely
        if is_market_volatile:
            return None, "WAITING (VOLATILE)"
            
        if strength > self.CONFIDENCE_THRESHOLD_LOW:
            return best_pred, "LOW BET"

        return None, "WAITING..."

    def update_stats(self, won):
        """Updates internal streak counter"""
        if won:
            self.wins += 1
            self.streak = 0
        else:
            self.losses += 1
            self.streak += 1