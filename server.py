"""
Tic-Tac-Toe Game Server
A multi-client server that manages multiple concurrent Tic-Tac-Toe games.
Supports x players with dynamic board size (x+1)^2.
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

# Player symbols for up to 10 players
# Requirements: X, O, ∆ for first three players
SYMBOLS = ['X', 'O', '∆', '□', '◇', '☆', '◎', '♠', '♣', '♥']

# Global game storage
games = {}  # game_id -> Game object
game_counter = 0
games_lock = threading.Lock()


class Game:
    """Represents a single Tic-Tac-Toe game."""

    def __init__(self, game_id, num_players):
        self.game_id = game_id
        self.num_players = num_players
        self.board_size = num_players + 1  # (x+1) for x players
        self.board = [['.' for _ in range(self.board_size)] for _ in range(self.board_size)]
        self.players = []  # List of (client_socket, symbol)
        self.current_turn = 0  # Index of current player
        self.started = False
        self.finished = False
        self.winner = None
        self.lock = threading.Lock()

    def add_player(self, client_socket):
        """Add a player to the game. Returns the player's symbol."""
        with self.lock:
            if len(self.players) >= self.num_players:
                return None
            symbol = SYMBOLS[len(self.players)]
            self.players.append((client_socket, symbol))
            return symbol

    def is_full(self):
        """Check if game has all players."""
        return len(self.players) >= self.num_players

    def start_game(self):
        """Start the game."""
        with self.lock:
            self.started = True

    def get_current_symbol(self):
        """Get the symbol of the player whose turn it is."""
        return SYMBOLS[self.current_turn]

    def make_move(self, row, col, symbol):
        """
        Attempt to make a move.
        Returns: (success, message)
        """
        with self.lock:
            # Check if game is active
            if not self.started or self.finished:
                return False, "Game is not active"

            # Check if it's this player's turn
            if SYMBOLS[self.current_turn] != symbol:
                return False, "Not your turn"

            # Validate position
            if row < 0 or row >= self.board_size or col < 0 or col >= self.board_size:
                return False, "Invalid position"

            # Check if cell is empty
            if self.board[row][col] != '.':
                return False, "Cell is occupied"

            # Make the move
            self.board[row][col] = symbol

            # Check for winner
            if self.check_winner(symbol):
                self.finished = True
                self.winner = symbol
                return True, "WIN"

            # Check for draw
            if self.check_draw():
                self.finished = True
                return True, "DRAW"

            # Move to next player
            self.current_turn = (self.current_turn + 1) % self.num_players
            return True, "OK"

    def check_winner(self, symbol):
        """Check if the given symbol has won (3 in a row)."""
        # Check all possible lines of 3
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]  # horizontal, vertical, diagonal down-right, diagonal down-left

        for row in range(self.board_size):
            for col in range(self.board_size):
                if self.board[row][col] != symbol:
                    continue

                # Check each direction from this cell
                for dr, dc in directions:
                    count = 1
                    # Check forward
                    r, c = row + dr, col + dc
                    while 0 <= r < self.board_size and 0 <= c < self.board_size and self.board[r][c] == symbol:
                        count += 1
                        r += dr
                        c += dc
                    # Check backward
                    r, c = row - dr, col - dc
                    while 0 <= r < self.board_size and 0 <= c < self.board_size and self.board[r][c] == symbol:
                        count += 1
                        r -= dr
                        c -= dc

                    if count >= 3:
                        return True
        return False

    def check_draw(self):
        """Check if the board is full (draw)."""
        for row in self.board:
            for cell in row:
                if cell == '.':
                    return False
        return True

    def get_board_string(self):
        """Get board as a string for transmission."""
        rows = []
        for row in self.board:
            rows.append(','.join(row))
        return ';'.join(rows)

    def remove_player(self, client_socket):
        """Remove a player from the game."""
        with self.lock:
            for i, (sock, symbol) in enumerate(self.players):
                if sock == client_socket:
                    self.players.pop(i)
                    return symbol
        return None

    def broadcast(self, message, exclude=None):
        """Send a message to all players in the game."""
        for sock, symbol in self.players:
            if sock != exclude:
                try:
                    sock.send(message.encode('utf-8'))
                except:
                    pass


