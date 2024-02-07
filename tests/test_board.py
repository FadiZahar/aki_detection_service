import unittest

from prediction_system import *

class TestBoard(unittest.TestCase):
    def setUp(self):
        pass

    def test_board(self):
        is_ship_hit, has_ship_sunk = self.board.is_attacked_at((3, 4))
        assert is_ship_hit == True
        assert has_ship_sunk == False
    
    def test_are_ships_within_bounds(self):
        output = self.board.are_ships_within_bounds()
        assert output == True
    
    def test_are_ships_too_close(self):
        output = self.board.are_ships_too_close()
        assert output == False
    
    def test_have_all_ships_sunk(self):
        output = self.board.have_all_ships_sunk()
        assert output == False

        self.board.is_attacked_at((3, 1))
        self.board.is_attacked_at((3, 2))
        self.board.is_attacked_at((3, 3))
        self.board.is_attacked_at((3, 4))
        self.board.is_attacked_at((3, 5))

        self.board.is_attacked_at((9, 7))
        self.board.is_attacked_at((9, 8))
        self.board.is_attacked_at((9, 9))
        self.board.is_attacked_at((9, 10))

        self.board.is_attacked_at((1, 9))
        self.board.is_attacked_at((2, 9))
        self.board.is_attacked_at((3, 9))
        
        self.board.is_attacked_at((5, 2))
        self.board.is_attacked_at((6, 2))

        self.board.is_attacked_at((8, 3))

        output = self.board.have_all_ships_sunk()
        assert output == True

    def test_is_attacked_at(self):
        output = self.board.is_attacked_at((3, 1))
        assert output == (True, False)
        self.board.is_attacked_at((3, 2))
        self.board.is_attacked_at((3, 3))
        self.board.is_attacked_at((3, 4))
        output = self.board.is_attacked_at((3, 5))
        assert output == (True, True)
        output = self.board.is_attacked_at((3, 6))
        assert output == (False, False)
