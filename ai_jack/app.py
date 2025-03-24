from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random
import time
import copy
from queue import PriorityQueue

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

class NPuzzle:
    def __init__(self, N):
        self.N = N
        self.board = self.generate_random_board()
        self.final_state = self.generate_final_state()
        self.tree = {'name': 'Start', 'board': self.board, 'children': []}
        self.current_path = [self.tree]
        self.solution_found = False

    def generate_random_board(self):
        """Generate a random solvable N-Puzzle board."""
        numbers = list(range(self.N * self.N))
        random.shuffle(numbers)
        return [numbers[i:i + self.N] for i in range(0, len(numbers), self.N)]

    def generate_final_state(self):
        """Generate the ordered final state."""
        return [[(i * self.N + j + 1) % (self.N * self.N) for j in range(self.N)] for i in range(self.N)]

    def is_solvable(self):
        """Check if the generated puzzle is solvable."""
        flat_board = sum(self.board, [])
        inversions = sum(1 for i in range(len(flat_board)) for j in range(i + 1, len(flat_board))
                         if flat_board[i] and flat_board[j] and flat_board[i] > flat_board[j])
        if self.N % 2:  # Odd grid size
            return inversions % 2 == 0
        else:  # Even grid size
            row = next(i for i, row in enumerate(self.board) if 0 in row)
            return (inversions + row) % 2 == 0

    def find_zero(self, board):
        """Find the position of the empty space (0)."""
        for i, row in enumerate(board):
            if 0 in row:
                return i, row.index(0)

    def generate_moves(self, board):
        """Generate possible moves from the current state."""
        moves = []
        x, y = self.find_zero(board)
        directions = {'Up': (-1, 0), 'Down': (1, 0), 'Left': (0, -1), 'Right': (0, 1)}

        for direction, (dx, dy) in directions.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.N and 0 <= ny < self.N:
                new_board = copy.deepcopy(board)
                new_board[x][y], new_board[nx][ny] = new_board[nx][ny], new_board[x][y]
                moves.append((direction, new_board))
        return moves

    def calculate_manhattan_distance(self, board):
        """Calculate Manhattan distance for heuristic."""
        distance = 0
        for i in range(self.N):
            for j in range(self.N):
                value = board[i][j]
                if value != 0:
                    target_x, target_y = divmod(value - 1, self.N)
                    distance += abs(target_x - i) + abs(target_y - j)
        return distance

    def solve_recursive(self):
        """Solve the puzzle using A* algorithm."""
        initial_board = self.board
        visited = set()
        pq = PriorityQueue()
        pq.put((0, initial_board, self.tree))

        while not pq.empty():
            _, current_board, current_node = pq.get()

            # Mark the state as visited
            visited.add(tuple(tuple(row) for row in current_board))

            if current_board == self.final_state:
                current_node['children'].append({'name': 'Goal', 'board': current_board, 'children': []})
                socketio.emit('update', {'board': current_board, 'tree': self.tree})
                time.sleep(0.02)
                return True

            for direction, new_board in self.generate_moves(current_board):
                board_tuple = tuple(tuple(row) for row in new_board)
                if board_tuple not in visited:
                    # Calculate heuristic + cost (A* search)
                    heuristic = self.calculate_manhattan_distance(new_board)
                    cost = len(current_node['children'])
                    priority = heuristic + cost

                    # Add child node to the tree
                    child_node = {'name': direction, 'board': new_board, 'children': []}
                    current_node['children'].append(child_node)

                    # Add to priority queue
                    pq.put((priority, new_board, child_node))

                    # Send live updates
                    socketio.emit('update', {'board': new_board, 'tree': self.tree})
                    time.sleep(0.02)

        return False

    def get_tree(self):
        """Return the full state space tree."""
        return self.tree


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('solve')
def handle_solve(data):
    N = int(data.get('N', 3))
    puzzle = NPuzzle(N)

    while not puzzle.is_solvable():
        puzzle.board = puzzle.generate_random_board()

    socketio.emit('update', {'board': puzzle.board, 'tree': puzzle.get_tree()})
    puzzle.solve_recursive()
    emit('complete', {'solution_found': puzzle.solution_found, 'tree': puzzle.get_tree()})


if __name__ == '__main__':
    socketio.run(app, debug=True)