def handle_client(client_socket, client_address):
    """Handle a single client connection."""
    global game_counter

    print(f"[NEW CONNECTION] {client_address} connected")
    current_game = None
    player_symbol = None

    try:
        while True:
            # Receive data from client
            data = client_socket.recv(1024).decode('utf-8').strip()
            if not data:
                break

            print(f"[{client_address}] Received: {data}")
            parts = data.split()
            command = parts[0].upper()

            if command == "CREATE":
                # Create a new game
                if len(parts) < 2:
                    client_socket.send("ERROR Missing number of players\n".encode('utf-8'))
                    continue

                try:
                    num_players = int(parts[1])
                    if num_players < 2 or num_players > 10:
                        client_socket.send("ERROR Players must be between 2 and 10\n".encode('utf-8'))
                        continue
                except ValueError:
                    client_socket.send("ERROR Invalid number of players\n".encode('utf-8'))
                    continue

                with games_lock:
                    game_counter += 1
                    game_id = game_counter
                    game = Game(game_id, num_players)
                    games[game_id] = game

                # Creator joins the game
                player_symbol = game.add_player(client_socket)
                current_game = game

                client_socket.send(f"CREATED {game_id}\n".encode('utf-8'))
                client_socket.send(f"WAITING 1/{num_players}\n".encode('utf-8'))
                print(f"[GAME {game_id}] Created with {num_players} players")

            elif command == "LIST":
                # List available games
                with games_lock:
                    available = []
                    for gid, game in games.items():
                        if not game.started and not game.finished:
                            available.append(f"{gid}:{len(game.players)}/{game.num_players}")

                if available:
                    client_socket.send(f"GAMES {','.join(available)}\n".encode('utf-8'))
                else:
                    client_socket.send("GAMES NONE\n".encode('utf-8'))

            elif command == "JOIN":
                # Join an existing game
                if len(parts) < 2:
                    client_socket.send("ERROR Missing game ID\n".encode('utf-8'))
                    continue

                try:
                    game_id = int(parts[1])
                except ValueError:
                    client_socket.send("ERROR Invalid game ID\n".encode('utf-8'))
                    continue

                with games_lock:
                    if game_id not in games:
                        client_socket.send("ERROR Game not found\n".encode('utf-8'))
                        continue
                    game = games[game_id]

                if game.started:
                    client_socket.send("ERROR Game already started\n".encode('utf-8'))
                    continue

                if game.is_full():
                    client_socket.send("ERROR Game is full\n".encode('utf-8'))
                    continue

                player_symbol = game.add_player(client_socket)
                current_game = game

                client_socket.send(f"JOINED {game_id}\n".encode('utf-8'))

                # Notify all players of current count
                msg = f"WAITING {len(game.players)}/{game.num_players}\n"
                game.broadcast(msg)

                print(f"[GAME {game_id}] Player joined: {len(game.players)}/{game.num_players}")

                # If game is now full, start it
                if game.is_full():
                    game.start_game()
                    # Send START to each player with their symbol and board size
                    for sock, sym in game.players:
                        try:
                            sock.send(f"START {sym} {game.board_size}\n".encode('utf-8'))
                        except:
                            pass
                    # Send initial board and turn info
                    board_str = game.get_board_string()
                    game.broadcast(f"BOARD {board_str}\n")
                    game.broadcast(f"TURN {game.get_current_symbol()}\n")
                    print(f"[GAME {game_id}] Game started!")

            elif command == "MOVE":
                # Make a move
                if current_game is None:
                    client_socket.send("ERROR Not in a game\n".encode('utf-8'))
                    continue

                if len(parts) < 3:
                    client_socket.send("ERROR Missing row or column\n".encode('utf-8'))
                    continue

                try:
                    row = int(parts[1])
                    col = int(parts[2])
                except ValueError:
                    client_socket.send("ERROR Invalid row or column\n".encode('utf-8'))
                    continue

                success, result = current_game.make_move(row, col, player_symbol)

                if not success:
                    client_socket.send(f"ERROR {result}\n".encode('utf-8'))
                else:
                    # Broadcast updated board
                    board_str = current_game.get_board_string()
                    current_game.broadcast(f"BOARD {board_str}\n")

                    if result == "WIN":
                        current_game.broadcast(f"WIN {player_symbol}\n")
                        print(f"[GAME {current_game.game_id}] {player_symbol} wins!")
                    elif result == "DRAW":
                        current_game.broadcast("DRAW\n")
                        print(f"[GAME {current_game.game_id}] Draw!")
                    else:
                        # Send whose turn it is
                        current_game.broadcast(f"TURN {current_game.get_current_symbol()}\n")

            elif command == "QUIT":
                break

            else:
                client_socket.send("ERROR Unknown command\n".encode('utf-8'))

    except Exception as e:
        print(f"[ERROR] {client_address}: {e}")

    finally:
        # Clean up
        if current_game is not None:
            symbol = current_game.remove_player(client_socket)
            if symbol:
                current_game.broadcast(f"PLAYER_LEFT {symbol}\n")
                print(f"[GAME {current_game.game_id}] Player {symbol} left")

        client_socket.close()
        print(f"[DISCONNECTED] {client_address}")


def admin_console(server_socket):
    """Admin console for server commands."""
    print("[ADMIN] Type 'stop' to shut down the server")
    while True:
        try:
            cmd = input().strip().lower()
            if cmd == 'stop':
                print("[SERVER] Shutting down...")
                server_socket.close()
                break
        except EOFError:
            break


def main():
    """Main server function."""
    # Create server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

        # Start admin console thread
        admin_thread = threading.Thread(target=admin_console, args=(server_socket,))
        admin_thread.daemon = True
        admin_thread.start()

        while True:
            # Accept new connections
            try:
                client_socket, client_address = server_socket.accept()
            except OSError:
                # Socket was closed by admin
                break

            # Create a new thread for this client
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_thread.daemon = True
            client_thread.start()

            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 2}")

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
