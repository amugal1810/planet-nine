from unittest.mock import patch
import pytest
import random
from the_crew_game import TheCrewGame
from game_config import Game, GameplayError

# Test a full end-to-end gameplay flow
def test_end_to_end_thecrew_gameplay():
    random.seed(42)

    # Mock the input calls for new mission number and other inputs
    with patch('builtins.input', side_effect=['1', 'no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(num_mission=1, seed=42)

    assert len(game.hands) == 4
    assert sum(len(hand) for hand in game.hands.values()) == 40
    assert set(game.tasks) == set(game.task_ordering)

    r4_holder = next(i for i, hand in game.hands.items() if 'R4' in hand)
    assert game.turn_order[0] == r4_holder

    radio_card = next(c for c in game.hands[r4_holder] if not c.startswith("R"))
    
    # Corrected the RADIO input to include a valid clue type
    game.play(f"RADIO highest {radio_card}", player_id=r4_holder)
    assert game.radio_used[r4_holder]
    assert game.radio_clues[r4_holder] == (radio_card, 'highest')

    # Test trying to reuse radio clue
    with pytest.raises(GameplayError, match="Radio clue already used."):
        game.play(f"radio highest {radio_card}", player_id=r4_holder)


def test_follow_suit_enforcement():
    random.seed(0)
    
    # Mock the input calls
    with patch('builtins.input', side_effect=['no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(seed=0)

    player = game.turn_order[0]
    lead_card = next(c for c in game.hands[player] if not c.startswith("R"))
    lead_suit = lead_card[0]
    game.play(lead_card, player_id=player)

    next_player = game.turn_order[0]
    hand = game.hands[next_player]
    has_lead = any(c[0] == lead_suit and not c.startswith("R") for c in hand)
    off_suit = next((c for c in hand if c[0] != lead_suit and not c.startswith("R")), None)

    if has_lead and off_suit:
        with pytest.raises(GameplayError):
            game.play(off_suit, player_id=next_player)


def test_trick_winner_advances_turn_order():
    random.seed(1)
    
    # Mock the input calls
    with patch('builtins.input', side_effect=['no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(seed=1)

    trick_cards = []

    for i in range(4):
        player = game.turn_order[0]
        hand = game.hands[player]

        # Only play cards that are not tasks
        non_task_cards = [c for c in hand if c not in game.tasks and not c.startswith("R")]

        if i == 0:
            card = non_task_cards[0]
            lead_suit = card[0]
        else:
            suit_cards = [c for c in non_task_cards if c[0] == lead_suit]
            card = suit_cards[0] if suit_cards else non_task_cards[0]

        game.play(card, player_id=player)
        trick_cards.append((player, card))

    assert len(game.trick) == 0
    assert game.turn == 2
    winner, _ = max(trick_cards, key=lambda x: (x[1][0] == lead_suit, int(x[1][1:])))
    assert game.turn_order[0] == winner


def test_task_fails_if_wrong_order_completed():
    random.seed(100)

    # Mock the input calls for new mission number and other inputs
    with patch('builtins.input', side_effect=['1', 'no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(num_mission=1, seed=100)

    # Shuffling task order for the test
    if len(game.task_ordering) >= 2:
        first, second = game.task_ordering[:2]
        game.task_ordering = [second, first] + game.task_ordering[2:]
        game.assigned_tasks = {t: game.turn_order[i % game.num_players] for i, t in enumerate(game.task_ordering)}
        game.tasks = list(game.task_ordering)
        game.completed_tasks = []

        # Force the wrong task (which is now second in order) to be played first
        wrong_task = first
        wrong_player = game.turn_order[0]
        game.hands[wrong_player].append(wrong_task)

        # Try to play the wrong task first and catch the error
        try:
            game.play(wrong_task, player_id=wrong_player)

            # Complete the trick with other players following suit
            lead_suit = wrong_task[0]
            for _ in range(game.num_players - 1):
                p = game.turn_order[0]
                hand = game.hands[p]
                suit_cards = [c for c in hand if c[0] == lead_suit]
                if suit_cards:
                    card = suit_cards[0]
                else:
                    card = next(c for c in hand if not c.startswith("R"))
                game.play(card, player_id=p)

            # If the game doesn't raise the error, we should manually fail the test
            assert False, "Expected RuntimeError due to task order violation not raised."

        except RuntimeError as e:
            # Verify the error message matches the expected task order violation message
            assert str(e) == "Mission failed due to task order violation.", f"Unexpected error message: {str(e)}"


def test_invalid_number_of_players():
    with pytest.raises(Exception, match="Number of players must be between 2 and 5."):
        TheCrewGame(num_players=1, seed=123)

    with pytest.raises(Exception, match="Number of players must be between 2 and 5."):
        TheCrewGame(num_players=6, seed=123)


def test_invalid_mission_number():
    with pytest.raises(Exception, match="Invalid mission number selected."):
        TheCrewGame(num_mission=100, seed=123)


def test_2_player_game():
    random.seed(0)

    # Mock the input calls for distress signal, card passing direction, and other moves
    with patch('builtins.input', side_effect=['no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(num_players=2, seed=0)

    # Ensure correct card distribution for 2 players
    assert len(game.hands) == 2
    assert sum(len(hand) for hand in game.hands.values()) == 26  # 40 total cards, 14 for JARVIS, 13 each for players
    assert game.jarvis_hands is not None
    assert len(game.jarvis_hands['face_up']) == 7
    assert len(game.jarvis_hands['face_down']) == 7
    assert game.distress_signal_active is False  # Initially no distress signal

    # Test JARVIS turn setup
    player = game.turn_order[0]

    # Play a normal card for the human player (first player)
    play_card = next(c for c in game.hands[player] if not c.startswith("R"))
    game.play(play_card, player_id=player)

    # Verify the card is removed from the player's hand and added to the trick
    assert play_card not in game.hands[player]
    assert game.trick[0] == (player, play_card)

    # Now it's JARVIS's turn, so we need to ensure JARVIS follows suit if possible
    # Get the lead suit from the first card played
    lead_suit = play_card[0]

    # Check if JARVIS has any revealed cards of the lead suit
    jarvis_card = None
    for card in game.jarvis_hands['face_up']:  # Only look at face-up cards (revealed cards)
        if card[0] == lead_suit:
            jarvis_card = card
            break

    # If JARVIS has a card of the lead suit, he must play it
    if jarvis_card:
        print(f"JARVIS follows suit and plays: {jarvis_card}")
        print("lalala")
        game.play(jarvis_card, player_id=2)  # JARVIS is player 2
        print("lalala")
        assert jarvis_card not in game.jarvis_hands['face_up']  # JARVIS should no longer have this card in the revealed cards
        print("lalala")
        assert game.trick[1] == (2, jarvis_card)  # Verify JARVIS's card is in the trick
        print("lalala")
    else:
        # If JARVIS doesn't have a matching suit, he can play any valid card from his revealed cards (not a rocket)
        jarvis_card = next(card for card in game.jarvis_hands['face_up'] if not card.startswith("R"))
        print(f"JARVIS cannot follow suit, so he plays: {jarvis_card}")
        game.play(jarvis_card, player_id=2)  # JARVIS plays any valid card
        assert jarvis_card not in game.jarvis_hands['face_up']  # JARVIS should no longer have this card in the revealed cards
        assert game.trick[1] == (2, jarvis_card)  # Verify JARVIS's card is in the trick


def test_4_player_game():
    random.seed(10)

    # Mock the input calls for distress signal, card passing direction, and other moves
    with patch('builtins.input', side_effect=['no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(num_players=4, seed=10)

    # Assert basic game setup
    assert len(game.hands) == 4
    assert sum(len(hand) for hand in game.hands.values()) == 40
    assert game.turn_order[0] == next(i for i, hand in game.hands.items() if 'R4' in hand)

    # Test that turn order advances correctly (Player 0 -> Player 1 -> Player 2 -> Player 3)
    player = game.turn_order[0]
    normal_card = next(c for c in game.hands[player] if not c.startswith("R") and c not in game.tasks)
    game.play(normal_card, player_id=player)
    assert normal_card not in game.hands[player]
    assert game.trick[0] == (player, normal_card)

    # Assert turn has advanced
    next_player = game.turn_order[0]
    assert next_player != player  # Turn should have advanced to the next player

    # Corrected the RADIO input to include a valid clue type
    radio_card = next(c for c in game.hands[next_player] if not c.startswith("R"))
    game.play(f"RADIO highest {radio_card}", player_id=next_player)
    assert game.radio_used[next_player]
    assert game.radio_clues[next_player] == (radio_card, 'highest')


def test_5_player_game():
    random.seed(11)

    # Mock the input for distress signal, no passing, then a single transfer by player 2→player 0
    with patch('builtins.input', side_effect=['no','yes','no','yes','1']):
        game = TheCrewGame(num_players=5, num_mission=10,seed=11)

    # Basic setup
    assert len(game.hands) == 5
    assert sum(len(hand) for hand in game.hands.values()) == 40
    assert game.turn_order[0] == next(i for i,h in game.hands.items() if 'R4' in h)

    # No distress
    assert game.distress_signal_active is False
    assert game.card_pass_direction is None

    # Test normal play: first trick, then radio usage
    player = game.turn_order[0]
    normal_card = next(c for c in game.hands[player] if not c.startswith("R") and c not in game.tasks)
    game.play(normal_card, player_id=player)
    assert game.trick[0] == (player, normal_card)

    # turn advances
    next_player = game.turn_order[0]
    assert next_player != player

    # Corrected the RADIO input to include a valid clue type
    radio_card = next(c for c in game.hands[next_player] if not c.startswith("R"))
    game.play(f"RADIO highest {radio_card}", player_id=next_player)
    assert game.radio_used[next_player]
    assert game.radio_clues[next_player] == (radio_card, 'highest')

def test_disruption_condition():
    random.seed(42)

    # Mock the input calls for new mission number and other inputs
    with patch('builtins.input', side_effect=['7', 'no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(num_mission=7, seed=42)

    # Ensure that disruption condition is applied
    assert game.disruption is True
    r4_holder = next(i for i, hand in game.hands.items() if 'R4' in hand)

    # Now, test that radio communication is disrupted
    # The player holding R4 should try to play a radio clue
    with pytest.raises(GameplayError, match="Radio communication is disabled due to disruption. You cannot use the radio."):
        game.play("radio highest B1", player_id=r4_holder)

def test_deadzone_condition():
    random.seed(42)

    # Mock the input calls for new mission number and other inputs
    with patch('builtins.input', side_effect=['6', 'no', 'cw', '1', '2', '3', '4']):
        game = TheCrewGame(num_mission=6, seed=42)

    # Ensure that deadzone condition is applied
    assert game.deadzone is True
    r4_holder = next(i for i, hand in game.hands.items() if 'R4' in hand)
    # Test that players can't know if card is highest/lowest/only
    radio_card = next(c for c in game.hands[0] if not c.startswith("R"))
    radio_card = radio_card.lower()
    game.play(f"RADIO highest {radio_card}", player_id=r4_holder)
    assert game.radio_clues[r4_holder] == (radio_card, 'deadzone')  # This should be marked as 'deadzone'

def test_commanders_decision():
    
    # All inputs needed for the entire test in one patch
    all_inputs = [
        '3',  # number of players
        '8',  # mission number
        'no',  # distress signal
        'yes',  # Player 2 wants to take all tasks
        'no',   # Player 3 doesn't want to take all tasks
        'no',   # Commander doesn't want tasks
        '2'     # Commander assigns to Player 2
    ]
    
    with patch('builtins.input', side_effect=all_inputs):
        game = TheCrewGame(num_mission=8, seed=42)
        
        # After game initialization, commanders_decision should be True for mission 8
        assert game.commanders_decision is True
        
        # Check that tasks are assigned to player 2 (index 1)
        for task in game.tasks:
            # Ensure all tasks are assigned to Player 2 (index 1)
            assert game.assigned_tasks[task] == 1  # Player 2 (index 1)


# def test_commanders_distribution():
#     random.seed(42)
#     all_inputs = [
#         '3',  # number of players
#         '9',  # mission number
#         'no',  # distress signal
#         'yes',
#         'no', 'no', '1', 'no', 'yes','no','2','no','no','yes','3','yes', 'no', 'no', '1'
#     ]

#     # Mock the input calls for new mission number and other inputs
#     with patch('builtins.input', side_effect=all_inputs):
#         game = TheCrewGame(num_mission=9, seed=42)

#     # Ensure that commander's distribution is applied
#     assert game.commanders_distribution is True
    

#     # Test that tasks are distributed according to the rules
#     for task, player in game.assigned_tasks.items():
#         assert player in range(game.num_players)  # Ensure assigned task is given to valid player


def test_commanders_distribution():
    import random
    from unittest.mock import patch
    
    # Set seed for consistent results
    random.seed(42)
    
    # From the captured output, we see:
    # - Player 3 has R4 and is the commander
    # - First task to distribute is P8
    
    # We need to provide specific inputs for the validation flow
    all_inputs = [
        '3',             # number of players
        '9',             # mission number
        'no',            # distress signal
        
        # Tasks inputs
        'no',            
        'no',            
        'no', 
        'no',          
        '1',            
        'no',            
        'no',           
        'no', 
        'no',          
        '2',           
        'no',            
        'no',            
        'no', 
        '2',          
        '2',             
        'no',           
        'no',           
        'yes', 
        'no',          
        '1',             
        '3', '1', '2', '2'  # extra inputs for any potential validation retries
    ]
    
    # Run the actual test with our prepared inputs
    with patch('builtins.input', side_effect=all_inputs):
        game = TheCrewGame(num_mission=9, seed=42)
        
        # Ensure commander's distribution flag is set
        assert game.commanders_distribution is True
        
        # Test that tasks are distributed according to the rules
        assert len(game.assigned_tasks) == 4, "Should have 4 tasks assigned"
        
        # Count tasks per player
        tasks_per_player = [0, 0, 0]  # Initialize counter for each player
        for player_idx in game.assigned_tasks.values():
            tasks_per_player[player_idx] += 1
        
        # Check distribution matches our expected pattern (1 task to P1, 2 to P2, 1 to P3)
        assert tasks_per_player[0] == 1, f"Player 1 should have 1 task, but has {tasks_per_player[0]}"
        assert tasks_per_player[1] == 2, f"Player 2 should have 2 tasks, but has {tasks_per_player[1]}"
        assert tasks_per_player[2] == 1, f"Player 3 should have 1 task, but has {tasks_per_player[2]}"
        
        # Final check that all players have at least one task
        assert all(count > 0 for count in tasks_per_player), "Not all players received at least one task"