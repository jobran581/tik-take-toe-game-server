"""
Tic-Tac-Toe Game Client
Connects to the game server to play Tic-Tac-Toe.
Supports x players with dynamic board size.
"""

import socket
import threading
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Server configuration
HOST = '127.0.0.1'
PORT = 5555

# Global state
my_symbol = None
board_size = 0
current_board = None
current_turn = None
in_game = False
game_over = False
running = True


def print_board(board):
    """Display the game board."""
    if board is None:
        return

    size = len(board)
    print()

    # Print column numbers
    print("   ", end="")
    for col in range(size):
        print(f" {col}  ", end="")
    print()

    # Print top border
    print("   " + "+---" * size + "+")

    for row in range(size):
        # Print row number and cells
        print(f" {row} ", end="")
        for col in range(size):
            cell = board[row][col] if board[row][col] != '.' else ' '
            print(f"| {cell} ", end="")
        print("|")

        # Print row border
        print("   " + "+---" * size + "+")

    print()


def parse_board(board_str):
    """Parse board string from server into 2D list."""
    rows = board_str.split(';')
    board = []
    for row in rows:
        cells = row.split(',')
        board.append(cells)
    return board


def receive_messages(sock):
    """Thread function to receive messages from server."""
    global my_symbol, board_size, current_board, current_turn, in_game, game_over, running

    while running:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                print("\n[DISCONNECTED] Lost connection to server")
                running = False
                break

            # Process each message (may receive multiple)
            messages = data.strip().split('\n')
            for msg in messages:
                if not msg:
                    continue

                parts = msg.split()
                cmd = parts[0]

                if cmd == "CREATED":
                    game_id = parts[1]
                    print(f"\n[GAME] Created game #{game_id}. Waiting for players...")

                elif cmd == "JOINED":
                    game_id = parts[1]
                    print(f"\n[GAME] Joined game #{game_id}")

                elif cmd == "WAITING":
                    count = parts[1]
                    print(f"[GAME] Players: {count}")

                elif cmd == "GAMES":
                    if parts[1] == "NONE":
                        print("\n[GAMES] No games available")
                    else:
                        print("\n[GAMES] Available games:")
                        games_list = parts[1].split(',')
                        for g in games_list:
                            gid, players = g.split(':')
                            print(f"  Game #{gid}: {players} players")

                elif cmd == "START":
                    my_symbol = parts[1]
                    board_size = int(parts[2])
                    in_game = True
                    game_over = False
                    print(f"\n{'='*40}")
                    print(f"[GAME STARTED] You are: {my_symbol}")
                    print(f"Board size: {board_size}x{board_size}")
                    print(f"{'='*40}")

                elif cmd == "BOARD":
                    board_str = parts[1]
                    current_board = parse_board(board_str)
                    print_board(current_board)

                elif cmd == "TURN":
                    current_turn = parts[1]
                    if current_turn == my_symbol:
                        print(f">>> YOUR TURN ({my_symbol}) - Enter: <row> <col>")
                    else:
                        print(f"[WAITING] {current_turn}'s turn...")

                elif cmd == "WIN":
                    winner = parts[1]
                    game_over = True
                    in_game = False
                    print(f"\n{'='*40}")
                    if winner == my_symbol:
                        print("CONGRATULATIONS! YOU WIN!")
                    else:
                        print(f"GAME OVER - {winner} wins!")
                    print(f"{'='*40}")
                    print("\nType 'menu' to return to main menu")

                elif cmd == "DRAW":
                    game_over = True
                    in_game = False
                    print(f"\n{'='*40}")
                    print("GAME OVER - It's a DRAW!")
                    print(f"{'='*40}")
                    print("\nType 'menu' to return to main menu")

                elif cmd == "PLAYER_LEFT":
                    symbol = parts[1]
                    print(f"\n[NOTICE] Player {symbol} has left the game")

                elif cmd == "ERROR":
                    error_msg = ' '.join(parts[1:])
                    print(f"\n[ERROR] {error_msg}")

        except ConnectionResetError:
            print("\n[DISCONNECTED] Server closed connection")
            running = False
            break
        except Exception as e:
            if running:
                print(f"\n[ERROR] {e}")
            break


def print_menu():
    """Print the main menu."""
    print("\n" + "=" * 40)
    print("       TIC-TAC-TOE GAME")
    print("=" * 40)
    print("Commands:")
    print("  CREATE <num_players> - Create a new game")
    print("  LIST                 - List available games")
    print("  JOIN <game_id>       - Join an existing game")
    print("  QUIT                 - Exit")
    print()
    print("In game:")
    print("  <row> <col>          - Make a move (e.g., 0 1)")
    print("=" * 40)


def main():
    """Main client function."""
    global in_game, game_over, running

    # Connect to server
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        print(f"[CONNECTED] Connected to server at {HOST}:{PORT}")
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to server at {HOST}:{PORT}")
        print("Make sure the server is running!")
        return
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return

    # Start receiver thread
    receiver_thread = threading.Thread(target=receive_messages, args=(client_socket,))
    receiver_thread.daemon = True
    receiver_thread.start()

    print_menu()

    # Main input loop
    try:
        while running:
            try:
                user_input = input().strip()
                if not user_input:
                    continue

                # Handle local commands
                if user_input.lower() == 'menu':
                    in_game = False
                    game_over = False
                    print_menu()
                    continue

                if user_input.lower() == 'help':
                    print_menu()
                    continue

                # If in game and input looks like coordinates, add MOVE prefix
                if in_game and not game_over:
                    parts = user_input.split()
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        user_input = f"MOVE {user_input}"

                # Send command to server
                client_socket.send((user_input + "\n").encode('utf-8'))

                # Handle quit
                if user_input.upper() == 'QUIT':
                    running = False
                    break

            except EOFError:
                break

    except KeyboardInterrupt:
        print("\n[EXITING] Goodbye!")

    finally:
        running = False
        client_socket.close()


if __name__ == "__main__":
    main()
