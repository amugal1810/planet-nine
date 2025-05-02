class GameplayError(Exception):
    '''
    Throw this error when the model has made a mistake (e.g. played an invalid move). The model will be prompted to make another move. If the game should end, throw a RuntimeError instead.
    '''
    pass

class Game():
    def valid_players(self) -> tuple[int, ...]: ...

    def whose_turn(self) -> int: ...

    def is_over(self) -> bool: ...

    def scores(self) -> dict[int, float]: ...

    def state(self, player_id: int | None = None) -> str: ...
    '''
    Returns a string representation of the game state.
    This is the only context the model receives about the game, so make sure to include all necessary details, including a brief summary of the rules and objective (on first turn), instructions for the current turn, current board state, scores, any face-up cards, etc. For games with constrained action spaces, you may consider printing an exhaustive list of available actions to the current player at the end of the state.
    If player_id is None, returns a global state.
    If player_id is not None, returns a state for the given player.
    '''

    def play(self, move: str, player_id: int = 0) -> None: ...
    '''
    Update the game state according to the move. The move string expected here should be consistent with instructions provided to the model in the state function. If the move is invalid, throw a GameplayError. The error should describe why the move is invalid.
    '''
