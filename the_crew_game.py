import random
import time

from game_config import Game, GameplayError
import mock_missions 


class TheCrewGame(Game):
    COLORS = ['P', 'Y', 'G', 'B']
    ROCKETS = ['R1', 'R2', 'R3', 'R4']
    ARROW_TOKENS = ['<', '<<', '<<<', '<<<<']
    OMEGA_TOKEN = 'Ω'  # New omega token

    def __init__(self, num_players=4, num_mission=8, seed=None):
      # Ask the user to select a mission number
        if num_mission not in mock_missions.missions:
            raise Exception("Invalid mission number selected.")
        
        # Get the mission details from the mock_missions file
        mission = mock_missions.missions[num_mission]
        

        # Initialize attempt counter and distress token counter
        self.attempts = 1  # Tracks the number of attempts to complete the mission
        self.distress_token_usage = 0  # Tracks how many times the distress token was used

        # Get the predefined task types (simple, numbered, arrow, omega)
        self.task_types = mission["tasks"]  # e.g., ["simple", "numbered", "arrow"]
        self.task_tokens = mission["tokens"]  # e.g., ["simple task", "numbered token", "<"]
        self.condition = mission.get("condition", [])
        self.tasks = []
        # Generate the actual task cards (e.g., "P7", "B3") based on task types
        self._generate_task_cards()

        if not (2 <= num_players <= 5):
            raise Exception("Number of players must be between 2 and 5.")
        
        random.seed(seed if seed is not None else time.time())

        self.failed = False
        self.num_players = num_players
        
        result = self._deal_cards()
        self.hands = result[0]
        self.jarvis_hands = result[1]
        if self.jarvis_hands:
            self.hands[2] = self.jarvis_hands['face_up']
        
        self._print_initial_hands()
        self.played_cards = []
        self.trick = []
        self.completed_tasks = []  # Now tracking actual cards
        self.turn = 1
        self.radio_used = [False] * self.num_players
        self.radio_clues = {}

        self.distress_signal_active = False
        self.card_pass_direction = None

        self.turn_order = self._get_turn_order_starting_with_r4_holder()
        
        # Initialize task_ordering with the generated task cards
        self.task_ordering = self.tasks.copy()  # Now, task_ordering holds actual cards (e.g., "P7", "B3")
        self.assigned_tasks = {
            task: self.turn_order[i % self.num_players] for i, task in enumerate(self.tasks)
        }
        
        self.activate_distress_signal()
        if self.num_players == 5:
            self._prompt_task_transfer()
        if self.num_players == 2:
            self._jarvis_turn_setup()
        
        self.previous_trick = []

        # Handle the deadzone condition
        if "deadzone" in self.condition:
            print("\nThe is a special mission in which you are not allowed the information about the radio card being highest, lowest, or only will be hidden. This is DEADZONE mission!")
            self.deadzone = True
        else:
            self.deadzone = False

        if "disruption" in self.condition:
            print("\nThe is a special mission in which all radio communication is DISRUPTED")
            self.disruption = True
        else:
            self.disruption = False

        if "commanders_decision" in self.condition:
            self.commanders_decision = True
        else:
            self.commanders_decision = False

        if "commanders_distribution" in self.condition:
            self.commanders_distribution = True
        else:
            self.commanders_distribution = False

        if self.commanders_decision:
            self._commanders_decision()

        if self.commanders_distribution:
            self._commanders_distribution()


    def _apply_special_conditions(self):
        """Reapply any special conditions like commander's decision, etc., for the new attempt."""
        if "commanders_decision" in self.condition:
            self._commander_decision()  # Apply commander's decision condition
        
        if "commanders_distribution" in self.condition:
            self._commander_distribution()  # Apply commander's distribution condition

    def _commanders_decision(self):
        """
        This method allows the commander to decide who will take on all the tasks in the mission.
        The commander will ask each player if they want to take on all tasks.
        """
        print("\nThe is a special mission in which commander will decide one player who will get all the tasks.")
        print("\nThe commander will now ask the players if they want to take on all tasks.")

        # Get the commander (the player with R4)
        commander = None
        for player_id, hand in self.hands.items():
            if 'R4' in hand:
                commander = player_id
                break
        
        # Commander asks players if they want to take on all tasks
        for player_id in self.turn_order:
            if player_id == commander:
                continue  # Skip the commander since they are asking
            response = input(f"state just for following question: {self.hands[player_id]} Question: Player {player_id + 1}, do you want to take on all tasks for this mission? (yes/no): ").strip().lower()
            while response not in ["yes", "no"]:
                response = input("Invalid input. Please respond with 'yes' or 'no': ").strip().lower()
            if response == 'yes':
                self.assigned_tasks = {task: player_id for task in self.tasks}
                print(f"Player {player_id + 1} will take on all tasks!")
                return
                
        # If no one takes on all tasks, the commander decides who will take on all tasks
        print(f"\nCommander (Player {commander + 1}) decides who will take on all tasks.")

        # If the commander decides to assign all tasks to another player, ask the commander to choose a player
        target_player = int(input(f"Commander, which player do you want to assign all tasks to other than yourself which is {commander + 1}? (1-{self.num_players}): ").strip()) - 1
        while target_player < 0 or target_player >= self.num_players or target_player == commander:
            target_player = int(input(f"Invalid input. Choose a valid player (1-{self.num_players}): ").strip()) - 1
        self.assigned_tasks = {task: target_player for task in self.tasks}
        print(f"Player {target_player + 1} will take on all tasks!")
    

    def _commanders_distribution(self):
        """
        This method allows the commander to distribute tasks equally among the players.
        The commander asks each player if they want a task, and then the commander assigns tasks.
        Tasks are distributed equally, with the possibility of one player getting one more task than others.
        """
        print("\nThe is a special mission in which commander will distribute the tasks.")
        print("\nThe commander will now distribute the tasks.")

        # Get the commander (the player with R4)
        commander = None
        for player_id, hand in self.hands.items():
            if 'R4' in hand:
                commander = player_id
                break

        # Calculate the base number of tasks each player should get
        tasks_per_player = len(self.tasks) // self.num_players
        extra_tasks = len(self.tasks) % self.num_players  # The number of extra tasks that will be assigned

        # Keep track of how many tasks each player has
        player_task_count = {player_id: 0 for player_id in self.turn_order}

        # Assign tasks one by one, ensuring equal distribution
        for task in self.tasks:
            print(f"\nCommander (Player {commander + 1}), it's time to distribute task: {task}")

            # Ask each player if they want the task
            task_assigned = False
            responses = {}

            for player_id in self.turn_order:
                if player_task_count[player_id] < tasks_per_player or (player_task_count[player_id] == tasks_per_player and extra_tasks > 0):
                    response = input(f"Player {player_id + 1}, do you want task {task}? (yes/no): ").strip().lower()
                    while response not in ["yes", "no"]:
                        response = input("Invalid input. Please respond with 'yes' or 'no': ").strip().lower()
                    responses[player_id] = response
                else:
                    print(f"Player {player_id + 1} cannot take more tasks.")

            # Now the commander decides who to give the task to
            eligible_players = [player_id for player_id in self.turn_order if responses.get(player_id) == "yes" and player_task_count[player_id] < tasks_per_player + (1 if extra_tasks > 0 else 0)]
            
            if eligible_players:
                # Commander decides who to assign the task to
                print(f"Eligible players for task {task}: {', '.join([str(player_id + 1) for player_id in eligible_players])}")
                target_player = int(input(f"Commander, who do you want to give task {task} to? (Choose from: {', '.join([str(player_id + 1) for player_id in eligible_players])}): ").strip()) - 1
                
                # Check if the target player is eligible
                while target_player not in eligible_players:
                    target_player = int(input(f"Invalid input. Choose a valid player from: {', '.join([str(player_id + 1) for player_id in eligible_players])}: ").strip()) - 1
                
                self.assigned_tasks[task] = target_player
                player_task_count[target_player] += 1
                if player_task_count[target_player] > tasks_per_player:
                    extra_tasks -= 1
                task_assigned = True
                print(f"Task {task} assigned to Player {target_player + 1}.")
            else:
                # If no player said yes, the commander can assign the task to themselves or another player
                print(f"No player has volunteered for task {task}. Commander (Player {commander + 1}), do you want to take it?")
                response = input(f"Commander, do you want to take on task {task}? (yes/no): ").strip().lower()
                while response not in ["yes", "no"]:
                    response = input("Invalid input. Please respond with 'yes' or 'no': ").strip().lower()

                if response == "yes":
                    self.assigned_tasks[task] = commander
                    player_task_count[commander] += 1
                    print(f"Commander (Player {commander + 1}) will take on task {task}!")
                else:
                    # If the commander decides not to take the task, assign it to another player
                    target_player = int(input(f"Commander, which player do you want to assign task {task} to? (1-{self.num_players}): ").strip()) - 1
                    while target_player < 0 or target_player >= self.num_players or target_player == commander:
                        target_player = int(input(f"Invalid input. Choose a valid player (1-{self.num_players}): ").strip()) - 1
                    self.assigned_tasks[task] = target_player
                    player_task_count[target_player] += 1
                    print(f"Task {task} assigned to Player {target_player + 1}.")

        print("\nTask distribution completed.")


    def _generate_task_cards(self):
        """This function generates the task cards based on the predefined task types (simple, numbered, etc.)."""
        all_cards = [f"{color}{num}" for color in self.COLORS for num in range(1, 10)] + self.ROCKETS
        
        selected_cards = []  # List to store the generated task cards

        # For each task type, pick random cards from the deck
        for task_type in self.task_types:
            if task_type == "simple":
                card = random.choice(all_cards)
                selected_cards.append(card)
                all_cards.remove(card)  # Remove the card from the deck once it’s picked
            elif task_type == "numbered":
                card = random.choice(all_cards)
                selected_cards.append(card)
                all_cards.remove(card)
            elif task_type == "arrow":
                card = random.choice(all_cards)
                selected_cards.append(card)
                all_cards.remove(card)
            elif task_type == "omega":
                card = random.choice(all_cards)
                selected_cards.append(card)
                all_cards.remove(card)
        
        # Assign the selected cards to the tasks
        self.tasks = selected_cards

        self.task_token_map = {task: token for task, token in zip(self.tasks, self.task_tokens)}


    def _prompt_task_transfer(self):
        """Prompt players to transfer their task card to another player."""
        transfer_choice = input("Do any players want to transfer their task card to another player? (yes/no): ").strip().lower()
        
        if transfer_choice != "yes":
            print("No task card transfer will be made.")
            return

        # Keep asking players until one decides to transfer their task
        for player_id in range(self.num_players):
            print(f"\nPlayer {player_id + 1}'s assigned task: {self.task_ordering[player_id]}")
            transfer_task = input(f"Player {player_id + 1}, do you want to transfer your task? (yes/no): ").strip().lower()
            
            if transfer_task == "yes":
                # Ask who they want to give the task to
                target_player = int(input(f"Player {player_id + 1}, which player do you want to transfer your task to? (1-{self.num_players}): ").strip()) - 1
                while target_player == player_id or target_player < 0 or target_player >= self.num_players:
                    target_player = int(input(f"Invalid input. Choose a valid target player (1-{self.num_players}): ").strip()) - 1

                # Perform the transfer
                task_to_transfer = self.task_ordering[player_id]
                print(f"Player {player_id + 1} is transferring task {task_to_transfer} to Player {target_player + 1}.")
                self.assigned_tasks[task_to_transfer] = target_player
                
                # After transferring, print the updated task assignments and stop asking
                self._print_updated_task_assignments()
                return  # Stop asking other players once a transfer has been made

        # If no player transfers, print message and proceed
        print("No task transfer was made.")

    def _print_updated_task_assignments(self):
        """Print the updated task assignments after a transfer."""
        print("\nUpdated Task Assignments:")
        for task, player in self.assigned_tasks.items():
            print(f"{task} → Player {player + 1}")

    def _deal_cards(self):
        deck = [f"{color}{num}" for color in self.COLORS for num in range(1, 10)] + self.ROCKETS
        random.shuffle(deck)
        
        if self.num_players == 2:
            # Remove the 4 rocket cards for JARVIS (JARVIS will not get rocket cards)
            jarvis_deck = [card for card in deck if card != 'R4']
            
            # Deal 14 cards to JARVIS (7 face-up and 7 face-down)
            jarvis_hand = {
                'face_up': jarvis_deck[:7],  # First 7 cards (face-up)
                'face_down': jarvis_deck[7:14]  # Next 7 cards (face-down)
            }
            
            # The remaining cards (including rocket cards) are dealt to the human players
            remaining_deck = ['R4'] + jarvis_deck[14:]

            hands = {i: [] for i in range(2)}  # Two human players
            for i, card in enumerate(remaining_deck):
                hands[i % 2].append(card)

            return hands, jarvis_hand  # Return human players' hands and JARVIS's hand
        else:
            # Regular card dealing for 3, 4, or 5 players
            hands = {i: [] for i in range(self.num_players)}
            for i, card in enumerate(deck):
                hands[i % self.num_players].append(card)
            return hands, None  # No JARVIS hand in these cases

    def _jarvis_turn_setup(self):
        """Setup JARVIS's turn, task assignment, and reveal cards logic for 2-player game."""
        # Automatically add JARVIS as the third player and give them tasks
        print("\nJARVIS is now added as the third player.")
        
        # When the game starts, JARVIS can only use 7 revealed cards
        self.jarvis_revealed_cards = self.jarvis_hands['face_up']
        self.jarvis_hidden_cards = self.jarvis_hands['face_down']
        self.jarvis_dictionary = {self.jarvis_hands['face_up'][i]: self.jarvis_hands['face_down'][i] for i in range(7)}
        # Create a method for JARVIS to play cards
        self.jarvis_play = lambda move: self._handle_jarvis_play(move)

        # Determine the commander (the one with R4)
        commander = None
        for player_id, hand in self.hands.items():
            if 'R4' in hand:
                commander = player_id
                break
        print(f"\n🚀 Player {commander + 1} holds R4 and is the commander.")
        self.commander = commander


    def _print_initial_hands(self):
        print("\n🃏 Initial Hands:")
        for player, hand in self.hands.items():
            print(f"Player {player + 1}: {sorted(hand)}")

        if self.num_players == 2 and self.jarvis_hands is not None:
            print("\nJARVIS' Cards (7 face-up and 7 face-down):")
            print(f"Face-up: {sorted(self.jarvis_hands['face_up'])}")
            print(f"Face-down: {'[Hidden]' * len(self.jarvis_hands['face_down'])}")




    def _print_updated_hands(self):
        print("\n🃏 Updated Hands:")
        for player, hand in self.hands.items():
            print(f"Player {player + 1}: {sorted(hand)}")
        print()


    def _get_turn_order_starting_with_r4_holder(self):
        if self.num_players == 2:
            # In a 2-player game with JARVIS, the commander is the player with R4
            for player_id, hand in self.hands.items():
                if 'R4' in hand:
                    print(f"\n🚀 Player {player_id + 1} holds R4 and will start the game.\n")
                    return [player_id, 2, (player_id + 1) % 2]  # Human player, JARVIS, and the other human
        else:
            # Regular turn order for 3-5 players
            for player_id, hand in self.hands.items():
                if 'R4' in hand:
                    print(f"\n🚀 Player {player_id + 1} holds R4 and will start the game.\n")
                    return [(player_id + i) % self.num_players for i in range(self.num_players)]

        return list(range(self.num_players))
    

    def activate_distress_signal(self):
        """Method to handle the distress signal activation logic."""
        # Ask if players want to use the distress signal
        distress_signal_choice = "no"
        if self.num_players != 2:
            distress_signal_choice = input("Do you want to send a distress signal? (yes/no): ").strip().lower()
        if distress_signal_choice != "yes":
            print("No distress signal sent.")
            return

        self.distress_signal_active = True
        print("Distress signal sent! Now choose the direction to pass the cards.")
        
        # Ask for direction: clockwise or anticlockwise
        self.card_pass_direction = input("Do you want to pass cards clockwise or anticlockwise? (cw/ccw): ").strip().lower()
        if self.card_pass_direction not in ['cw', 'ccw']:
            print("Invalid direction chosen. Defaulting to clockwise.")
            self.card_pass_direction = 'cw'
        
        self.distress_signal_active = True
        self.distress_token_usage += 1  # Increment distress token usage
        print(f"Distress signal sent! Attempts increased due to distress token usage.")

        self._pass_cards()
    

    def _pass_cards(self):
        """Handles the logic for passing cards."""
        for i in range(self.num_players):
            print(f"Player {i+1}, your hand: {sorted(self.hands[i])}")
            pass_card = input(f"Player {i+1}, choose a card to pass (cannot be a rocket card): ").strip().upper()
            
            while pass_card not in self.hands[i] or pass_card in self.ROCKETS:
                print(f"Invalid card choice. Please select a valid card that is not a rocket.")
                pass_card = input(f"Player {i+1}, choose a card to pass (cannot be a rocket card): ").strip().upper()

            # Remove the card from the current player's hand
            self.hands[i].remove(pass_card)
            
            # Determine the next player based on direction
            if self.card_pass_direction == 'cw':
                next_player = (i + 1) % self.num_players
            else:
                next_player = (i - 1) % self.num_players

            # Add the card to the next player's hand
            self.hands[next_player].append(pass_card)
            print(f"Player {i+1} passed {pass_card} to Player {next_player+1}.")
            
        print("Card passing complete. Game can now begin.")
        self._print_updated_hands()


    @property
    def valid_players(self):
        return tuple(range(self.num_players))

    def whose_turn(self):
        return self.turn_order[0]

    def is_over(self):
        if self.failed:
            print(f"Mission failed! Restarting mission... (Attempt #{self.attempts + 1})")
            # Restart the mission, increment attempts, and reset necessary state
            self.failed = False
            self.completed_tasks = []  # Reset completed tasks
            self.tasks = self.task_ordering.copy()  # Reset tasks
            self.activate_distress_signal()  # Reactivate any conditions (e.g., distress signal)
            self.attempts += 1  # Increment attempt count due to mission failure
             # Reshuffle and redistribute cards for a new attempt
            result = self._deal_cards()
            self.hands = result[0]
            self.jarvis_hands = result[1]
            
            self._print_initial_hands()
            self.played_cards = []
            self.trick = []
            self.completed_tasks = []  # Now tracking actual cards
            # Reapply special conditions like commander’s decision or distribution
            self._apply_special_conditions()
            return False  # Mission is not over yet, game continues
        
        # Check if any player ran out of cards
        if not any(self.hands.values()) and set(self.completed_tasks) != set(self.task_ordering):
            print("❌ A player ran out of cards before completing all tasks. Mission failed!")
            self.completed_tasks = []  # Reset completed tasks
            self.tasks = self.task_ordering.copy()  # Reset tasks
            self.activate_distress_signal()  # Reactivate any conditions (e.g., distress signal)
            self.attempts += 1  # Increment attempt count due to mission failure
             # Reshuffle and redistribute cards for a new attempt
            result = self._deal_cards()
            self.hands = result[0]
            self.jarvis_hands = result[1]
            
            self._print_initial_hands()
            self.played_cards = []
            self.trick = []
            self.completed_tasks = []  # Now tracking actual cards
            # Reapply special conditions like commander’s decision or distribution
            self._apply_special_conditions()
            return False  # Game continues, mission is failed, it will restart

        # Mission is completed if all tasks are completed
        if set(self.completed_tasks) == set(self.task_ordering):
            return True
        
        if self.attempts > 10:
            raise GameplayError('Mission failed completely. Reached the attempt limit of 10')
            return True

        return False  # Game continues if not yet completed

            


    def scores(self):
        success = float(set(self.completed_tasks) == set(self.task_ordering))
        return {i: success for i in range(self.num_players)}

    def _get_card_position_info(self, player_id: int, card: str) -> str:
        """Determine if the card is the highest, lowest, or only card of its color in the player's hand."""
        color = card[0]
        color_cards = [c for c in self.hands[player_id] if c[0] == color]
        
        if len(color_cards) == 1:
            return "only"
            
        # For rockets, compare their numbers (R1, R2, R3, R4)
        if color == 'R':
            card_num = int(card[1:])
            rocket_nums = [int(c[1:]) for c in color_cards]
            if card_num == max(rocket_nums):
                return "highest"
            elif card_num == min(rocket_nums):
                return "lowest"
            else:
                return "middle"
        # For regular cards
        else:
            card_num = int(card[1:])
            color_nums = [int(c[1:]) for c in color_cards]
            if card_num == max(color_nums):
                return "highest"
            elif card_num == min(color_nums):
                return "lowest"
            else:
                return "middle"


    def _check_radio_card(self, player_id: int, card: str) -> str:
        """
        Check if the card is the highest, lowest, or only card of its color in the player's hand.
        """
        color = card[0]
        color_cards = [c for c in self.hands[player_id] if c[0] == color]

        # If the card is the only card of its color
        if len(color_cards) == 1:
            return "only"

        # For rockets, compare their numbers (R1, R2, R3, R4)
        if color == 'R':
            card_num = int(card[1:])
            rocket_nums = [int(c[1:]) for c in color_cards]
            if card_num == max(rocket_nums):
                return "highest"
            elif card_num == min(rocket_nums):
                return "lowest"
            else:
                return "middle"

        # For regular cards, check highest and lowest
        else:
            card_num = int(card[1:])
            color_nums = [int(c[1:]) for c in color_cards]
            if card_num == max(color_nums):
                return "highest"
            elif card_num == min(color_nums):
                return "lowest"
            else:
                return "middle"


    def _handle_jarvis_play(self, move: str) -> None:
        """Handle JARVIS's card play."""
        # JARVIS can only play cards from its revealed cards
        move = move.upper()
        
        if move not in self.jarvis_revealed_cards:
            raise GameplayError(f"Card {move} not in JARVIS's revealed cards.")
            
        # Follow-suit enforcement
        if self.trick:
            lead_suit = self.trick[0][1][0]
            has_lead_suit = any(card[0] == lead_suit for card in self.jarvis_revealed_cards)
            if has_lead_suit and move[0] != lead_suit:
                raise GameplayError(f"JARVIS must follow suit with {lead_suit} if possible.")
        
        # Remove the card from JARVIS's revealed cards
        self.jarvis_revealed_cards.remove(move)
        self.hands[2] = self.jarvis_revealed_cards
        self.trick.append((2, move))  # JARVIS is player 2
        self.turn_order = self.turn_order[1:]
        revealed_card = self.jarvis_dictionary[move]
        self.jarvis_dictionary.pop(move)
        # If JARVIS used its last revealed card, reveal a new card from face-down
        if revealed_card != '':
            self.jarvis_revealed_cards.append(revealed_card)
            self.jarvis_dictionary[revealed_card] = ''
            self.hands[2] = self.jarvis_revealed_cards
            print(f"JARVIS reveals a new card: {revealed_card}")
            
        # Process the trick if it's complete
        if len(self.trick) == self.num_players + 1:  # +1 for JARVIS
            self._process_trick()
            
    def play(self, move: str, player_id: int = 0) -> None:
        
        if self.num_players == 2 and player_id == 2:
            self._handle_jarvis_play(move)
            return

        if player_id != self.turn_order[0]:
            raise GameplayError(f"Not player {player_id}'s turn.")

        move = move.lower()
        if self.disruption:
            if move.startswith("radio"):
                raise GameplayError("Radio communication is disabled due to disruption. You cannot use the radio.")
        if move.startswith("radio "):
            if self.radio_used[player_id]:
                raise GameplayError("Radio clue already used.")
            
            # Split input into keyword and card (Expected format: 'radio <clue_type> <card>')
            move_parts = move.split()
            
            # Check if the input format is correct
            if len(move_parts) != 3 or move_parts[0].lower() != "radio":
                raise GameplayError("Invalid input format. Please use 'radio <clue_type> <card>'.")

            clue_type_input, clue_card = move_parts[1], move_parts[2]
            # Validate the clue type input (it should be "highest", "lowest", or "only")
            if self.deadzone:
                print(f"📡 Player {player_id + 1} used their radio to reveal they have {clue_card}.")
                self.radio_clues[player_id] = (clue_card, "deadzone")
            else:
                # Validate the clue type input (it should be "highest", "lowest", or "only")
                if clue_type_input not in ['highest', 'lowest', 'only']:
                    raise GameplayError("Invalid clue type. Please enter 'highest', 'lowest', or 'only'.")
                # Ensure case-insensitive card check
                clue_card = clue_card.upper()  # Convert input card to uppercase
                if clue_card not in [card.upper() for card in self.hands[player_id]]:
                    raise GameplayError(f"Card {clue_card} not in hand.")
                # Check if the radio card is valid
                clue_type = self._check_radio_card(player_id, clue_card)
                if clue_type == "middle":
                    raise GameplayError(f"Card {clue_card} cannot be communicated as it is neither highest, lowest, nor the only card of that color.")
                # Store the clue with the chosen type
                self.radio_clues[player_id] = (clue_card, clue_type_input)
                self.radio_used[player_id] = True
                print(f"📡 Player {player_id + 1} used their radio to reveal they have {clue_card} ({clue_type_input} card)!")
            return
        move = move.upper()
        # Follow-suit enforcement, including rockets
        if self.trick:
            lead_suit = self.trick[0][1][0]  # even if it's 'R'
            player_hand = self.hands[player_id]
            has_lead_suit = any(card[0] == lead_suit for card in player_hand)
            if has_lead_suit and move[0] != lead_suit:
                raise GameplayError(f"You must follow suit with {lead_suit} if possible.")
        
        self.hands[player_id].remove(move)
        self.trick.append((player_id, move))
        self.turn_order = self.turn_order[1:]

        # Process the trick using the shared method if the right number of cards are played
        expected_trick_size = self.num_players
        if self.num_players == 2:  # For 2-player mode with JARVIS
            expected_trick_size = 3  # 2 human players + JARVIS

        if len(self.trick) == expected_trick_size:
            self._process_trick()

    def _process_trick(self):
        """Process the current trick to determine winner and check for task completion."""
        def card_strength(card, lead_suit):
            if card.startswith("R"):
                return (2, int(card[1:]))  # Rockets always win
            elif card[0] == lead_suit:
                return (1, int(card[1:]))  # Followed suit
            else:
                return (0, 0)  # Off-suit

        # Determine the lead suit and the winner of the trick
        lead_card = self.trick[0][1]
        lead_suit = lead_card[0]
        winner, winning_card = max(self.trick, key=lambda x: card_strength(x[1], lead_suit))

        print(f"🏆 Player {winner + 1} wins the trick with {winning_card}!")
        self.previous_trick = self.trick.copy()

        # Adjust turn order based on game mode
        if self.num_players == 2:  # 2-player mode with JARVIS
            self.turn_order = [(winner + i) % 3 for i in range(3)]  # 3 players including JARVIS
        else:
            self.turn_order = [(winner + i) % self.num_players for i in range(self.num_players)]

        for player, card in self.trick:
            if card in self.tasks:
                # Ensure no numbered tasks are skipped
                remaining_numbered_tasks = [t for t in self.tasks if t in self.task_token_map and self.task_token_map[t].startswith("numbered token")]

                # For simple tasks, ensure no numbered tasks are pending
                if self.task_token_map[card] == "simple task" and remaining_numbered_tasks:
                    print(f"❌ Cannot complete simple task {card} while numbered tasks remain. Mission failed!")
                    self.failed = True
                    return  # Return to prevent further trick processing

                # For arrow tasks, ensure no numbered tasks are pending
                if self.task_token_map[card] in self.ARROW_TOKENS and remaining_numbered_tasks:
                    print(f"❌ Cannot complete arrow task {card} while numbered tasks remain. Mission failed!")
                    self.failed = True
                    return  # Return to prevent further trick processing

                # For omega task, ensure it is completed last
                if self.task_token_map[card] == self.OMEGA_TOKEN:
                    if len(self.completed_tasks) != len(self.task_ordering) - 1:
                        print(f"❌ Omega task {card} must be completed last. Mission failed!")
                        self.failed = True
                        return  # Return to prevent further trick processing

                # For simple tasks, don't need order checks beyond numbered tasks
                if self.task_token_map[card] == "simple task":
                    print(f"✅ Simple task {card} completed by Player {player + 1}!")
                    self.completed_tasks.append(card)
                    self.tasks.remove(card)
                    continue

                # For other tasks, check if they're completed in the correct order
                expected_card = self.task_ordering[len(self.completed_tasks)]
                expected_player = self.assigned_tasks[expected_card]

                if card != expected_card:
                    print(f"❌ Task {card} was completed out of order. Mission failed!")
                    self.failed = True
                    return  # Return to prevent further trick processing

                if winner != expected_player:
                    print(f"❌ Task {card} was won by Player {winner + 1}, but was assigned to Player {expected_player + 1}. Mission failed!")
                    self.failed = True
                    return  # Return to prevent further trick processing

                print(f"✅ Task {card} completed by Player {player + 1} in correct order and by assigned player!")
                self.completed_tasks.append(card)
                self.tasks.remove(card)

        self.trick = []  # Reset the trick
        self.turn += 1  # Move to the next turn

        # Check if mission is completed or failed and handle accordingly
        if self.is_over():  # If the mission is over, print the score and restart if necessary
            print(f"Mission completed in {self.attempts} attempts.")
            print(f"Final Score: {self.attempts + self.distress_token_usage} attempts taken")
            return  # End the game once the mission is completed

    def state(self, player_id: int | None = None) -> str:  
        state_str = f"\n=== The Crew: Quest for Planet Nine ===\n"
        state_str += f"Turn: {self.turn} (Player {self.turn_order[0] + 1}'s move)\n"
        
        # commander = None
        # for player_id, hand in self.hands.items():
        #     if 'R4' in hand:
        #         commander = player_id
        #         break
        # if self.num_players == '2':
        #     if player_id == 2:
        #         state_str += f"\n Commander's hand (read only, can't play): {self.hands[commander]} \n"
        #     else:
        #         state_str += f"\n Jarvis' hand (read only, can't play): {self.hands[2]} \n"
                
        state_str += "\n🧩 Task Breakdown:\n"
        for task in self.task_ordering:
            label = self.task_token_map[task]
            state_str += f"{task} → ({label})\n"

        state_str += "\n🎯 Task Assignments:\n"
        for task in self.task_ordering:
            player = self.assigned_tasks[task]
            state_str += f"{task} → Player {player + 1}\n"

        state_str += f"\nTasks remaining: {self.tasks}\n"
        state_str += f"Completed tasks: {self.completed_tasks}\n"

        # Display the previous trick (completed round)
        if self.previous_trick:
            state_str += "\n🔄 Previous Trick (Completed Round):\n"
            for player, card in self.previous_trick:
                state_str += f"Player {player + 1} played {card}\n"
        else:
            state_str += "\n🔄 No previous trick played yet.\n"

        # Show the radio clues with the correct format (radio <clue_type> <card>)
        state_str += "\n📡 Radio Clues:\n"
        for pid, (card, clue_type) in self.radio_clues.items():
            state_str += f"Player {pid + 1}: radio {clue_type} {card}\n"

        # Show the lead suit for the current trick (the first card's suit)
        if self.trick:
            lead_card = self.trick[0][1]
            lead_suit = lead_card[0]  # The suit of the first card in the current trick
            state_str += f"\n🃏 Lead suit for the current trick: {lead_suit}\n"
        
        # Show current trick information
        state_str += "\n🔥 Current Trick:\n"
        if self.trick:
            for player, card in self.trick:
                state_str += f"Player {player + 1} played {card}\n"
        else:
            state_str += "No cards played in the current trick yet.\n"

        if player_id is not None:
            # Handle JARVIS (player_id = 2) case separately
            if player_id == 2 and self.num_players == 2: 
                state_str += f"\nJARVIS' hand (face-up): {sorted(self.jarvis_revealed_cards)}\n"
            else:
                state_str += f"\nYour hand: {sorted(self.hands[player_id])}\n"
                if not self.radio_used[player_id]:
                    state_str += "You can use your radio to give a clue by typing: radio <highest/lowest/only> <card>\n"

        state_str += f"\nCurrent Trick: {self.trick}\n"
        return state_str












