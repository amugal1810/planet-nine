from the_crew_game import TheCrewGame, GameplayError
from openai import OpenAI
import re
import os
import sys
from unittest.mock import patch
import random
from dotenv import load_dotenv
load_dotenv()


# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def mock_input(prompt_text, responses=None):
    """Simulates input() but uses OpenAI to generate responses to all questions."""
    print(f"mock_input called with prompt: {prompt_text}")  # Debugging statement
    
    # Skip message processing for empty or whitespace-only prompts
    if not prompt_text.strip():
        print("Automated response (empty prompt): ")
        return ""
    
    # Gather game state and context to send with the question
    game_context = (
     #   f"Current game state:\n{game_state}\n"
        f"Question: {prompt_text}\n"
        f"Make a decision based on this context.\n"
    )
    
    # Use OpenAI to generate a response to the question
    ai_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": 
                "You are playing The Crew: The Quest for Planet Nine board game. "
                "Answer ONLY with the exact text of your choice or decision, nothing else. "
                "For card choices, respond with just the card code (like 'P5' or 'R2'). "
                "For player choices, respond with just the number (like '1', '2', or '3'). "
                "For yes/no questions, respond with just 'yes' or 'no'. "
                "Do not include explanations, reasoning, or anything besides your direct answer."
            },
            {"role": "user", "content": game_context}
        ],
        max_tokens=10  # Keep responses short
    )
    
    response = ai_response.choices[0].message.content.strip()
    print(f"AI response: {response}")  # Debugging statement
    return response

def run_rollout():
    game = type('DummyGame', (object,), {'state': lambda player_id: f"Dummy state for player {player_id}"})()
    # Apply the patch first to ensure all input() calls are handled by mock_input
    with patch('builtins.input', side_effect=lambda prompt: mock_input(prompt)):
        print("Patch applied. Running game...")  # Debugging statement
        game = TheCrewGame(num_players=3, num_mission=2, seed=42)
        # Initialize the game **after** patching input
          # Adjust to use mission 8 directly
        game_log = []
        chat_history = {str(i): [] for i in range(max(3,game.num_players))}
        # Handle the game start
        starting_player_id = game.whose_turn()
        state = game.state(starting_player_id)
        
        print(f"\nPlayer {starting_player_id + 1} will start the game.")
        
        # Now we check if there's a distress signal **after** applying the patch
        if "distress signal" in state.lower():
            print("Distress signal detected. AI will handle card passing.")
        else:
            print("No distress signal detected. Proceeding directly to game.")
        
        try:
            while not game.is_over():
                if game.failed:
                    print("\n🚨 Mission failed. Exiting early.")
                    break  # Break the loop when game.failed is True
                
                pid = game.whose_turn()
                state = game.state(pid)
                log_string = f"\nPlayer: {pid + 1}\nState:\n{state}\n"
                
                # Proceed with AI's suggested move
                chat = chat_history[str(pid)] + [{
                    "role": "user",
                    "content": (
                        f"You are an expert board game player assisting in a game of The Crew: The Quest for Planet Nine.\n"
                        f"Here is the current state:\n{state}\n"
                        "Suggestions for the next move should always follow these rules:\n"
                        "1. Complete numbered tasks first (1, 2, 3, etc.).\n"
                        "2. After all numbered tasks are completed, complete the arrowed tasks in the following order: < before << before <<< before <<<<.\n"
                        "3. The omega task must be completed last, after all other tasks are done.\n"
                        "4. Simple tasks can be completed at any time after the numbered tasks and before the omega task.\n"
                        "5. If the distress signal is active (before the first trick), players must pass cards in the specified direction (clockwise or counter-clockwise).\n"
                        "6. Only the assigned player may complete a task.\n"
                        "7. Always follow suit unless playing a Rocket card.\n\n"
                        "8. Focus on the tasks assigned to the players. you have to complete those to win the game and remember the task has to be completed by the player it is assigned to. A task is won when u win the round that task card was played in for example if b2 is assigned to player 1, then player 1 has to play the highest b card in the round to win that round in which b2 is played in.\n"
                        "9. You will be given multiple atttempts. You have to sucessfully finish the mission in minimum attempts as possible. If you use the distress token, your final number of attemtps will be increadsed by 1.\n"
                        "10. You can attempt one mission a maximum of 10 times.\n"
                        "Provide short reasoning, then your move in JSON format like:\n"
                        "{\"move\": \"P5\"} or {\"move\": \"RADIO P5\"}.\nOnly use cards from the player's hand."
                    )
                }]
                
                # Call OpenAI API to get the AI response
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=chat
                )
                
                text_response = response.choices[0].message.content.strip()
                chat_history[str(pid)].append({"role": "assistant", "content": text_response})
                
                # Match the AI's response to extract the move
                match = re.search(r'"move"\s*:\s*"([^"]+)"', text_response)
                if match:
                    move = match.group(1)
                    log_string += f"🧠 Suggested move: {move}\n"
                    try:
                        game.play(move=move, player_id=pid)
                        log_string += f"✅ Player {pid + 1} played: {move}\n"
                        log_string += f"🂠 Remaining hand: {sorted(game.hands[pid])}\n"
                    except GameplayError as e:
                        log_string += f"❌ Illegal move: {e}\n"
                        chat_history[str(pid)].append({
                            "role": "user",
                            "content": f"Illegal move: {e}. Try again."
                        })
                        print(log_string)
                        continue
                    except RuntimeError as e:
                        # Log the error but don't re-raise, let the main loop handle it
                        log_string += f"\n🚨 Mission failed during move: {e}"
                        game.failed = True  # Make sure failed flag is set
                        game_log.append(log_string)
                        print(log_string)
                        break  # Break out of the main loop
                
                game_log.append(log_string)
                print(log_string)
            
            # After the game is over (whether normally or due to failure)
            score = game.attempts+game.distress_token_usage
            game_log.append(f"\nFinal Scores: {score} attempts taken. Distress token used: {game.distress_signal_active}")
            print(f"\nFinal Scores: {score} attempts taken. Distress token used: {game.distress_signal_active}")
            
            if game.failed:
                sys.exit(1)  # Exit with error code if the mission failed
        
        except Exception as e:
            print(f"\n🚨 Unexpected error: {e}")
            sys.exit(1)

# Run normally now
if __name__ == "__main__":
    run_rollout()