# mock_missions.py

missions = {
    1:{
        "tasks": ["simple"], 
        "tokens": ["simple"]
    },
    2: {
        "tasks": ["numbered", "numbered", "simple", "simple"],  
        "tokens": ["numbered token 1", "numbered token 2", "simple task", "simple task"]
    },
    3: {
        "tasks": ["arrow", "arrow", "simple", "simple", "simple"],  
        "tokens": ["<", "<<", "simple task", "simple task", "simple task"]
    },
    4: {
        "tasks": ["simple", "simple", "simple", "omega"],  
        "tokens": ["simple task", "simple task", "simple task", "Ω"]
    },
    5: {
        "tasks": ["arrow", "arrow", "simple", "omega"],  
        "tokens": ["<", "<<", "simple task", "Ω"]
    },
    6: {
        "tasks": ["simple"],  
        "tokens": ["simple task"],
        "condition": ["deadzone"]  
    },
    7: {
        "tasks": ["numbered", "numbered", "simple", "simple"],  
        "tokens": ["numbered token 1", "numbered token 2", "simple task", "simple task"],
        "condition": ["disruption"]
    },
    8: {
        "tasks": ["simple", "simple", "simple", "omega"],  
        "tokens": ["simple task", "simple task", "simple task", "Ω"],
        "condition": ["commanders_decision"]  
    },
    9: {
        "tasks": ["numbered", "numbered", "simple", "simple"],  
        "tokens": ["numbered token 1", "numbered token 2", "simple task", "simple task"],
        "condition": ["commanders_distribution"]  
    },
    10: {
        "tasks": ["numbered", "numbered","arrow", "arrow", "simple", "omega"],  
        "tokens": ["numbered token 1", "numbered token 2","<", "<<", "simple task", "Ω"]
    },
}

